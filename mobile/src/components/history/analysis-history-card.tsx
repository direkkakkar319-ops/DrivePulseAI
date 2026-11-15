// A supplied persisted-record view; navigation is enabled only when a consumer provides it.
import { AppButton } from '@/components/ui/app-button';
import { AppCard } from '@/components/ui/app-card';
import type { AnalysisHistoryRecord } from '@/types/analysis-history';
import { AnalysisRecordMetadata } from './analysis-record-metadata';

export function AnalysisHistoryCard({ record, onOpen }: {
  record: AnalysisHistoryRecord;
  onOpen?: (id: string) => void;
}) {
  return <AppCard testID={`history-record-${record.id}`}>
    <AnalysisRecordMetadata record={record} />
    {onOpen && <AppButton title="View analysis" accessibilityLabel={`View analysis ${record.id}`} variant="secondary"
      onPress={() => onOpen(record.id)} />}
  </AppCard>;
}
