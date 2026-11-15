import io
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import pandas as pd

XLSX_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
XLSX_REL_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"

# File starts with a ~20-line GPL copyright preamble; the header row begins
# with "class,". Verified against the canonical train file (header at line 20).
APS_PREAMBLE_LINES = 20


def load_aps(filepath: str | Path, split: str = "train") -> pd.DataFrame:
    """
    Load the Scania APS failure dataset (heavy-truck air pressure system).

    Failure semantics: failure=1 means the specified APS component failed.
    failure=0 means failure in some OTHER component, not a healthy vehicle.
    The 170 features are anonymized counters/histogram bins with no physical
    units. vehicle_id is a row identity (APS-<split>-<row>), not a vehicle:
    the files carry no vehicle, trip, or time axis.

    Args:
        filepath: Directory holding the official CSVs, or a single CSV file.
        split: "train" or "test" when filepath is a directory. The official
            split is preserved as-is; never remix it for evaluation.

    Returns:
        pd.DataFrame: Features plus failure label, vehicle_id, and source label.
    """
    filepath = Path(filepath)
    if split not in ("train", "test"):
        raise ValueError(f"split must be 'train' or 'test', got {split!r}")
    if filepath.is_dir():
        name = "training" if split == "train" else "test"
        filepath = filepath / f"aps_failure_{name}_set.csv"
    elif not filepath.is_file():
        raise FileNotFoundError(f"File or directory not found: {filepath}")

    df = pd.read_csv(filepath, skiprows=APS_PREAMBLE_LINES, na_values=["na"])
    if "class" not in df.columns:
        raise ValueError(f"No 'class' column in {filepath}: not an APS file")
    df["failure"] = (df["class"] == "pos").astype(int)
    df["vehicle_id"] = f"APS-{split}-" + df.index.astype(str)
    df["source"] = "scania_aps"
    df.attrs.update(
        dataset_version="local_scania_aps_release",
        identity_type="row_identity_only",
        label_semantics="pos=APS component failure; neg=other component failure",
        official_split=True,
    )
    return df


# KIT recordings carry 11 columns (time + 10 signals) with units in the
# headers. Renamed positionally so header mojibake variants can't misalign
# signals; a file with != 11 columns fails loudly instead of shifting data.
KIT_COLUMNS = [
    "timestamp_raw",
    "coolant_temp_c",
    "map_kpa",
    "engine_rpm",
    "speed_kmph",
    "intake_air_temp_c",
    "maf_gs",
    "throttle_pct",
    "ambient_air_temp_c",
    "pedal_d_pct",
    "pedal_e_pct",
]


def load_kit_obd(filepath: str | Path, pattern: str = "*.csv") -> pd.DataFrame:
    """
    Load KIT Automotive OBD-II recordings (real Seat Leon trips).

    timestamp is seconds since midnight parsed from the time-of-day column;
    the date context lives in vehicle_id (KIT-<filename stem>), which is a
    recording/trip identity, not a proven independent vehicle. Small backward
    timestamp jumps and blank cells documented in the data audit are retained
    as-is for preprocessing to handle. No failure labels exist: anomaly
    detection only.

    Args:
        filepath: A single recording CSV or a directory of recordings.
        pattern: Glob pattern when loading from a directory.

    Returns:
        pd.DataFrame: Telemetry with vehicle_id, timestamp, and source label.
    """
    filepath = Path(filepath)
    files = (
        sorted(filepath.glob(pattern))
        if filepath.is_dir()
        else [filepath]
        if filepath.is_file()
        else None
    )
    if not files:
        raise FileNotFoundError(f"No KIT recordings found at {filepath}")

    dfs = []
    for f in files:
        df = pd.read_csv(f)
        if len(df.columns) != len(KIT_COLUMNS):
            raise ValueError(
                f"{f.name}: expected {len(KIT_COLUMNS)} columns, got {len(df.columns)}"
            )
        df.columns = KIT_COLUMNS
        df["timestamp"] = pd.to_timedelta(
            df["timestamp_raw"], errors="coerce"
        ).dt.total_seconds()
        df["vehicle_id"] = f"KIT-{f.stem}"
        df["source"] = "kit_obd"
        df.attrs.update(
            dataset_version="KIT-OBD-II-DOI-10.35097/1130",
            identity_type="recording_or_trip_not_verified_vehicle",
            label_semantics="no_failure_labels",
            official_split=False,
        )
        dfs = dfs + [df]
    result = pd.concat(dfs, ignore_index=True)
    result.attrs.update(dfs[0].attrs)
    return result


def load_carobd(filepath: str | Path, pattern: str = "*.csv") -> pd.DataFrame:
    """
    Load carOBD candidate recordings (provenance UNVERIFIED, see data audit).

    timestamp is engine runtime (ENGINE_RUN_TINE, spelling preserved
    upstream), not wall-clock time. vehicle_id is the recording filename
    stem (trip identity), not a verified vehicle. Short/truncated rows are
    kept with NaN, never dropped or realigned. No failure labels: anomaly
    detection exploration only, after provenance validation.

    Args:
        filepath: A single recording CSV or a directory of recordings.
        pattern: Glob pattern when loading from a directory.

    Returns:
        pd.DataFrame: Telemetry with vehicle_id, timestamp, and source label.
    """
    filepath = Path(filepath)
    files = (
        sorted(filepath.glob(pattern))
        if filepath.is_dir()
        else [filepath]
        if filepath.is_file()
        else None
    )
    if not files:
        raise FileNotFoundError(f"No carOBD recordings found at {filepath}")

    dfs = []
    for f in files:
        header = pd.read_csv(f, nrows=0).columns.tolist()
        if len(header) != 27:
            raise ValueError(f"{f.name}: expected 27 header columns, got {len(header)}")
        # usecols pins the read to the 27 named positions so the trailing
        # empty 28th field present in most rows can never shift signals.
        df = pd.read_csv(f, usecols=list(range(27)))
        df.columns = header
        rename = {
            "ENGINE_RUN_TINE ()": "timestamp",
            "ENGINE_RPM ()": "engine_rpm",
            "VEHICLE_SPEED ()": "speed_kmph",
            "THROTTLE ()": "throttle_pct",
            "ENGINE_LOAD ()": "engine_load_pct",
            "COOLANT_TEMPERATURE ()": "coolant_temp_c",
            "LONG_TERM_FUEL_TRIM_BANK_1 ()": "long_term_fuel_trim_bank_1",
            "SHORT_TERM_FUEL_TRIM_BANK_1 ()": "short_term_fuel_trim_bank_1",
        }
        df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
        for c in df.columns:
            if c not in ("vehicle_id", "source"):
                df[c] = pd.to_numeric(df[c], errors="coerce")
        df["vehicle_id"] = f"carOBD-{f.stem}"
        df["source"] = "carobd"
        df.attrs.update(
            dataset_version="unverified_local_carobd_candidate",
            identity_type="recording_or_trip_not_verified_vehicle",
            label_semantics="no_verified_failure_labels",
            official_split=False,
        )
        dfs = dfs + [df]
    result = pd.concat(dfs, ignore_index=True)
    result.attrs.update(dfs[0].attrs)
    return result


def _xlsx_column_number(cell_ref: str) -> int:
    letters = re.match(r"[A-Z]+", cell_ref).group(0)
    number = 0
    for letter in letters:
        number = number * 26 + ord(letter) - ord("A") + 1
    return number - 1


def _read_xlsx_rows(payload: bytes) -> list[dict[int, str]]:
    """Read simple Tongji feature workbooks without pickle or Excel execution."""
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = [
                "".join(item.itertext()) for item in root.findall("m:si", XLSX_NS)
            ]
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        relationships = ElementTree.fromstring(
            archive.read("xl/_rels/workbook.xml.rels")
        )
        relation_map = {
            relation.attrib["Id"]: relation.attrib["Target"]
            for relation in relationships
            if relation.attrib.get("Type", "").endswith("/worksheet")
        }
        sheet = workbook.find("m:sheets/m:sheet", XLSX_NS)
        target = relation_map[sheet.attrib[XLSX_REL_ID]].lstrip("/")
        if not target.startswith("xl/"):
            target = "xl/" + target
        root = ElementTree.fromstring(archive.read(target))
        rows: list[dict[int, str]] = []
        for row in root.findall("m:sheetData/m:row", XLSX_NS):
            values: dict[int, str] = {}
            for cell in row.findall("m:c", XLSX_NS):
                value = cell.find("m:v", XLSX_NS)
                text = "" if value is None else value.text or ""
                if cell.attrib.get("t") == "s" and text.isdigit():
                    text = shared[int(text)]
                values[_xlsx_column_number(cell.attrib["r"])] = text
            if values:
                rows.append(values)
        return rows


def _load_tongji_workbook(name: str, payload: bytes) -> pd.DataFrame:
    rows = _read_xlsx_rows(payload)
    if not rows:
        return pd.DataFrame()
    header = rows[0]
    columns = [header[index] for index in sorted(header)]
    records = [
        {header[index]: row.get(index, "") for index in sorted(header)}
        for row in rows[1:]
    ]
    result = pd.DataFrame.from_records(records, columns=columns)
    for column in result.columns:
        if column != "car_identifier":
            result[column] = pd.to_numeric(result[column], errors="coerce")
    path = Path(name)
    result["source_file"] = path.name
    result["source_split"] = "test" if "data_test" in path.parts else "train"
    result["feature_kind"] = "slow" if "_slow_" in path.name else "fast"
    if "car_identifier" in result:
        identifier = result["car_identifier"].astype("string")
    else:
        identifier = pd.Series(pd.NA, index=result.index, dtype="string")
    result["asset_id"] = identifier.fillna(path.stem)
    result["asset_id_type"] = identifier.notna().map(
        {True: "car_identifier", False: "file_stem"}
    )
    return result


def _assign_tongji_vehicle_splits(
    result: pd.DataFrame,
) -> tuple[pd.DataFrame, set[str]]:
    """Move every asset observed in the official test directory to evaluation."""
    evaluation_ids = set(
        result.loc[result["source_split"] == "test", "asset_id"].dropna().astype(str)
    )
    result = result.copy()
    result["split"] = (
        result["asset_id"]
        .astype(str)
        .map(lambda asset_id: "test" if asset_id in evaluation_ids else "train")
    )
    return result, evaluation_ids


def load_tongji_rest(
    filepath: str | Path,
    split: str | None = None,
    kind: str | None = None,
) -> pd.DataFrame:
    """Load Tongji features with a vehicle-disjoint train/evaluation partition.

    Any vehicle appearing in the official test directory is assigned wholly to
    ``test``. Thus all records for GE16 and HQ05, including their official-train
    files, remain in evaluation. ``source_split`` retains the release directory.
    """
    if split not in (None, "train", "test"):
        raise ValueError("split must be None, 'train', or 'test'")
    if kind not in (None, "fast", "slow"):
        raise ValueError("kind must be None, 'fast', or 'slow'")
    source = Path(filepath)
    if not source.exists():
        raise FileNotFoundError(f"Tongji release not found: {source}")
    records: list[pd.DataFrame] = []
    if source.is_dir():
        files = sorted(source.rglob("*.xlsx"))
        for file in files:
            name = file.as_posix()
            records.append(_load_tongji_workbook(name, file.read_bytes()))
    elif source.suffix.lower() == ".zip":
        with zipfile.ZipFile(source) as archive:
            names = sorted(
                name for name in archive.namelist() if name.endswith(".xlsx")
            )
            for name in names:
                records.append(_load_tongji_workbook(name, archive.read(name)))
    else:
        raise ValueError(f"Expected a directory or .zip archive: {source}")
    records = [record for record in records if not record.empty]
    if not records:
        raise FileNotFoundError(
            f"No Tongji XLSX files matched split={split!r}, kind={kind!r}"
        )
    result = pd.concat(records, ignore_index=True, sort=False)
    result, evaluation_ids = _assign_tongji_vehicle_splits(result)
    if split:
        result = result.loc[result["split"] == split].reset_index(drop=True)
    if kind:
        result = result.loc[result["feature_kind"] == kind].reset_index(drop=True)
    if result.empty:
        raise FileNotFoundError(
            f"No Tongji XLSX rows matched vehicle-disjoint split={split!r}, kind={kind!r}"
        )
    result.attrs.update(
        dataset_version="zenodo-16868546",
        license="CC BY 4.0",
        identity_type="car_identifier_or_source_file",
        label_semantics="soh/capacity health proxies; no documented RUL/TTE",
        official_split=False,
        split_protocol="vehicle-disjoint; any asset_id present in official test is held out",
        evaluation_asset_ids=sorted(evaluation_ids),
        source_split_column="source_split",
    )
    return result
