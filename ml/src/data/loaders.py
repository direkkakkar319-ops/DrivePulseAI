import pandas as pd
from pathlib import Path
from typing import Union


def load_ai4i(filepath: Union[str, Path]) -> pd.DataFrame:
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
