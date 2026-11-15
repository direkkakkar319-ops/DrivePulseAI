// Future history presentation models, not a backend API schema or an inference contract.
export interface AnalysisDataSource {
  kind: 'csv-upload' | 'recorded-dataset' | 'other';
  label?: string | null;
}

export interface AnalysisHistoryRecord {
  id: string;
  createdAt?: string | null;
  source?: AnalysisDataSource | null;
  status?: string | null;
  summary?: string | null;
}

export interface AnalysisDetailResult {
  id: string;
  label: string;
  value?: string | null;
  explanation?: string | null;
}

export interface AnalysisDetails extends AnalysisHistoryRecord {
  results?: readonly AnalysisDetailResult[] | null;
  telemetryMetadata?: readonly { id: string; label: string; value?: string | null }[] | null;
}

/** Loading/error are supplied only by a future real request; production is not-integrated. */
export type HistoryResource<T> =
  | { status: 'not-integrated' }
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; data: T };
