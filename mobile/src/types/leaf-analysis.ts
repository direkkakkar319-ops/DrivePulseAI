export const leafFeatures = ['HV_Bat_Voltage', 'Pack_1_C_Temp', 'SOC', 'HV_Bat_Current_2', 'Pack_2_C_Temp', 'Pack_4_C_Temp'] as const;
export interface LeafSample { id: string; display_name: string; provenance: string; synthetic: boolean; format_version: 'leaf-csv-v1'; limitations: string[] }
export interface LeafCatalog { schema_version: 1; samples: LeafSample[] }
export interface LeafCsvFile { uri: string; name: string; mimeType?: string; sizeBytes?: number }
export type LeafSource = { kind: 'none' } | { kind: 'demo' } | { kind: 'sample'; sampleId: string } | { kind: 'csv'; file: LeafCsvFile };
export interface LeafContext { uid: string; signal?: AbortSignal }
export interface LeafContribution { rank: number; feature: string; measured_value: number; shap_value: number; direction: 'toward_anomaly' | 'toward_typical' }
export interface LeafExplanation { method: 'shap_permutation'; output: string; baseline_score: number; contributions: LeafContribution[]; interpretation: string }
export interface LeafReading { row_id: number; timestamp_us: number; values: Record<string, number | null> }
export interface LeafPrediction { row_id: number; timestamp_us: number; anomaly_score: number; is_unusual: boolean; explanation: LeafExplanation | null }
export interface RulConfidenceInterval {
  level_pct: number; rul_km_p10: number; rul_km_p50: number; rul_km_p90: number;
  estimated_days_p10?: number | null; estimated_days_p50?: number | null; estimated_days_p90?: number | null;
  bootstrap_iterations_valid: number; interpretation?: string | null;
}
export interface RulResult extends Record<string, unknown> {
  model_version: 'nissan-leaf-soh-theilsen-v1'; status: string; rul_km: number | null;
  rul_km_p10?: number | null; rul_km_p50?: number | null; rul_km_p90?: number | null;
  estimated_days_to_threshold_p10?: number | null; estimated_days_to_threshold_p50?: number | null; estimated_days_to_threshold_p90?: number | null;
  confidence_interval?: RulConfidenceInterval | null;
}
export interface Capability { status: 'completed' | 'unavailable' | 'insufficient_history' | 'failed'; reason: string | null; result: Record<string, unknown> | null }
export interface LeafAnalysis {
  schema_version: 1; analysis_type: 'nissan_leaf_telemetry'; source_type: 'built_in_sample' | 'uploaded_csv';
  source: { format_version: 'leaf-csv-v1'; sample_id: string | null; synthetic: boolean; provenance: string };
  recording: { input_rows: number; valid_timestamp_rows: number; skipped_timestamp_rows: number; missing_or_invalid_cells: number; columns: string[]; issues: string[]; vehicle_identity: string; backward_or_duplicate_timestamps: number; reading_count: number; start_timestamp_us: number; end_timestamp_us: number; timestamp_unit: 'unix_microseconds'; vehicle_compatibility: string };
  battery: { latest_soc: number | null; soc_timestamp_us: number | null; latest_soh: number | null; soh_timestamp_us: number | null; estimated_range_km: null; range_status: 'unavailable'; range_reason: string };
  anomaly: { status: 'completed' | 'unavailable' | 'failed'; reason: string | null; model_version: string | null; threshold: number | null; score_direction: 'lower_is_more_unusual'; analyzed_count: number; skipped_count: number; unusual_count: number; unusual_percentage: number; explanation_status: string | null; results: LeafPrediction[] };
  health: Capability; rul: Omit<Capability, 'result'> & { result: RulResult | null }; telemetry: LeafReading[]; units: Record<string, string>; warnings: string[]; limitations: string[]; persisted: false;
}
export interface LeafApi {
  samples: (context: LeafContext) => Promise<LeafCatalog>;
  sample: (id: string, context: LeafContext) => Promise<LeafAnalysis>;
  upload: (file: LeafCsvFile, context: LeafContext) => Promise<LeafAnalysis>;
}
