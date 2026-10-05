from pathlib import Path

import pandas as pd

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
                f"{f.name}: expected {len(KIT_COLUMNS)} columns, "
                f"got {len(df.columns)}"
            )
        df.columns = KIT_COLUMNS
        df["timestamp"] = pd.to_timedelta(
            df["timestamp_raw"], errors="coerce"
        ).dt.total_seconds()
        df["vehicle_id"] = f"KIT-{f.stem}"
        df["source"] = "kit_obd"
        dfs = dfs + [df]
    return pd.concat(dfs, ignore_index=True)


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
            raise ValueError(
                f"{f.name}: expected 27 header columns, got {len(header)}"
            )
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
        dfs = dfs + [df]
    return pd.concat(dfs, ignore_index=True)
