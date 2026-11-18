// Version-1 main-backend wire contracts. Separate from demo and saved History models.
export const kitSignals = ['coolant_temp_c', 'map_kpa', 'engine_rpm', 'speed_kmph',
  'intake_air_temp_c', 'maf_gs', 'throttle_pct', 'ambient_air_temp_c', 'pedal_d_pct', 'pedal_e_pct'] as const;
export type KitSignal = typeof kitSignals[number];
export interface KitSample {
  id: string; display_name: string; recording_id: string; recording_date: string;
  dataset: string; creator: string; source_doi: string; license: string; license_url: string;
  source_split: 'train' | 'validation' | 'test'; window_count: number; valid_pair_count: number;
  window_seconds: 10; compatible_model_version: 'kit-xgb-forecast-v1'; limitations: string[];
}
export interface KitSampleCatalog { schema_version: 1; samples: KitSample[] }
export interface KitModelMetadata {
  schema_version: 1; model_version: 'kit-xgb-forecast-v1'; assessment_type: 'novelty';
  threshold: number; label_status: 'unlabeled_dataset_not_fault_diagnosis';
}
export interface KitWindowReference {
  id: string; recording_id: string; recording_date: string; split: string; segment_id: number;
  start_seconds: number; end_seconds: number; relative_start_seconds: number;
}
export interface KitSignalDeviation { signal: KitSignal; normalized_error: number }
export interface KitPairAnalysis {
  pair_id: string; current_window: KitWindowReference; next_window: KitWindowReference;
  anomaly_score: number; threshold: number; is_novel: boolean;
  normalized_signal_errors: Record<KitSignal, number>; top_signal_deviations: KitSignalDeviation[];
}
export interface KitSummary {
  evaluated_pairs: number; novel_pairs: number; not_novel_pairs: number; novel_percentage: number;
  max_anomaly_score: number; mean_anomaly_score: number; threshold: number;
}
export interface KitFlaggedInterval {
  recording_id: string; recording_date: string; split: string; segment_id: number;
  start_seconds: number; end_seconds: number; pair_ids: string[]; peak_anomaly_score: number;
}
export interface KitScorePoint {
  pair_id: string; window: KitWindowReference; anomaly_score: number; threshold: number; is_novel: boolean;
}
export interface KitTelemetryWindow {
  window: KitWindowReference; medians: Record<KitSignal, number>;
  missing_fractions: Partial<Record<KitSignal, number>>;
}
export interface KitExplanation {
  summary: string; signal_summary: string; signal_scope: 'flagged_pairs' | 'all_evaluated_pairs';
  strongest_signal_deviations: KitSignalDeviation[]; score_definition: string;
  threshold_definition: string; signal_definition: string; measurement_definition: string; limitations: string;
}
export interface KitPreparedAnalysis {
  schema_version: 1; analysis_type: 'kit_telemetry_novelty'; model: KitModelMetadata;
  window_count: number; pair_count: number; window_seconds: 10; summary: KitSummary;
  predictions: KitPairAnalysis[]; flagged_intervals: KitFlaggedInterval[]; score_series: KitScorePoint[];
  signals: { name: KitSignal; unit: string; display_name: string }[]; telemetry: KitTelemetryWindow[];
  explanation: KitExplanation; time_basis: string; relative_time_basis: string;
  interval_definition: string; contribution_definition: string; persisted: false; limitations: string[];
}
export interface KitSampleAnalysis extends KitPreparedAnalysis { source_type: 'packaged_sample'; sample: KitSample }
export interface KitUploadedAnalysis extends KitPreparedAnalysis {
  source_type: 'uploaded_csv';
  source: {
    kind: 'uploaded_csv'; format_version: 'kit_obd_raw_v1'; preprocessing_version: 'kit-10s-window-recipe-v1';
    recording_id: string; recording_date: string; metadata_verification: 'caller_supplied_unverified';
    input_bytes: number; accepted_rows: number; missing_cells: number; discarded_incomplete_windows: number;
    backward_timestamp_jumps: number; duplicate_timestamp_rows: number;
  };
}
export type KitAnalysis = KitSampleAnalysis | KitUploadedAnalysis;
/** Native reference only: never put CSV text/base64 into component state. */
export interface KitCsvFile { uri: string; name: string; mimeType?: string; sizeBytes?: number }
export type KitSource = { kind: 'none' } | { kind: 'demo' } | { kind: 'sample'; sampleId: string }
  | { kind: 'csv'; file: KitCsvFile };
export interface AnalysisContext { uid: string; signal?: AbortSignal }
export interface AnalysisApi {
  samples: (context: AnalysisContext) => Promise<KitSampleCatalog>;
  sample: (id: string, context: AnalysisContext) => Promise<KitSampleAnalysis>;
  upload: (file: KitCsvFile, recordingDate: string, context: AnalysisContext) => Promise<KitUploadedAnalysis>;
}
