// Native text with shared typography, semantic colors, and unrestricted font scaling.
import { Text, type TextProps } from 'react-native';
import { colors, typography } from '@/theme/tokens';

const tones = {
  primary: colors.text,
  secondary: colors.textSecondary,
  accent: colors.accent,
  error: colors.danger,
  success: colors.success,
  warning: colors.warning,
  inverse: colors.onAccent,
} as const;

export interface AppTextProps extends TextProps {
  variant?: keyof typeof typography;
  tone?: keyof typeof tones;
}

export function AppText({ variant = 'body', tone = 'primary', style, ...props }: AppTextProps) {
  return <Text {...props} style={[typography[variant], { color: tones[tone] }, style]} />;
}
