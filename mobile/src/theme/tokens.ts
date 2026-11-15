// Shared light-theme tokens; importing these does not change the active app theme.
import type { TextStyle, ViewStyle } from 'react-native';

export const colors = {
  background: '#FFFFFF',
  backgroundSecondary: '#F8F9FB',
  text: '#17212F',
  textSecondary: '#667085',
  accent: '#2563EB',
  accentPressed: '#1D4ED8',
  accentSoft: '#EFF6FF',
  border: '#E5E7EB',
  // Inputs need a stronger boundary than decorative card dividers.
  borderStrong: '#667085',
  focus: '#2563EB',
  onAccent: '#FFFFFF',
  disabledBackground: '#F2F4F7',
  disabledText: '#667085',
  success: '#166534',
  successSoft: '#F0FDF4',
  warning: '#92400E',
  warningSoft: '#FFFBEB',
  danger: '#B42318',
  dangerSoft: '#FEF3F2',
} as const;

export const spacing = { xxs: 4, xs: 8, sm: 12, md: 16, lg: 20, xl: 24, xxl: 32, xxxl: 48 } as const;
export const radii = { sm: 8, md: 12, lg: 16, pill: 999 } as const;
export const typography = {
  caption: { fontSize: 12, lineHeight: 18, fontWeight: '400' },
  body: { fontSize: 16, lineHeight: 24, fontWeight: '400' },
  label: { fontSize: 14, lineHeight: 20, fontWeight: '600' },
  subtitle: { fontSize: 18, lineHeight: 26, fontWeight: '600' },
  title: { fontSize: 24, lineHeight: 32, fontWeight: '700' },
  display: { fontSize: 32, lineHeight: 40, fontWeight: '700' },
  metric: { fontSize: 28, lineHeight: 36, fontWeight: '600', fontVariant: ['tabular-nums'] },
} as const satisfies Record<string, TextStyle>;

export const layout = { minimumTouchTarget: 48, contentMaxWidth: 720 } as const;
export const shadows = {
  card: {
    shadowColor: colors.text,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 6,
    elevation: 1,
  } satisfies ViewStyle,
} as const;

export const statusColors = {
  neutral: { foreground: colors.textSecondary, background: colors.backgroundSecondary },
  info: { foreground: colors.accentPressed, background: colors.accentSoft },
  success: { foreground: colors.success, background: colors.successSoft },
  warning: { foreground: colors.warning, background: colors.warningSoft },
  error: { foreground: colors.danger, background: colors.dangerSoft },
} as const;
export type StatusTone = keyof typeof statusColors;
