// Honest empty History until a genuine authenticated persistence adapter is available.
import { StyleSheet, View } from 'react-native';
import { AppButton } from '@/components/ui/app-button';
import { AppCard } from '@/components/ui/app-card';
import { AppDataState } from '@/components/ui/app-data-state';
import { AppHeader } from '@/components/ui/app-header';
import { AppIcon } from '@/components/ui/app-icon';
import { AppScreen } from '@/components/ui/app-screen';
import { AppText } from '@/components/ui/app-text';
import { colors, radii, spacing } from '@/theme/tokens';
import type { AnalysisHistoryRecord, HistoryResource } from '@/types/analysis-history';
import { AnalysisHistoryCard } from './analysis-history-card';

const notIntegrated = { status: 'not-integrated' } as const;
export function HistoryScreen({ resource = notIntegrated, onExploreInsights, onRetry, onOpenRecord }: {
  resource?: HistoryResource<readonly AnalysisHistoryRecord[]>;
  onExploreInsights: () => void;
  onRetry?: () => void;
  onOpenRecord?: (id: string) => void;
}) {
  return <AppScreen edges={['top', 'left', 'right']}>
    <AppHeader title="History" subtitle="Your vehicle analysis records" />
    {resource.status === 'loading' ? <AppDataState status="loading" title="Loading analysis history" />
      : resource.status === 'error' ? <AppCard><AppDataState status="error" title="Could not load analysis history"
        message={resource.message} onRetry={onRetry} retryLabel="Retry" /></AppCard>
      : resource.status === 'ready' && resource.data.length > 0
        ? resource.data.map(record => <AnalysisHistoryCard key={record.id} record={record} onOpen={onOpenRecord} />)
        : <AppCard style={styles.empty}>
          <View style={styles.icon}><AppIcon name="history" color={colors.accent} size={32} /></View>
          <AppText variant="subtitle" style={styles.copy}>No analysis history yet</AppText>
          <AppText tone="secondary" style={styles.copy}>Your completed vehicle analyses will appear here once real analysis is available.</AppText>
          <AppButton title="Explore AI Insights" onPress={onExploreInsights} />
        </AppCard>}
  </AppScreen>;
}
const styles = StyleSheet.create({
  empty: { alignItems: 'center', paddingVertical: spacing.xxl, gap: spacing.lg },
  icon: { width: 64, height: 64, borderRadius: radii.lg, backgroundColor: colors.accentSoft,
    alignItems: 'center', justifyContent: 'center' },
  copy: { textAlign: 'center' },
});
