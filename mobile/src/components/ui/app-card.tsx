// Non-interactive surfaces that keep nested controls independently accessible.
import { View, StyleSheet, type ViewProps } from 'react-native';
import { colors, radii, shadows, spacing } from '@/theme/tokens';

export interface AppCardProps extends ViewProps {
  variant?: 'outlined' | 'filled' | 'raised';
  padding?: keyof typeof spacing;
}

export function AppCard({ variant = 'outlined', padding = 'md', style, ...props }: AppCardProps) {
  return <View {...props} style={[styles.card, { padding: spacing[padding],
    backgroundColor: variant === 'filled' ? colors.backgroundSecondary : colors.background },
    variant === 'raised' && shadows.card, style]} />;
}

const styles = StyleSheet.create({
  card: { borderRadius: radii.lg, borderWidth: 1, borderColor: colors.border, gap: spacing.sm },
});
