// Presentational header; consumers supply navigation and trailing action callbacks.
import type { ReactNode } from 'react';
import { StyleSheet, View, type ViewProps } from 'react-native';
import { layout, spacing } from '@/theme/tokens';
import { AppButton } from './app-button';
import { AppText } from './app-text';

export interface AppHeaderProps extends ViewProps {
  title: string;
  subtitle?: string;
  onBack?: () => void;
  backLabel?: string;
  trailing?: ReactNode;
}

export function AppHeader({ title, subtitle, onBack, backLabel = 'Back', trailing, style, ...props }: AppHeaderProps) {
  return <View {...props} style={[styles.header, style]}>
    {onBack && <AppButton title={backLabel} variant="text" icon="back" onPress={onBack} />}
    <View style={styles.copy}>
      <AppText variant="title" accessibilityRole="header">{title}</AppText>
      {!!subtitle && <AppText tone="secondary">{subtitle}</AppText>}
    </View>
    {trailing}
  </View>;
}

const styles = StyleSheet.create({
  header: { minHeight: layout.minimumTouchTarget, flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: spacing.sm },
  copy: { flex: 1, minWidth: 120, gap: spacing.xxs },
});
