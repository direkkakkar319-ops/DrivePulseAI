// Presentation contracts; no inference, file contents, account identity, or telemetry providers.
export interface AnalysisResult {
  id: string;
  title: string;
  value: string;
  sourceLabel: string;
  explanation: string;
}

export interface SampleTelemetry {
  id: string;
  label: string;
  value: number;
  unit: string;
  source: 'simulated';
}

/** Metadata only. A future picker must not read/copy entire CSV contents here. */
export interface CsvFileMetadata {
  name: string;
  sizeBytes?: number;
  mimeType?: string;
}
export type PickCsv = () => Promise<CsvFileMetadata | null>;
export type InsightsSource = { kind: 'none' } | { kind: 'demo' } | { kind: 'csv'; file: CsvFileMetadata };
