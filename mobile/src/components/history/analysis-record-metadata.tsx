// Shared accessible metadata for history cards and details; no Garage identity inference.
import { AppStatus } from '@/components/ui/app-status';
import { AppText } from '@/components/ui/app-text';
import { analysisDate, analysisSource } from '@/lib/analysis-history';
import type { AnalysisHistoryRecord } from '@/types/analysis-history';

export function AnalysisRecordMetadata({ record }: { record: AnalysisHistoryRecord }) {
  return <>
    <AppText variant="label" selectable>Analysis ID: {record.id}</AppText>
    <AppText tone="secondary">Date and time: {analysisDate(record.createdAt)}</AppText>
    <AppText tone="secondary">Data source: {analysisSource(record.source)}</AppText>
    <AppStatus label={`Status: ${record.status?.trim() || 'Unavailable'}`} />
    <AppText>{record.summary?.trim() || 'No summary provided.'}</AppText>
  </>;
}
