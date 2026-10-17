"""Extract the source XLSX using the standard library and map documented aliases."""

from __future__ import annotations

import csv
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def workbook_rows(path: Path) -> list[dict]:
    rows = []
    with zipfile.ZipFile(path) as z:
        strings = [
            "".join(si.itertext())
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS)
        ]
        for row in ET.fromstring(z.read("xl/worksheets/sheet1.xml")).findall(
            ".//m:row", NS
        ):
            cells = {}
            for c in row.findall("m:c", NS):
                v = c.find("m:v", NS)
                if v is not None:
                    cells[re.sub(r"\d", "", c.get("r"))] = (
                        strings[int(v.text)] if c.get("t") == "s" else v.text
                    )
            if "A" in cells:
                rows.append(
                    {
                        "excel_row": int(row.get("r")),
                        "variable": cells["A"],
                        "unit": cells.get("F", "Unknown"),
                        "description": cells.get("H", "Unknown"),
                        "ecu": cells.get("G", "Unknown"),
                        "sampling": "; ".join(
                            f"{label}: {cells[key]}"
                            for key, label in [
                                ("B", "250ms"),
                                ("C", "1s"),
                                ("D", "10s"),
                                ("E", "100s"),
                            ]
                            if key in cells
                        )
                        or "Unknown",
                    }
                )
    return rows


def definitions(base: Path) -> dict:
    rows = workbook_rows(base / "metadata/Nissan_Leaf_Model2018_Data_Description.xlsx")
    with (base / "metadata/parameter_dictionary_extracted.csv").open(
        "w", newline=""
    ) as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    out = {
        r["variable"]: dict(r, provenance=f"Workbook row {r['excel_row']}")
        for r in rows
    }
    for name, alias in {
        "AHr": "Ahr",
        "Plug_State": "PlugState",
        "Pack_1_C_Temp": "Packs Temperature",
        "Pack_2_C_Temp": "Packs Temperature",
        "Pack_3_C_Temp": "Packs Temperature",
        "Pack_4_C_Temp": "Packs Temperature",
    }.items():
        out[name] = dict(out[alias], provenance=f"Workbook alias mapping to {alias}")
    combo = out["AC_Pwr_250W\n+\nAC_Compressor_Air_pressure"]
    out["AC_Pwr_250W"] = dict(
        combo, unit="W", provenance="Workbook combined AC power/pressure entry"
    )
    out["AC_Compressor_Air_pressure"] = dict(
        combo, unit="MPa", provenance="Workbook combined AC power/pressure entry"
    )
    for name in ["Brake", "Acc_Pedal", "Insulation"]:
        out[name]["unit"] = "Unknown"
    out["Ambient_C_Temp"]["unit"] = (
        "Unknown: workbook unit says °C; description says Fahrenheit"
    )
    out["Horsepower"] = dict(
        out["Horse power"],
        unit="Unknown: formula gives 1.341 × kW",
        description="Derived from battery voltage × current, not a measured mechanical output",
        provenance="Workbook indirect formula; observed formula checked separately",
    )
    out["Instant_kW"] = dict(
        out["Current kW/Charging \nOr\nPower/Battery Power (kW)"],
        unit="kW",
        description="Battery electrical power from voltage × current / 1000",
        provenance="Workbook indirect formula; alias inferred and numerically checked",
    )
    return out


CATEGORICAL = {
    "Power_SW",
    "Gear",
    "Rain_level",
    "Front_wiper_level",
    "Rear_wiper_level",
    "Front_washer",
    "Rear_washer",
    "Position_lights",
    "Headlights",
    "Anti_fog_lights",
    "HighBeam",
    "Plug_State",
    "Charge_Mode",
    "AC",
    "RearHeater",
    "ECO",
    "ePedal",
    "Right_Arrow",
    "Left_Arrow",
    "FanSpeed",
}
IDS = {"", "Unnamed: 0", "Unnamed: 0.1", "index", "id", "Driver_ID", "Trip"}
TIMES = {"Timestamp", "DateTime", "Timestamp_Object"}


def role(column: str) -> str:
    if column in TIMES:
        return "timestamp"
    if column in IDS:
        return "identifier_or_export_index"
    if column in CATEGORICAL:
        return "categorical_status"
    if column.startswith("accu_") or column in {
        "Day sin",
        "Day cos",
        "Season sin",
        "Season cos",
        "Year sin",
        "Year cos",
        "Odometer_diff",
        "kWh_Remaining",
        "Pack_Avg_C_Temp",
        "Horsepower",
        "Instant_kW",
    }:
        return "derived_numeric"
    return "numeric_measurement_or_undocumented"
