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

export function AIInsightsScreen({ initialDemo = false, pickCsv }: { initialDemo?: boolean; pickCsv?: PickCsv }) {
  const data = useInsightsSource(initialDemo, pickCsv);
  const demo = data.source.kind === 'demo';
  return <AppScreen edges={['top', 'left', 'right']}>
    <AppHeader title="AI Insights" />
    <AppText variant="subtitle" accessibilityRole="header">Choose Data Source</AppText>
    <AppCard>
      <CsvSourceControl available={Boolean(pickCsv)} selecting={data.selecting}
        file={data.source.kind === 'csv' ? data.source.file : undefined} error={data.error}
        onSelect={() => { void data.selectCsv(); }} onClear={data.clearCsv} />
      <View style={styles.switchRow}>
        <AppText variant="label" style={styles.switchLabel}>Use Demo Data</AppText>
        <Switch accessible accessibilityRole="switch" accessibilityLabel="Use Demo Data" value={demo} disabled={data.selecting}
          accessibilityState={{ checked: demo, disabled: data.selecting }}
          onValueChange={data.useDemo} trackColor={{ false: colors.borderStrong, true: colors.accent }}
          thumbColor={colors.background} style={styles.switch} />
      </View>
      <AppText variant="caption" tone="secondary">{demoInsights.description}</AppText>
      <AppText variant="caption" tone="secondary">Selecting demo data replaces a CSV selection. Nothing is added to saved analysis history.</AppText>
      {demo && <AppStatus label="Demo data selected" tone="info" />}
    </AppCard>

    <AppText variant="subtitle" accessibilityRole="header">Analysis Results</AppText>
    {demo ? demoInsights.results.map(result => <AnalysisResultCard key={result.id} result={result} />)
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
    </AppCard> : <AppCard><AppDataState status="empty" title="No telemetry data selected"
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
