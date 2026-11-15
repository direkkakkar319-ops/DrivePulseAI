"""Export only the two reviewed clips from saved results; never load or run a model."""
import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT = '0c777345c64dfeba'
PREPARATION = '1d6fc5b045ee25d0'
MODEL = ROOT / 'ml/artifacts/nissan_leaf_2018/isolation_forest' / EXPERIMENT
PREP = ROOT / 'ml/artifacts/nissan_leaf_2018/preparation' / PREPARATION


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def utc(value):
    return pd.to_datetime(value, unit='us', utc=True).isoformat().replace('+00:00', 'Z')


def main():
    protocol = json.loads((MODEL / 'frozen_protocol.json').read_text())
    scores = pd.read_parquet(MODEL / 'scores_validation.parquet')
    intervals = pd.read_parquet(MODEL / 'intervals_validation.parquet')
    metadata = pd.read_parquet(PREP / 'metadata_validation.parquet')
    ledger = pd.read_parquet(PREP / 'row_ledger.parquet', columns=[
        'source_row', 'Timestamp', 'Trip', 'HV_Bat_Voltage', 'Pack_1_C_Temp', 'SOC'])
    hashes = {str(p.relative_to(ROOT)): digest(p) for p in [
        MODEL / 'scores_validation.parquet', MODEL / 'intervals_validation.parquet',
        MODEL / 'frozen_protocol.json', PREP / 'metadata_validation.parquet']}
    result = []
    for clip_id, title, trip, lo, hi in [
        ('leaf-typical', 'Typical telemetry', 153, 1637821, 1638031),
        ('leaf-unusual', 'Unusual pattern', 167, 1759260, 1759464),
    ]:
        data = scores[scores.source_row.between(lo, hi)].sort_values('source_row')
        assert data.source_row.tolist() == list(range(lo, hi + 1))
        assert data.Trip.eq(trip).all() and data.split.eq('validation').all()
        assert data.segment_id.nunique() == 1 and data.quality_flags.eq(0).all()
        assert data.Timestamp.diff().dropna().between(1, 1_000_000).all()
        for other, columns in [(metadata, ['Timestamp', 'Trip', 'segment_id', 'quality_flags']),
                               (ledger, ['Timestamp', 'Trip', 'HV_Bat_Voltage', 'Pack_1_C_Temp', 'SOC'])]:
            joined = data.merge(other, on='source_row', suffixes=('', '_check'), validate='one_to_one')
            assert len(joined) == len(data)
            assert all(joined[c].equals(joined[c + '_check']) for c in columns)
        start, end = int(data.Timestamp.iloc[0]), int(data.Timestamp.iloc[-1])
        persistent = intervals[(intervals.Trip == trip) & intervals.persistent &
                               (intervals.end_row >= lo) & (intervals.start_row <= hi)]
        assert ((persistent.start_row >= lo) & (persistent.end_row <= hi)).all()
        samples = [{
            'source_row': int(r.source_row), 'original_timestamp_utc': utc(r.Timestamp),
            'playback_offset_ms': (int(r.Timestamp) - start) / 1000,
            'voltage_v': r.HV_Bat_Voltage, 'temperature_c': r.Pack_1_C_Temp,
            'soc_percent': r.SOC, 'score_samples': r.score_samples,
            'unusual': bool(r.score_samples < protocol['threshold']), 'quality_flags': int(r.quality_flags),
        } for r in data.itertuples()]
        events = [{
            'interval_id': f'{clip_id}-{int(r.start_row)}', 'start_source_row': int(r.start_row),
            'end_source_row': int(r.end_row), 'start_utc': utc(r.start_us), 'end_utc': utc(r.end_us),
            'duration_seconds': r.duration_seconds, 'row_count': int(r.row_count),
            'score_min': r.score_min, 'score_max': r.score_max,
        } for r in persistent.itertuples()]
        result.append({
            'schema_version': 1, 'clip_id': clip_id, 'title': title,
            'source_dataset': 'Dataset_NissanLeaf-2021_2022.csv',
            'vehicle': {'description': '2018 Nissan Leaf', 'recording_source': 'Macao Polytechnic University research dataset'},
            'preparation_run_id': PREPARATION, 'experiment_id': EXPERIMENT,
            'trip_id': trip, 'split': 'validation', 'segment_id': int(data.segment_id.iloc[0]),
            'recorded_start_utc': utc(start), 'recorded_end_utc': utc(end),
            'recorded_duration_ms': (end - start) / 1000, 'sample_count': len(samples),
            'threshold': protocol['threshold'], 'samples': samples, 'persistent_intervals': events,
            'provenance': {'source_file': data.source_file.iloc[0],
                           'source_sha256': protocol['identity']['input_hashes'][data.source_file.iloc[0]],
                           'artifact_sha256': hashes},
        })
    target = ROOT / 'mobile/src/demo/recorded/clips.json'
    target.write_text(json.dumps(result, separators=(',', ':'), allow_nan=False) + '\n')
    print(f'Exported {sum(c["sample_count"] for c in result)} source-aligned observations; {target.stat().st_size} bytes')


if __name__ == '__main__':
    main()
