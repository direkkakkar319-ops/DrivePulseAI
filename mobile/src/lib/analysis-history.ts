// Display only provided history metadata, with explicit fallbacks instead of inferred values.
import type { AnalysisDataSource } from '@/types/analysis-history';

export function analysisDate(value?: string | null): string {
  if (!value?.trim()) return 'Date and time unavailable';
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return 'Date and time unavailable';
  return date.toLocaleString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZoneName: 'short',
  });
}

export function analysisSource(source?: AnalysisDataSource | null): string {
  if (!source) return 'Data source unavailable';
  const kind = { 'csv-upload': 'CSV upload', 'recorded-dataset': 'Recorded dataset', other: 'Other source' }[source.kind];
  return source.label?.trim() ? `${kind} · ${source.label.trim()}` : kind;
}
