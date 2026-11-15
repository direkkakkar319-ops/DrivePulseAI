// Compact visual system for the recorded Nissan Leaf experience.
export const colors = {
  canvas: '#F3F5F2',
  surface: '#FFFFFF',
  surfaceMuted: '#EDF2EE',
  text: '#16231E',
  textSecondary: '#596760',
  border: '#D5DED8',
  borderStrong: '#B7C6BD',
  accent: '#1F634B',
  accentPressed: '#174B39',
  accentSoft: '#E1EEE7',
  typical: '#2D6A52',
  unusual: '#9C5A13',
  unusualSoft: '#F8EBD9',
  danger: '#9A3838',
  white: '#FFFFFF',
} as const;

export const spacing = {
  xxs: 4,
  xs: 8,
  sm: 12,
  md: 16,
  lg: 20,
  xl: 24,
  xxl: 32,
} as const;

export const radius = { sm: 6, md: 10, lg: 14, pill: 999 } as const;
export const type = {
  caption: { fontSize: 12, lineHeight: 17 } as const,
  body: { fontSize: 15, lineHeight: 22 } as const,
  label: { fontSize: 13, lineHeight: 18, fontWeight: '600' as const } as const,
  section: { fontSize: 18, lineHeight: 24, fontWeight: '600' as const } as const,
  title: { fontSize: 30, lineHeight: 36, fontWeight: '700' as const } as const,
  metric: { fontSize: 28, lineHeight: 34, fontWeight: '600' as const } as const,
} as const;

export const minimumTouchTarget = 48;
