// Reusable result presentation: provenance and explanation are mandatory for every value.
import { StyleSheet, View } from 'react-native';
import type { AnalysisResult } from '@/types/ai-insights';
import { AppCard } from '@/components/ui/app-card';
import { AppText } from '@/components/ui/app-text';
import { AppStatus } from '@/components/ui/app-status';
import { spacing } from '@/theme/tokens';

export function AnalysisResultCard({ result }: { result: AnalysisResult }) {
  return <AppCard testID={`analysis-${result.id}`}>
    <View style={styles.heading}>
      <AppText variant="label" style={styles.title}>{result.title}</AppText>
      <AppStatus label={result.sourceLabel} tone="info" />
    </View>
    <AppText variant="metric">{result.value}</AppText>
    <AppText variant="caption" tone="secondary">{result.explanation}</AppText>
  </AppCard>;
}
const styles = StyleSheet.create({
  heading: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: spacing.sm },
  title: { flex: 1, minWidth: 160 },
});
