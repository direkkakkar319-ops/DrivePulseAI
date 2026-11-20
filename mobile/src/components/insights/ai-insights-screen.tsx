// Generic Insights demonstration independent of accounts, Garage, recordings, and ML services.
import { StyleSheet, Switch, View } from 'react-native';
import { AppCard } from '@/components/ui/app-card';
import { AppDataState } from '@/components/ui/app-data-state';
import { AppHeader } from '@/components/ui/app-header';
import { AppScreen } from '@/components/ui/app-screen';
import { AppStatus } from '@/components/ui/app-status';
import { AppText } from '@/components/ui/app-text';
import { demoInsights } from '@/config/demo-insights';
import { useInsightsSource } from '@/hooks/use-insights-source';
import { colors, layout, spacing } from '@/theme/tokens';
import type { PickCsv } from '@/types/ai-insights';
import { AnalysisResultCard } from './analysis-result-card';
import { CsvSourceControl } from './csv-source-control';
import type { AnalysisController } from '@/hooks/use-leaf-analysis';
import { LeafAnalysisControls } from './leaf-analysis-controls';
import { LeafResults, LeafAnalysisFeedback } from './leaf-analysis-results';

export function AIInsightsScreen({ initialDemo = false, pickCsv, analysis }: { initialDemo?: boolean; pickCsv?: PickCsv; analysis?: AnalysisController }) {
  const data = useInsightsSource(initialDemo, pickCsv);
  const source = analysis?.source ?? data.source;
  const selecting = analysis?.selecting ?? data.selecting;
  const demo = source.kind === 'demo';
  return <AppScreen edges={['top', 'left', 'right']}>
    <AppHeader title="AI Insights" />
    <AppText variant="subtitle" accessibilityRole="header">Choose Data Source</AppText>
    <AppCard>
      {analysis && <LeafAnalysisControls analysis={analysis} />}
      <CsvSourceControl available={analysis ? analysis.canPickCsv : Boolean(pickCsv)} selecting={selecting}
        file={source.kind === 'csv' ? source.file : undefined} error={analysis?.selectionError ?? data.error}
        selectionLabel={analysis ? analysis.result.status === 'ready' && analysis.result.data.source_type === 'uploaded_csv'
          ? 'CSV analysis received · Not saved' : 'Selected CSV · Not saved' : undefined}
        onSelect={() => { void (analysis ?? data).selectCsv(); }} onClear={(analysis ?? data).clearCsv} />
      <View style={styles.switchRow}>
        <AppText variant="label" style={styles.switchLabel}>Use Demo Data</AppText>
        <Switch accessible accessibilityRole="switch" accessibilityLabel="Use Demo Data" value={demo} disabled={selecting}
          accessibilityState={{ checked: demo, disabled: selecting }}
          onValueChange={(analysis ?? data).useDemo} trackColor={{ false: colors.borderStrong, true: colors.accent }}
          thumbColor={colors.background} style={styles.switch} />
      </View>
      <AppText variant="caption" tone="secondary">{demoInsights.description}</AppText>
      <AppText variant="caption" tone="secondary">Selecting demo data replaces a real data selection. Nothing is added to saved analysis history.</AppText>
      {demo && <AppStatus label="Demo data selected" tone="info" />}
    </AppCard>

    <AppText variant="subtitle" accessibilityRole="header">Analysis Results</AppText>
    {demo ? demoInsights.results.map(result => <AnalysisResultCard key={result.id} result={result} />)
      : analysis && analysis.result.status !== 'idle' ? <LeafAnalysisFeedback analysis={analysis} />
      : analysis ? <AppCard><AppDataState status="empty" title="No analysis results yet"
        message="Select a built-in Nissan Leaf sample or a compatible CSV, then start analysis." /></AppCard>
      : <AppCard><AppDataState status="empty" title={data.source.kind === 'csv' ? 'Analysis not available yet' : 'No analysis results yet'}
        message={data.source.kind === 'csv' ? 'The selected CSV has not been uploaded or analysed. ML inference is not integrated.'
          : 'Enable Use Demo Data to preview illustrative results.'} /></AppCard>}

    <AppText variant="subtitle" accessibilityRole="header">Telemetry Data</AppText>
    {demo ? <AppCard>
      <AppStatus label="Sample telemetry · Demo" tone="info" />
      <AppText variant="caption" tone="secondary">Illustrative values, separate from your saved vehicles and recorded research data.</AppText>
      {demoInsights.telemetry.map(item => <View key={item.id} style={styles.measurement}>
        <AppText tone="secondary" style={styles.switchLabel}>{item.label}</AppText>
        <AppText variant="label">{item.value}{item.unit === '%' || item.unit === '°C' ? '' : ' '}{item.unit}</AppText>
      </View>)}
    </AppCard> : analysis?.result.status === 'ready' ? <LeafResults data={analysis.result.data} telemetryOnly /> : <AppCard><AppDataState status="empty" title="No telemetry data selected"
      message={data.source.kind === 'csv' ? 'CSV telemetry preview is not available yet. The selected file has not been read.'
        : 'Enable Use Demo Data to view sample telemetry.'} /></AppCard>}
  </AppScreen>;
}
const styles = StyleSheet.create({
  switchRow: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: spacing.sm },
  switchLabel: { flex: 1, minWidth: 140 },
  switch: { minHeight: layout.minimumTouchTarget, minWidth: layout.minimumTouchTarget },
  measurement: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm, paddingVertical: spacing.sm,
    borderTopWidth: 1, borderTopColor: colors.border },
});
