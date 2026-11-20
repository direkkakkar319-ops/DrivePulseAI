"""Bounded leaf-csv-v1 ingestion and shared sample/upload orchestration."""

import csv
import hashlib
import io
import math
from collections import defaultdict
from itertools import pairwise
from pathlib import Path
from statistics import mean, median

from python_multipart import MultipartParser
from python_multipart.multipart import parse_options_header

from app.schemas.leaf_analysis import (
    FEATURES,
    SIGNALS,
    AnomalyAnalysis,
    Availability,
    BatteryOverview,
    LeafAnalysis,
    Reading,
    ScoredReading,
)
from app.services.ml_errors import MLServiceError

SAMPLE_ID = "nissan-leaf-synthetic-integration-v1"
SAMPLE_PATH = (
    Path(__file__).resolve().parents[1]
    / "data/samples/nissan/synthetic-integration-v1.csv"
)
LIMITATIONS = [
    "Isolation Forest flags unusual telemetry, not confirmed mechanical faults or calibrated failure probabilities.",
    "SHAP explains the model score, not physical causes. Only the three strongest contributions are returned.",
    "The anomaly model was trained on one Nissan Leaf; generalization to other vehicles is unvalidated.",
    "RUL is an experimental reported-SOH threshold extrapolation, not remaining driving range or validated battery life.",
    "Analysis and uploaded telemetry are transient, not stored or associated with Garage vehicles.",
    "Units follow the existing Leaf implementation; original workbook and current polarity remain unverified locally.",
]
UNITS = {
    "Pack_Avg_C_Temp": "°C",
    "SOC": "%",
    "SOH": "%",
    "HV_Bat_Voltage": "V",
    "HV_Bat_Current_2": "A (sign convention unverified)",
    "Pack_1_C_Temp": "°C",
    "Pack_2_C_Temp": "°C",
    "Pack_4_C_Temp": "°C",
    "Odometer": "km",
    "Speed": "source unit unverified",
    "Instant_kW": "kW (source-derived)",
    "kWh_Remaining": "kWh (source semantics unverified)",
}


class CSVError(Exception):
    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


def catalog() -> dict:
    return {
        "schema_version": 1,
        "samples": [
            {
                "id": SAMPLE_ID,
                "display_name": "Nissan Leaf · Synthetic integration fixture",
                "provenance": "Project-authored synthetic values, not a real vehicle recording. No scientific validation is implied.",
                "synthetic": True,
                "format_version": "leaf-csv-v1",
                "limitations": LIMITATIONS,
            }
        ],
    }


async def receive_csv(request, settings) -> bytes:
    # In-memory bounded multipart parser: no spooled files or cleanup leaks.
    maximum = settings.leaf_upload_max_bytes
    mime, options = parse_options_header(request.headers.get("content-type", ""))
    boundary = options.get(b"boundary", b"")
    if mime != b"multipart/form-data" or not 1 <= len(boundary) <= 200:
        raise CSVError("Expected multipart/form-data with one CSV file", 415)
    data, header_name, header_value = bytearray(), bytearray(), bytearray()
    headers = {}
    parts = 0
    complete = False

    def begin():
        nonlocal parts
        parts += 1
        if parts != 1:
            raise CSVError("Submit exactly one file field named file")

    def name(chunk, start, end):
        header_name.extend(chunk[start:end])

    def value(chunk, start, end):
        header_value.extend(chunk[start:end])

    def header_end():
        key = bytes(header_name).lower()
        if key in headers:
            raise CSVError("Duplicate multipart headers")
        headers[key] = bytes(header_value)
        header_name.clear()
        header_value.clear()

    def ready():
        disposition, fields = parse_options_header(
            headers.get(b"content-disposition", b"")
        )
        if (
            disposition != b"form-data"
            or fields.get(b"name") != b"file"
            or b"filename" not in fields
        ):
            raise CSVError("Submit exactly one file field named file")
        # Filename is never used as a path or returned. Content is validated separately.

    def content(chunk, start, end):
        data.extend(chunk[start:end])
        if len(data) > maximum:
            raise CSVError("CSV exceeds the size limit", 413)

    def end():
        nonlocal complete
        complete = True

    parser = MultipartParser(
        boundary,
        {
            "on_part_begin": begin,
            "on_header_field": name,
            "on_header_value": value,
            "on_header_end": header_end,
            "on_headers_finished": ready,
            "on_part_data": content,
            "on_end": end,
        },
    )
    consumed = 0
    try:
        async for chunk in request.stream():
            consumed += len(chunk)
            if consumed > maximum + 65536:
                raise CSVError("Upload exceeds the size limit", 413)
            parser.write(chunk)
        parser.finalize()
    except CSVError:
        raise
    except Exception:  # noqa: BLE001 -- sanitize multipart parser failures.
        raise CSVError("Malformed multipart upload") from None
    if not complete or parts != 1:
        raise CSVError("Incomplete multipart upload")
    return bytes(data)


def parse_csv(data: bytes, settings) -> tuple[list[Reading], dict]:
    if not data:
        raise CSVError("CSV is empty")
    if len(data) > settings.leaf_upload_max_bytes:
        raise CSVError("CSV exceeds the size limit", 413)
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise CSVError("Only UTF-8 CSV is supported", 415) from None
    if "\x00" in text:
        raise CSVError("Binary files are not supported", 415)
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        header = next(reader)
        if not 2 <= len(header) <= len(SIGNALS) + 2 or len(set(header)) != len(header):
            raise CSVError("Invalid or duplicate CSV columns")
        unknown = set(header) - {"Timestamp", "Vehicle_ID", *SIGNALS}
        if (
            unknown
            or "Timestamp" not in header
            or not set(SIGNALS).intersection(header)
        ):
            raise CSVError(
                "Expected leaf-csv-v1 exact columns, including Timestamp and at least one supported signal"
            )
        readings, issues, identities = [], [], set()
        invalid_cells = skipped = total = 0
        for index, fields in enumerate(reader, 1):
            total = index
            if index > settings.leaf_upload_max_rows:
                raise CSVError(
                    "CSV exceeds the row limit; no readings were analyzed", 413
                )
            if len(fields) != len(header) or any(len(v) > 128 for v in fields):
                raise CSVError("Malformed CSV row or excessive field length")
            row = dict(zip(header, fields, strict=True))
            if "Vehicle_ID" in row:
                identity = row["Vehicle_ID"].strip()
                if not identity:
                    raise CSVError(
                        "Vehicle_ID must be populated on every row when supplied"
                    )
                identities.add(identity)
                if len(identities) > 1:
                    raise CSVError("Mixed-vehicle recordings are not supported")
            timestamp = row["Timestamp"].strip()
            # Integral Unix microseconds only, 2000..2100 avoids seconds/milliseconds ambiguity.
            if (
                not timestamp.isascii()
                or not timestamp.isdecimal()
                or not 946684800000000 <= int(timestamp) < 4102444800000000
            ):
                skipped += 1
                if len(issues) < 20:
                    issues.append(
                        f"Row {index}: invalid Unix-microsecond Timestamp; row skipped"
                    )
                continue
            values = {}
            for name in SIGNALS:
                if name not in row:
                    continue
                raw = row[name].strip()
                value = None
                if raw:
                    try:
                        value = float(raw)
                        if (
                            not math.isfinite(value)
                            or abs(value) > 3.4028234663852886e38
                        ):
                            raise ValueError
                        if name in ("SOC", "SOH") and not 0 <= value <= 100:
                            raise ValueError
                        if name == "HV_Bat_Voltage" and not 0 < value <= 500:
                            raise ValueError
                        if name in ("Odometer", "kWh_Remaining") and value < 0:
                            raise ValueError
                    except ValueError:
                        value = None
                if value is None:
                    invalid_cells += 1
                    if len(issues) < 20:
                        issues.append(
                            f"Row {index}: {name} missing or invalid; not imputed"
                        )
                values[name] = value
            readings.append(
                Reading(row_id=index, timestamp_us=int(timestamp), values=values)
            )
        if not readings:
            raise CSVError("No readings with valid timestamps")
        if not any(any(v is not None for v in r.values.values()) for r in readings):
            raise CSVError("No valid telemetry measurements")
        return readings, {
            "input_rows": total,
            "valid_timestamp_rows": len(readings),
            "skipped_timestamp_rows": skipped,
            "missing_or_invalid_cells": invalid_cells,
            "columns": header,
            "issues": issues,
            "vehicle_identity": "caller_supplied_single_identifier_unverified"
            if identities
            else "single_vehicle_asserted_by_format_not_independently_verified",
            "backward_or_duplicate_timestamps": sum(
                b.timestamp_us <= a.timestamp_us for a, b in pairwise(readings)
            ),
        }
    except (csv.Error, StopIteration, OverflowError):
        raise CSVError("Malformed CSV") from None


def daily_history(readings: list[Reading]) -> list[dict]:
    days = defaultdict(list)
    for row in readings:
        if row.values.get("Odometer") is not None and row.values.get("SOH") is not None:
            days[row.timestamp_us // 86400000000].append(row)
    history = []
    for day, rows in sorted(days.items()):
        result = {
            "Timestamp": day * 86400000000,
            "Odometer": median(r.values["Odometer"] for r in rows),
            "SOH": median(r.values["SOH"] for r in rows),
        }
        # A daily mean of context preserves the estimator's daily context semantics.
        for name in (*FEATURES, "Pack_Avg_C_Temp"):
            values = [r.values[name] for r in rows if r.values.get(name) is not None]
            if values:
                result[name] = mean(values)
        history.append(result)
    return history


async def analyze(readings, quality, service, *, source_type, sample_id=None):
    def latest(name):
        candidates = [r for r in readings if r.values.get(name) is not None]
        return (
            max(candidates, key=lambda r: (r.timestamp_us, r.row_id))
            if candidates
            else None
        )

    soc, soh = latest("SOC"), latest("SOH")
    battery = BatteryOverview(
        latest_soc=soc.values["SOC"] if soc else None,
        soc_timestamp_us=soc.timestamp_us if soc else None,
        latest_soh=soh.values["SOH"] if soh else None,
        soh_timestamp_us=soh.timestamp_us if soh else None,
    )
    eligible = [
        r for r in readings if all(r.values.get(name) is not None for name in FEATURES)
    ]
    anomaly = AnomalyAnalysis(
        status="unavailable",
        reason="Each anomaly reading requires all six finite model features",
        skipped_count=len(readings),
    )
    if eligible:
        try:
            result = await service.anomaly(
                [{name: r.values[name] for name in FEATURES} for r in eligible]
            )
            predictions = [
                ScoredReading(
                    **p.model_dump(), row_id=r.row_id, timestamp_us=r.timestamp_us
                )
                for r, p in zip(eligible, result.results, strict=True)
            ]
            count = sum(p.is_unusual for p in predictions)
            anomaly = AnomalyAnalysis(
                status="completed",
                model_version=result.model_version,
                threshold=result.threshold,
                analyzed_count=len(predictions),
                skipped_count=len(readings) - len(predictions),
                unusual_count=count,
                unusual_percentage=100 * count / len(predictions),
                explanation_status=result.explanation_status,
                results=predictions,
            )
        except MLServiceError as error:
            anomaly = AnomalyAnalysis(
                status="failed", reason=str(error), skipped_count=len(readings)
            )
    health = Availability(
        status="unavailable", reason="No valid reported SOH measurement"
    )
    if soh:
        try:
            health = Availability(
                status="completed", result=await service.health(soh.values["SOH"])
            )
        except MLServiceError as error:
            health = Availability(status="failed", reason=str(error))
    history = daily_history(readings)
    rul = Availability(
        status="unavailable", reason="RUL requires Timestamp, Odometer and SOH history"
    )
    if history:
        if len(history) > 10000:
            raise CSVError("Daily RUL history exceeds the model limit", 413)
        if any(b["Odometer"] < a["Odometer"] for a, b in pairwise(history)):
            rul = Availability(
                status="unavailable",
                reason="Daily odometer decreases; consistent single-vehicle history is required",
            )
        else:
            try:
                result = await service.rul(history)
                reasons = {
                    "insufficient_history": "A projection requires at least 30 observed UTC days spanning 90 calendar days within the estimator lookback.",
                    "insufficient_odometer_variation": "There are too few distinct daily odometer values to fit a distance trend.",
                    "non_declining_trend": "The fitted SOH trend is flat or increasing, so no remaining-distance estimate is available.",
                    "no_valid_history": "The estimator found no valid SOH and odometer history.",
                    "threshold_reached": "The latest daily median SOH has already reached the configured threshold; this is not a fault diagnosis.",
                }
                rul = Availability(
                    status="insufficient_history"
                    if result["status"].startswith("insufficient")
                    else "completed",
                    reason=reasons.get(result["status"]),
                    result=result,
                )
            except MLServiceError as error:
                rul = Availability(status="failed", reason=str(error))
    source = {
        "format_version": "leaf-csv-v1",
        "sample_id": sample_id,
        "synthetic": source_type == "built_in_sample",
        "provenance": catalog()["samples"][0]["provenance"]
        if sample_id
        else "User-supplied telemetry; vehicle identity, units and provenance are not independently verified",
    }
    warnings = quality["issues"].copy()
    if quality["backward_or_duplicate_timestamps"]:
        warnings.append(
            "Source timestamps repeat or move backward; input order is preserved and graphs break at these boundaries"
        )
    return LeafAnalysis(
        source_type=source_type,
        source=source,
        recording={
            **quality,
            "reading_count": len(readings),
            "start_timestamp_us": min(r.timestamp_us for r in readings),
            "end_timestamp_us": max(r.timestamp_us for r in readings),
            "timestamp_unit": "unix_microseconds",
            "vehicle_compatibility": "Nissan Leaf schema only; cross-vehicle validity unverified",
        },
        battery=battery,
        anomaly=anomaly,
        health=health,
        rul=rul,
        telemetry=readings,
        units={k: v for k, v in UNITS.items() if k in quality["columns"]},
        warnings=warnings,
        limitations=LIMITATIONS,
    )


def sample_bytes(sample_id):
    if sample_id != SAMPLE_ID:
        raise CSVError("Sample not found", 404)
    try:
        data = SAMPLE_PATH.read_bytes()
        manifest = __import__("json").loads(
            SAMPLE_PATH.with_suffix(".json").read_text()
        )
        if hashlib.sha256(data).hexdigest() != manifest["sha256"]:
            raise ValueError
        return data
    except (OSError, ValueError, KeyError):
        raise CSVError("Sample data unavailable", 503) from None
