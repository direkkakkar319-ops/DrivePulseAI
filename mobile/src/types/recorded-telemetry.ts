// JSON contracts for recorded telemetry and saved scores, shared with the future replay API.
export interface RecordedVehicle { description: string; recording_source: string }
export interface AnomalyScore { score_samples: number | null; unusual: boolean | null }
export interface TelemetrySample extends AnomalyScore {
  source_row: number;
  original_timestamp_utc: string;
  playback_offset_ms: number;
  voltage_v: number | null;
  temperature_c: number | null;
  soc_percent: number | null;
  quality_flags: number;
}
export interface PersistentInterval {
  interval_id: string;
  start_source_row: number;
  end_source_row: number;
  start_utc: string;
  end_utc: string;
  duration_seconds: number;
  row_count: number;
  score_min: number;
  score_max: number;
}
export interface ReplayClipMetadata {
  schema_version: 1;
  clip_id: string;
  title: string;
  source_dataset: string;
  vehicle: RecordedVehicle;
  preparation_run_id: string;
  experiment_id: string;
  trip_id: number;
  split: 'train' | 'validation' | 'test';
  segment_id: number;
  recorded_start_utc: string;
  recorded_end_utc: string;
  recorded_duration_ms: number;
  sample_count: number;
  threshold: number;
  provenance: { source_file: string; source_sha256: string; artifact_sha256: Record<string, string> };
}
export interface ReplayClip extends ReplayClipMetadata {
  samples: TelemetrySample[];
  persistent_intervals: PersistentInterval[];
}
export interface InsightSummary { clip_id: string; trip_id: number; interval: PersistentInterval }
export type ApiState<T> = { status: 'loading' } | { status: 'empty' } |
  { status: 'error'; message: string } | { status: 'ready'; data: T };
export interface ReplayState { status: 'paused' | 'playing' | 'ended'; index: number }
