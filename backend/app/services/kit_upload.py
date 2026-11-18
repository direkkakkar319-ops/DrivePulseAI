"""Bounded, memory-only multipart ingestion and strict KIT raw CSV validation."""

import asyncio
import csv
import hashlib
import io
import math
import re
import time
from dataclasses import dataclass
from datetime import date

from fastapi import Request
from python_multipart import MultipartParser
from python_multipart.exceptions import MultipartParseError
from python_multipart.multipart import parse_options_header
from starlette.requests import ClientDisconnect

from app.config import Settings
from app.services.kit_preprocessing import KitWindowAccumulator, parse_time
from app.services.kit_samples import (
    KitWindow,
    KitWindowPair,
    make_window_pairs,
    validate_window,
)

RAW_HEADERS = (
    "Time",
    "Engine Coolant Temperature [°C]",
    "Intake Manifold Absolute Pressure [kPa]",
    "Engine RPM [RPM]",
    "Vehicle Speed Sensor [km/h]",
    "Intake Air Temperature [°C]",
    "Air Flow Rate from Mass Flow Sensor [g/s]",
    "Absolute Throttle Position [%]",
    "Ambient Air Temperature [°C]",
    "Accelerator Pedal Position D [%]",
    "Accelerator Pedal Position E [%]",
)
MAX_LINE_CHARACTERS = 2048
MAX_FIELD_CHARACTERS = 128
MULTIPART_OVERHEAD = 16 * 1024
MAX_MODEL_MAGNITUDE = (
    3.4028234663852886e38  # Finite float32 input bound, not a physical range.
)


class UploadError(ValueError):
    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class UploadedRecording:
    recording_id: str
    recording_date: str
    input_bytes: int
    accepted_rows: int
    missing_cells: int
    discarded_windows: int
    backward_jumps: int
    duplicate_timestamps: int
    windows: tuple[KitWindow, ...]
    pairs: tuple[KitWindowPair, ...]


class _MultipartUpload:
    """No UploadFile/SpooledTemporaryFile: authentication precedes body consumption."""

    def __init__(self, maximum: int):
        self.maximum = maximum
        self.data = bytearray()
        self.day = bytearray()
        self.seen = set()
        self.parts = 0
        self.complete = False
        self.name = None
        self.headers = {}
        self.header_name = bytearray()
        self.header_value = bytearray()

    def on_part_begin(self):
        self.parts += 1
        if self.parts > 2:
            raise UploadError(
                "Exactly one file and one recording_date field are supported"
            )
        self.headers = {}
        self.name = None

    def on_header_field(self, data, start, end):
        self.header_name.extend(data[start:end])

    def on_header_value(self, data, start, end):
        self.header_value.extend(data[start:end])

    def on_header_end(self):
        key = bytes(self.header_name).lower()
        if key in self.headers:
            raise UploadError("Duplicate multipart headers")
        self.headers[key] = bytes(self.header_value)
        self.header_name.clear()
        self.header_value.clear()

    def on_headers_finished(self):
        disposition, options = parse_options_header(
            self.headers.get(b"content-disposition")
        )
        name = options.get(b"name")
        if (
            disposition != b"form-data"
            or name not in {b"file", b"recording_date"}
            or name in self.seen
        ):
            raise UploadError(
                "Exactly one file and one recording_date field are supported"
            )
        self.name = name
        self.seen.add(name)
        if name == b"recording_date":
            if b"filename" in options:
                raise UploadError("recording_date must be a text field")
            return
        filename = options.get(b"filename", b"")
        if (
            not filename.lower().endswith(b".csv")
            or len(filename) > 255
            or b"\x00" in filename
        ):
            raise UploadError("Upload one raw CSV file with a .csv filename", 415)
        # Filename is never used as a path, echoed, or used to infer date/vehicle.
        mime, parameters = parse_options_header(self.headers.get(b"content-type"))
        mime = mime.lower()
        if mime not in {
            b"text/csv",
            b"application/csv",
            b"text/plain",
            b"application/octet-stream",
        }:
            raise UploadError("Unsupported upload media type", 415)
        if parameters.get(b"charset", b"utf-8").lower() not in {
            b"utf-8",
            b"utf8",
            b"utf-8-sig",
        }:
            raise UploadError("CSV encoding must be UTF-8", 415)

    def on_part_data(self, data, start, end):
        target = self.data if self.name == b"file" else self.day
        maximum = self.maximum if self.name == b"file" else 32
        if len(target) + end - start > maximum:
            raise UploadError("Upload exceeds the configured size limit", 413)
        target.extend(data[start:end])

    def on_end(self):
        self.complete = True

    def finish(self):
        if not self.complete or self.seen != {b"file", b"recording_date"}:
            raise UploadError(
                "Incomplete multipart upload; file and recording_date are required"
            )
        if not self.data:
            raise UploadError("CSV file is empty")
        try:
            day = self.day.decode("ascii")
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
                raise ValueError
            date.fromisoformat(day)
        except (ValueError, UnicodeError):
            raise UploadError(
                "recording_date must be a valid YYYY-MM-DD date"
            ) from None
        return bytes(self.data), day

    def clear(self):
        self.data.clear()
        self.day.clear()
        self.header_name.clear()
        self.header_value.clear()
        self.headers.clear()


async def receive_upload(request: Request, settings: Settings) -> tuple[bytes, str]:
    content_type, parameters = parse_options_header(request.headers.get("content-type"))
    boundary = parameters.get(b"boundary", b"")
    if content_type != b"multipart/form-data":
        raise UploadError("Use multipart/form-data", 415)
    if not 1 <= len(boundary) <= 70 or any(b < 33 or b > 126 for b in boundary):
        raise UploadError("Invalid multipart boundary")
    maximum = settings.kit_upload_max_bytes + MULTIPART_OVERHEAD
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > maximum:
        raise UploadError("Upload exceeds the configured size limit", 413)
    upload = _MultipartUpload(settings.kit_upload_max_bytes)
    callbacks = {
        name: getattr(upload, name)
        for name in (
            "on_part_begin",
            "on_header_field",
            "on_header_value",
            "on_header_end",
            "on_headers_finished",
            "on_part_data",
            "on_end",
        )
    }
    parser = MultipartParser(
        boundary, callbacks, max_header_count=4, max_header_size=2048
    )
    total = 0
    try:
        async for chunk in request.stream():
            total += len(chunk)
            if total > maximum:
                raise UploadError("Upload exceeds the configured size limit", 413)
            for start in range(0, len(chunk), 65536):
                parser.write(chunk[start : start + 65536])
                # Let the request deadline/cancellation run even for one large ASGI chunk.

                await asyncio.sleep(0)
        parser.finalize()
        return upload.finish()
    except MultipartParseError:
        raise UploadError("Malformed multipart upload") from None
    except ClientDisconnect:
        raise UploadError("Upload interrupted", 408) from None
    finally:
        upload.clear()


def prepare_csv(
    data: bytes, day: str, settings: Settings, deadline: float
) -> UploadedRecording:
    """Accept a stricter verified subset; valid readings use the original kernel."""
    accumulator = KitWindowAccumulator()
    if len(data) > settings.kit_upload_max_bytes:
        raise UploadError("Upload exceeds the configured size limit", 413)
    rows = missing = 0
    try:
        with io.TextIOWrapper(
            io.BytesIO(data), encoding="utf-8-sig", newline=""
        ) as stream:
            line_number = 0
            while True:
                if time.monotonic() >= deadline:
                    raise UploadError("CSV analysis timed out", 504)
                line = stream.readline(MAX_LINE_CHARACTERS + 1)
                if not line:
                    break
                line_number += 1
                if len(line) > MAX_LINE_CHARACTERS:
                    raise UploadError("CSV line exceeds parsing limit", 413)
                if "\x00" in line:
                    raise UploadError("CSV contains invalid characters")
                fields = next(csv.reader([line], strict=True))
                if len(fields) != 11 or any(
                    len(field) > MAX_FIELD_CHARACTERS for field in fields
                ):
                    raise UploadError(
                        "CSV must contain exactly eleven bounded fields per row"
                    )
                if line_number == 1:
                    # Both variants are present in the publisher archive. No other alias.
                    if (
                        tuple(field.replace("Â°C", "°C") for field in fields)
                        != RAW_HEADERS
                    ):
                        raise UploadError("Unsupported KIT columns, order or units")
                    continue
                rows += 1
                if rows > settings.kit_upload_max_rows:
                    raise UploadError("CSV exceeds row limit", 413)
                if not re.fullmatch(r"\d{2}:\d{2}:\d{2}\.\d{1,6}", fields[0].strip()):
                    raise UploadError("Invalid KIT clock timestamp")
                timestamp = parse_time(fields[0])
                if timestamp is None:
                    raise UploadError("Invalid KIT clock timestamp")
                values = []
                for cell in fields[1:]:
                    if not cell.strip():
                        missing += 1
                        values.append(None)
                        continue
                    try:
                        number = float(cell.strip())
                    except ValueError:
                        raise UploadError("Non-numeric telemetry cell") from None
                    if not math.isfinite(number) or abs(number) > MAX_MODEL_MAGNITUDE:
                        raise UploadError(
                            "Telemetry values must be finite and model-representable"
                        )
                    values.append(number)
                accumulator.add(timestamp, values)
                if (
                    len(accumulator.buckets) > settings.kit_upload_max_windows
                    or accumulator.segment_id + 1 > settings.kit_upload_max_segments
                ):
                    raise UploadError(
                        "CSV exceeds window or segment workload limit", 413
                    )
    except UnicodeError:
        raise UploadError("CSV encoding must be UTF-8", 415) from None
    except csv.Error:
        raise UploadError("Malformed CSV; multiline fields are unsupported") from None
    if not rows:
        raise UploadError("CSV contains no telemetry rows")
    recording_id = "upload-" + hashlib.sha256(data).hexdigest()[:24]
    windows = []
    for segment, start, features in accumulator.windows():
        if time.monotonic() >= deadline:
            raise UploadError("CSV analysis timed out", 504)
        window = KitWindow(recording_id, day, "uploaded", segment, start, features)
        validate_window(window)
        windows.append(window)
    canonical = tuple(windows)
    pairs = make_window_pairs(canonical)
    if not pairs:
        raise UploadError(
            "At least two usable adjacent ten-second windows are required"
        )
    if len(pairs) > settings.kit_upload_max_pairs:
        raise UploadError("CSV exceeds inference pair limit", 413)
    if (
        math.ceil(len(pairs) / settings.kit_ml_batch_size)
        > settings.kit_upload_max_batches
    ):
        raise UploadError("CSV exceeds inference batch workload limit", 413)
    return UploadedRecording(
        recording_id,
        day,
        len(data),
        rows,
        missing,
        len(accumulator.buckets) - len(windows),
        accumulator.backward_jumps,
        accumulator.duplicate_timestamps,
        canonical,
        pairs,
    )
