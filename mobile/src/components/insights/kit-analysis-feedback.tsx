import { AppButton } from '@/components/ui/app-button';
import { AppCard } from '@/components/ui/app-card';
import { AppDataState } from '@/components/ui/app-data-state';
import { AppStatus } from '@/components/ui/app-status';
import { AppText } from '@/components/ui/app-text';
import { KitAnalysisVisualization } from './kit-analysis-visualization';
import type { AnalysisController } from '@/hooks/use-analysis';

export function KitAnalysisFeedback({ analysis }: { analysis: AnalysisController }) {
  const { result } = analysis;
  if (result.status === 'loading') return <AppCard><AppDataState status="loading" title="Running KIT analysis"
    message="The backend is preparing telemetry and requesting model results. This may take a few minutes. You can cancel." /></AppCard>;
  if (result.status === 'error') return <AppCard><AppDataState status="error" title="Analysis unavailable"
    message={result.message} retryLabel="Retry analysis" onRetry={() => { void analysis.run(); }} /></AppCard>;
  if (result.status !== 'ready') return null;
  const data = result.data;
  return <><AppCard testID="kit-analysis-summary">
    <AppStatus label="Real KIT analysis received" tone="success" variant="notice" />
    <AppText variant="subtitle">{data.source_type === 'packaged_sample' ? data.sample.display_name : 'Uploaded KIT-compatible CSV'}</AppText>
    <AppText>Evaluated pairs: {data.summary.evaluated_pairs}</AppText>
    <AppText>Flagged pairs: {data.summary.novel_pairs}</AppText>
    <AppText>Unflagged pairs: {data.summary.not_novel_pairs} · Flagged: {data.summary.novel_percentage.toFixed(2)}%</AppText>
    <AppText>Mean anomaly score: {data.summary.mean_anomaly_score.toFixed(3)}</AppText>
    <AppText>{data.window_count} prepared windows · {data.window_seconds} seconds each · Not saved</AppText>
    <AppText variant="caption">Recording: {data.source_type === 'packaged_sample' ? data.sample.recording_id : data.source.recording_id}</AppText>
    <AppText variant="caption">Recording date: {data.source_type === 'packaged_sample' ? data.sample.recording_date : `${data.source.recording_date} (caller supplied, unverified)`}</AppText>
    <AppText>Maximum anomaly score: {data.summary.max_anomaly_score.toFixed(3)}</AppText>
    <AppText>Novelty threshold: {data.summary.threshold.toFixed(3)}</AppText>
    <AppText tone="secondary">{data.explanation.summary}</AppText>
    <AppText variant="caption" tone="secondary">Model: {data.model.model_version}</AppText>
    <AppText variant="caption" tone="secondary">Combustion-engine telemetry novelty, not fault diagnosis or EV battery health. Results are temporary, are not saved to History and are not associated with a Garage vehicle.</AppText>
    <AppButton title="Clear analysis" variant="text" onPress={analysis.cancel} />
  </AppCard><KitAnalysisVisualization data={data} section="scores" /></>;
}
