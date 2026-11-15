// Loading, empty, and error presentation; all retries are supplied by the caller.
import { ActivityIndicator, View, StyleSheet, type ViewProps } from 'react-native';
import { colors, spacing } from '@/theme/tokens';
import { AppButton } from './app-button';
import { AppIcon } from './app-icon';
import { AppText } from './app-text';

export interface AppDataStateProps extends ViewProps {
  status: 'loading' | 'empty' | 'error';
  title?: string;
  message?: string;
  onRetry?: () => void;
  retryLabel?: string;
  retrying?: boolean;
}

const titles = { loading: 'Loading…', empty: 'Nothing here yet', error: 'Unable to load' } as const;

export function AppDataState({ status, title = titles[status], message, onRetry, retryLabel = 'Try again', retrying = false, style, ...props }: AppDataStateProps) {
  return <View accessibilityLiveRegion="polite" {...props} style={[styles.container, style]}>
    {status === 'loading' ? <ActivityIndicator color={colors.accent} accessibilityLabel={title} />
      : <AppIcon name={status === 'error' ? 'warning' : 'info'} color={status === 'error' ? colors.danger : colors.textSecondary} />}
    <AppText variant="subtitle" accessibilityRole={status === 'error' ? 'alert' : undefined}>{title}</AppText>
    {!!message && <AppText tone="secondary">{message}</AppText>}
    {status !== 'loading' && onRetry && <AppButton title={retryLabel} onPress={onRetry} loading={retrying} variant="secondary" />}
  </View>;
}

const styles = StyleSheet.create({
  container: { padding: spacing.xl, gap: spacing.sm, alignItems: 'flex-start' },
});
