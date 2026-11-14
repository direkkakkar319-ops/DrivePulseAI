// Typed, dependency-light SVG icons independent of vehicle features and routing.
import type { ColorValue } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { colors } from '@/theme/tokens';

const paths = {
  home: 'M3 10l9-7 9 7M5 9v12h5v-7h4v7h5V9',
  car: 'M3 11l2-6h14l2 6M3 11h18v8H3zM6 19v2m12-2v2M6 14h2m8 0h2',
  insights: 'M2 12h5l3-8 4 16 3-8h5',
  history: 'M3 11a9 9 0 1 1 2 7M3 4v7h7M12 7v5l3 2',
  profile: 'M4 21v-2c0-6 16-6 16 0v2M8 6a4 4 0 1 0 8 0 4 4 0 1 0-8 0',
  back: 'M20 12H4m6-6-6 6 6 6',
  chevronRight: 'm9 5 7 7-7 7',
  plus: 'M12 4v16M4 12h16',
  close: 'm6 6 12 12M18 6 6 18',
  check: 'm5 12 4 4L19 6',
  info: 'M12 8h.01M12 11v6M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0',
  warning: 'M12 3 2 21h20L12 3M12 9v5m0 3v1',
  eye: 'M2 12s3-7 10-7 10 7 10 7-3 7-10 7S2 12 2 12M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0',
  eyeOff: 'm3 3 18 18M10 5c7-1 12 7 12 7s-1 3-4 5M6 6c-3 2-4 6-4 6s3 7 10 7c2 0 3 0 4-1M10 10a3 3 0 0 0 4 4',
  refresh: 'M20 8a9 9 0 0 0-15-3L2 8m0-5v5h5M4 16a9 9 0 0 0 15 3l3-3m0 5v-5h-5',
} as const;

export type AppIconName = keyof typeof paths;
export interface AppIconProps {
  name: AppIconName;
  size?: number;
  color?: ColorValue;
  strokeWidth?: number;
  /** Omit for decorative icons; label the surrounding button instead. */
  accessibilityLabel?: string;
  testID?: string;
}

export function AppIcon({ name, size = 22, color = colors.textSecondary, strokeWidth = 1.8, accessibilityLabel, testID }: AppIconProps) {
  const labeled = Boolean(accessibilityLabel);
  return <Svg width={size} height={size} viewBox="0 0 24 24" testID={testID}
    accessible={labeled} accessibilityRole={labeled ? 'image' : undefined}
    accessibilityLabel={accessibilityLabel} accessibilityElementsHidden={!labeled}
    importantForAccessibility={labeled ? 'yes' : 'no-hide-descendants'}>
    <Path d={paths[name]} stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" fill="none" />
  </Svg>;
}
