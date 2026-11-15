// Text-first semantic badges and notices; statuses never depend on color alone.
import { StyleSheet, View, type ViewProps } from 'react-native';
import { radii, spacing, statusColors, type StatusTone } from '@/theme/tokens';
import { AppIcon, type AppIconName } from './app-icon';
import { AppText } from './app-text';

export interface AppStatusProps extends ViewProps {
  label: string;
  tone?: StatusTone;
  variant?: 'badge' | 'notice';
  description?: string;
  icon?: AppIconName;
}

export function AppStatus({ label, tone = 'neutral', variant = 'badge', description, icon, style, ...props }: AppStatusProps) {
  const treatment = statusColors[tone];
  return <View accessibilityLiveRegion={variant === 'notice' ? 'polite' : undefined} {...props}
    style={[styles.container, variant === 'badge' ? styles.badge : styles.notice, { backgroundColor: treatment.background }, style]}>
    {icon && <AppIcon name={icon} color={treatment.foreground} size={18} />}
    <View style={styles.copy}>
      <AppText variant="label" style={{ color: treatment.foreground }}
        accessibilityRole={tone === 'error' && variant === 'notice' ? 'alert' : undefined}>{label}</AppText>
      {!!description && <AppText style={{ color: treatment.foreground }}>{description}</AppText>}
    </View>
  </View>;
}

const styles = StyleSheet.create({
  container: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  badge: { alignSelf: 'flex-start', borderRadius: radii.pill, paddingHorizontal: spacing.sm, paddingVertical: spacing.xxs },
  notice: { borderRadius: radii.md, padding: spacing.md },
  copy: { flexShrink: 1, gap: spacing.xxs },
});
