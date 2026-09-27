from pathlib import Path

import pandas as pd


def load_ai4i(filepath: str | Path) -> pd.DataFrame:
    """
    Load the AI4I Predictive Maintenance dataset and map to automotive fields.

    Args:
        filepath: Path to the predictive_maintenance.csv file.

    Returns:
        pd.DataFrame: Dataframe with standard automotive column names and source label.
    """
    df = pd.read_csv(filepath)

    mapping = {
        "UDI": "vehicle_id",
        "Rotational speed [rpm]": "engine_rpm",
        "Torque [Nm]": "engine_load_pct",
        "Process temperature [K]": "coolant_temp_c",
        "Air temperature [K]": "intake_air_temp_c",
        "Tool wear [min]": "vibration",
        "Machine failure": "failure",
    }

    rename_dict = {k: v for k, v in mapping.items() if k in df.columns}
    df = df.rename(columns=rename_dict)

    # Kelvin to Celsius
    if "coolant_temp_c" in df.columns:
        df["coolant_temp_c"] = df["coolant_temp_c"] - 273.15
    if "intake_air_temp_c" in df.columns:
        df["intake_air_temp_c"] = df["intake_air_temp_c"] - 273.15

    # Scale engine_load_pct to 0 to 100 (assuming torque max is around 80 Nm in AI4I)
    if "engine_load_pct" in df.columns:
        df["engine_load_pct"] = (
            df["engine_load_pct"] / df["engine_load_pct"].max()
        ) * 100

    # Add standard fields
    df["source"] = "ai4i"
    if "vehicle_id" not in df.columns:
        df["vehicle_id"] = "AI4I-" + df.index.astype(str)
    else:
        df["vehicle_id"] = "AI4I-" + df["vehicle_id"].astype(str)

    return df


def load_simulated(
    filepath: str | Path,
    pattern: str = "*.csv",
) -> pd.DataFrame:
    """
    Load simulated telemetry data (CSV or JSONL), either from a single file or a directory.

    Args:
        filepath: Path to the simulated data file or directory containing files.
        pattern: Glob pattern when loading from a directory (default: "*.csv").

    Returns:
        pd.DataFrame: Dataframe containing the simulated telemetry with unified column names and source label.
    """
    filepath = Path(filepath)

    def _load_single(f: Path) -> pd.DataFrame:
        if f.suffix == ".jsonl":
            sub_df = pd.read_json(f, lines=True)
        else:
            sub_df = pd.read_csv(f)
        if "vehicle_id" not in sub_df.columns:
            sub_df["vehicle_id"] = f"SIM-{f.stem}"
        return sub_df

    if filepath.is_dir():
        files = sorted(filepath.glob(pattern))
        if not files and pattern == "*.csv":
            files = sorted(filepath.glob("*.jsonl"))
        if not files:
            raise FileNotFoundError(f"No matching files found in directory: {filepath}")
        dfs = [_load_single(f) for f in files]
        df = pd.concat(dfs, ignore_index=True)
    elif filepath.is_file():
        df = _load_single(filepath)
    else:
        raise FileNotFoundError(f"File or directory not found: {filepath}")

    mapping = {
        "ENGINE_RUN_TINE ()": "timestamp",
        "ENGINE_RPM ()": "engine_rpm",
        "VEHICLE_SPEED ()": "speed_kmph",
        "ENGINE_LOAD ()": "engine_load_pct",
        "COOLANT_TEMPERATURE ()": "coolant_temp_c",
        "INTAKE_AIR_TEMP ()": "intake_air_temp_c",
        "CONTROL_MODULE_VOLTAGE ()": "battery_voltage",
        "THROTTLE ()": "throttle_pct",
    }
    rename_dict = {k: v for k, v in mapping.items() if k in df.columns}
    df = df.rename(columns=rename_dict)

    df["source"] = "simulated"
    return df


def load_cmapss(filepath: str | Path, subset: str = "FD001") -> pd.DataFrame:
    """
    Load the C-MAPSS dataset (turbofan engine degradation) and map to automotive fields.
    Adds a Remaining Useful Life (RUL) column for regression tasks.

    Args:
        filepath: Path to the directory containing C-MAPSS text files or the file itself.
        subset: The subset to load, e.g. "FD001" (default). If "all", loads all FD001-FD004.

    Returns:
        pd.DataFrame: Dataframe with standard automotive column names, RUL, and source label.
    """
    filepath = Path(filepath)
    columns = ["unit_number", "time_in_cycles", "setting_1", "setting_2", "setting_3"]
    columns += [f"sensor_{i}" for i in range(1, 22)]

    def _load_single_file(file_path: Path, subset_name: str) -> pd.DataFrame:
        df_sub = pd.read_csv(file_path, sep=r"\s+", header=None, names=columns)
        df_sub["subset"] = subset_name
        # Unit numbers are per subset, so make them globally unique
        df_sub["unit_number"] = subset_name + "_" + df_sub["unit_number"].astype(str)
        return df_sub

    dfs = []
    if filepath.is_dir():
        if subset == "all":
            for i in range(1, 5):
                sub_name = f"FD00{i}"
                file_path = filepath / f"train_{sub_name}.txt"
                if file_path.exists():
                    dfs.append(_load_single_file(file_path, sub_name))
        else:
            file_path = filepath / f"train_{subset}.txt"
            if file_path.exists():
                dfs.append(_load_single_file(file_path, subset))
    else:
        dfs.append(_load_single_file(filepath, subset))

    if not dfs:
        raise FileNotFoundError(
            f"No C-MAPSS files found at {filepath} for subset {subset}"
        )

    df = pd.concat(dfs, ignore_index=True)

    # Calculate RUL (Remaining Useful Life)
    rul = pd.DataFrame(df.groupby("unit_number")["time_in_cycles"].max()).reset_index()
    rul.columns = ["unit_number", "max_cycles"]
    df = df.merge(rul, on="unit_number", how="left")
    df["rul"] = df["max_cycles"] - df["time_in_cycles"]
    df.drop("max_cycles", axis=1, inplace=True)

    mapping = {
        "unit_number": "vehicle_id",
        "time_in_cycles": "timestamp",
        "sensor_2": "coolant_temp_c",
        "sensor_3": "intake_air_temp_c",
        "sensor_4": "battery_voltage",
        "sensor_11": "engine_rpm",
        "sensor_15": "vibration",
    }

    rename_dict = {k: v for k, v in mapping.items() if k in df.columns}
    df = df.rename(columns=rename_dict)

    df["source"] = "cmapss"

    if "vehicle_id" in df.columns:
        df["vehicle_id"] = "CMAPSS-" + df["vehicle_id"].astype(str)

    return df
