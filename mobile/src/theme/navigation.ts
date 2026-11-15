// Opt-in navigation colors for a later screen migration; no provider is mounted here.
import { DefaultTheme, type Theme } from 'expo-router';
import { colors } from './tokens';

export const appNavigationTheme: Theme = {
  ...DefaultTheme,
  dark: false,
  colors: {
    ...DefaultTheme.colors,
    primary: colors.accent,
    background: colors.background,
    card: colors.background,
    text: colors.text,
    border: colors.border,
    notification: colors.danger,
  },
};
