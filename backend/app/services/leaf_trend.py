"""Prepare a complete observation history; never batch independent trend windows."""

from collections import defaultdict

from app.schemas.leaf_analysis import Reading, SignalAvailability, TrendAnalysis
from app.services.ml_errors import MLServiceError

PACKS = ("Pack_1_C_Temp", "Pack_2_C_Temp", "Pack_4_C_Temp")
TREND_FIELDS = (*PACKS, "Pack_Avg_C_Temp", "Odometer", "SOH")
LIMITATIONS = [
    "Rolling Z-score is a statistical drift detector, separate from Isolation Forest point anomalies and not a mechanical fault diagnosis.",
    "The result assesses the latest observed daily point; it is not a time series of all historical alerts.",
    "Baseline windows and persistence count observed daily points, not necessarily consecutive calendar days. Missing days are not interpolated.",
    "Temperatures are daily means; pack spread compares daily sensor means, not simultaneous raw readings.",
    "SOH decline uses positive odometer changes greater than 0.01 km; negative SOH decline is clipped to zero by the detector.",
    "Severity comes from the detector. Rounded returned Z-scores must not be used to recalculate severity.",
]


def prepare_trend(readings: list[Reading]) -> tuple[list[dict], TrendAnalysis]:
    by_day = defaultdict(list)
    for row in readings:
        if any(row.values.get(name) is not None for name in TREND_FIELDS):
            by_day[row.timestamp_us // 86400000000].append(row)
    eligible = [
        row
        for row in readings
        if row.timestamp_us // 86400000000 in by_day
        and any(row.values.get(name) is not None for name in TREND_FIELDS)
    ]
    fields = {
        name
        for row in eligible
        for name in TREND_FIELDS
        if row.values.get(name) is not None
    }
    pack_coverage = bool(by_day) and all(
        sum(any(row.values.get(name) is not None for row in rows) for name in PACKS)
        >= 2
        for rows in by_day.values()
    )
    availability = {
        "pack_temp_spread": SignalAvailability(
            status="available" if pack_coverage else "unavailable",
            reason=None
            if pack_coverage
            else "At least two measured pack sensors are required on every supplied trend day; incomplete sensor days cannot establish a zero spread.",
        ),
        "pack_temp_rise": SignalAvailability(
            status="unavailable",
            reason="Ambient_C_Temp is not accepted by leaf-csv-v1 until its ambiguous source units have an explicit verified input contract.",
        ),
        "pack_avg_temp": SignalAvailability(
            status="available" if "Pack_Avg_C_Temp" in fields else "unavailable",
            reason=None
            if "Pack_Avg_C_Temp" in fields
            else "No supplied Pack_Avg_C_Temp measurement; no average is invented.",
        ),
        "soh_decline_rate_per_kkm": SignalAvailability(
            status="available" if {"SOH", "Odometer"} <= fields else "unavailable",
            reason=None
            if {"SOH", "Odometer"} <= fields
            else "Reported SOH and odometer history are required.",
        ),
    }
    # Conservatively omit incomplete sensor histories rather than let pandas'
    # skip-na max/min convert a one-sensor daily spread into a measured zero.
    used_fields = fields - (set(PACKS) if not pack_coverage else set())
    observations = [
        {
            "Timestamp": row.timestamp_us,
            **{
                name: row.values[name]
                for name in TREND_FIELDS
                if name in used_fields and row.values.get(name) is not None
            },
        }
        for row in eligible
    ]
    timestamps = [row["Timestamp"] for row in observations]
    metadata = TrendAnalysis(
        status="unavailable",
        reason="No supported trend signal has the required measurements",
        prepared_readings=len(observations),
        skipped_readings=len(readings) - len(observations),
        observed_days=len(by_day),
        start_timestamp_us=min(timestamps) if timestamps else None,
        end_timestamp_us=max(timestamps) if timestamps else None,
        source_fields=sorted(used_fields),
        signal_availability=availability,
        warnings=[
            "Daily sensor coverage is conservative: pack inputs are excluded if any supplied trend day has fewer than two valid pack sensors."
        ]
        if fields.intersection(PACKS) and not pack_coverage
        else [],
        limitations=LIMITATIONS,
    )
    return observations, metadata


async def analyze_trend(readings, service):
    observations, metadata = prepare_trend(readings)
    if not observations or not any(
        v.status == "available" for v in metadata.signal_availability.values()
    ):
        return metadata
    try:
        result = await service.trend(observations)
        metadata.result = result
        metadata.analyzed_readings = len(observations)
        metadata.reason = None
        if result.status == "insufficient_history":
            metadata.status = "insufficient_history"
            metadata.reason = f"At least {result.min_days_required} observed UTC days are required; {result.days_available} available. Individual signal baselines can require more measurements."
        elif result.signal_details and all(
            v.status == "insufficient_baseline_points"
            for v in result.signal_details.values()
        ):
            metadata.status = "insufficient_history"
            metadata.reason = "No signal has enough finite prior daily measurements for its rolling baseline."
        elif not result.signal_details or all(
            v.status == "non_finite_current_reading"
            for v in result.signal_details.values()
        ):
            metadata.status = "unavailable"
            metadata.reason = "No latest daily signal has a usable measurement."
        else:
            metadata.status = "completed"
    except MLServiceError as error:
        metadata.status = "failed"
        metadata.reason = str(error)
    return metadata
