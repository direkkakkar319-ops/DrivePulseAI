# Battery-only artifact schemas

Purpose: document feature/metadata separation and temporal index fields.

## features_test.parquet

```text
HV_Bat_Voltage: float
Pack_1_C_Temp: float
SOC: float
-- schema metadata --
pandas: '{"index_columns": [], "column_indexes": [], "columns": [{"name":' + 456
```

## features_train.parquet

```text
HV_Bat_Voltage: float
Pack_1_C_Temp: float
SOC: float
-- schema metadata --
pandas: '{"index_columns": [], "column_indexes": [], "columns": [{"name":' + 456
```

## features_validation.parquet

```text
HV_Bat_Voltage: float
Pack_1_C_Temp: float
SOC: float
-- schema metadata --
pandas: '{"index_columns": [], "column_indexes": [], "columns": [{"name":' + 456
```

## metadata_test.parquet

```text
source_row: int64
index: int64
Timestamp: int64
Trip: double
split: string
segment_id: int64
quality_flags: uint32
battery_blocking_flags: uint32
drivetrain_unavailable_suspected: bool
quality_status: string
source_dataset: string
source_file: string
-- schema metadata --
pandas: '{"index_columns": [], "column_indexes": [], "columns": [{"name":' + 1573
```

## metadata_train.parquet

```text
source_row: int64
index: int64
Timestamp: int64
Trip: double
split: string
segment_id: int64
quality_flags: uint32
battery_blocking_flags: uint32
drivetrain_unavailable_suspected: bool
quality_status: string
source_dataset: string
source_file: string
-- schema metadata --
pandas: '{"index_columns": [], "column_indexes": [], "columns": [{"name":' + 1573
```

## metadata_validation.parquet

```text
source_row: int64
index: int64
Timestamp: int64
Trip: double
split: string
segment_id: int64
quality_flags: uint32
battery_blocking_flags: uint32
drivetrain_unavailable_suspected: bool
quality_status: string
source_dataset: string
source_file: string
-- schema metadata --
pandas: '{"index_columns": [], "column_indexes": [], "columns": [{"name":' + 1573
```

## row_ledger.parquet

```text
index: int64
Timestamp: int64
Speed: double
Odometer: double
RPM: double
SOC: double
SOH: double
Torque: double
Motor_Temp: double
TP_FR: double
TP_FL: double
TP_RR: double
TP_RL: double
HV_Bat_Voltage: double
Brake: double
Acc_Pedal: double
ECO: double
ePedal: double
HV_Bat_Current_2: double
Ambient_C_Temp: double
Pack_1_C_Temp: double
Pack_2_C_Temp: double
Pack_4_C_Temp: double
Pack_Avg_C_Temp: double
Instant_kW: double
Trip: double
source_row: int64
quality_flags: uint32
quality_eligible: bool
battery_blocking_flags: uint32
drivetrain_unavailable_suspected: bool
segment_in_trip: int32
operating_context: string
segment_id: int64
split: string
cross_split_repeat: bool
export_eligible: bool
-- schema metadata --
pandas: '{"index_columns": [], "column_indexes": [], "columns": [{"name":' + 4540
```

## temperature_test.parquet

```text
Trip: int64
segment_id: int64
split: string
input_start_row: int64
anchor_row: int64
target_row: int64
input_start_us: int64
anchor_us: int64
target_us: int64
input_rows: int64
target_temperature_c: double
temperature_change_c: double
-- schema metadata --
pandas: '{"index_columns": [], "column_indexes": [], "columns": [{"name":' + 1540
```

## temperature_train.parquet

```text
Trip: int64
segment_id: int64
split: string
input_start_row: int64
anchor_row: int64
target_row: int64
input_start_us: int64
anchor_us: int64
target_us: int64
input_rows: int64
target_temperature_c: double
temperature_change_c: double
-- schema metadata --
pandas: '{"index_columns": [], "column_indexes": [], "columns": [{"name":' + 1540
```

## temperature_validation.parquet

```text
Trip: int64
segment_id: int64
split: string
input_start_row: int64
anchor_row: int64
target_row: int64
input_start_us: int64
anchor_us: int64
target_us: int64
input_rows: int64
target_temperature_c: double
temperature_change_c: double
-- schema metadata --
pandas: '{"index_columns": [], "column_indexes": [], "columns": [{"name":' + 1540
```
