// Unrouted details presentation for a future genuine record; never reads demo state.
import { AppCard } from '@/components/ui/app-card';
import { AppDataState } from '@/components/ui/app-data-state';
import { AppHeader } from '@/components/ui/app-header';
import { AppScreen } from '@/components/ui/app-screen';
import { AppText } from '@/components/ui/app-text';
import type { AnalysisDetails, HistoryResource } from '@/types/analysis-history';
import { AnalysisRecordMetadata } from './analysis-record-metadata';

export function AnalysisDetailsScreen({ resource, onBack, onRetry }: {
  resource: HistoryResource<AnalysisDetails | null>;
  onBack?: () => void;
  onRetry?: () => void;
}) {
  const record = resource.status === 'ready' ? resource.data : null;
  return <AppScreen>
    <AppHeader title="Analysis details" onBack={onBack} />
    {resource.status === 'loading' ? <AppDataState status="loading" title="Loading analysis details" />
      : resource.status === 'error' ? <AppDataState status="error" title="Could not load analysis details"
        message={resource.message} onRetry={onRetry} retryLabel="Retry" />
      : !record ? <AppDataState status="empty" title="Analysis unavailable" message="No saved analysis record is available." />
      : <>
        <AppCard><AnalysisRecordMetadata record={record} /></AppCard>
        <AppText variant="subtitle" accessibilityRole="header">Analysis results</AppText>
        {record.results?.length ? record.results.map(result => <AppCard key={result.id}>
          <AppText variant="label">{result.label}</AppText>
          <AppText>{result.value?.trim() || 'Result unavailable'}</AppText>
          <AppText tone="secondary">{result.explanation?.trim() || 'No explanation provided.'}</AppText>
        </AppCard>) : <AppCard><AppDataState status="empty" title="No analysis results available"
          message="This record does not include analysis results." /></AppCard>}
        <AppText variant="subtitle" accessibilityRole="header">Telemetry metadata</AppText>
        {record.telemetryMetadata?.length ? record.telemetryMetadata.map(item => <AppCard key={item.id}>
          <AppText variant="label">{item.label}</AppText>
          <AppText>{item.value?.trim() || 'Metadata unavailable'}</AppText>
        </AppCard>) : <AppCard><AppDataState status="empty" title="No telemetry metadata available"
          message="This record does not include telemetry metadata." /></AppCard>}
      </>}
  </AppScreen>;
}
