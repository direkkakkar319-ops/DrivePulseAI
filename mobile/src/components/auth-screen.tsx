// Light authentication layout; session handling and form actions remain in the route.
import type { PropsWithChildren } from 'react';
import { StyleSheet, View } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { spacing } from '@/theme/tokens';
import { AppBrand } from './app-brand';
import { AppScreen } from './ui/app-screen';
import { AppText } from './ui/app-text';

export function AuthScreen({ title, subtitle, children }: PropsWithChildren<{ title: string; subtitle: string }>) {
  return (
    <AppScreen keyboardAvoiding contentContainerStyle={styles.page}>
      <StatusBar style="dark" />
      <View style={styles.brand}>
        <AppBrand />
      </View>
      <View style={styles.heading}>
        <AppText variant="display" accessibilityRole="header">{title}</AppText>
        <AppText tone="secondary">{subtitle}</AppText>
      </View>
      {children}
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  page: { maxWidth: 480, padding: spacing.xl, paddingTop: spacing.xxl, gap: spacing.xl },
  brand: { marginBottom: spacing.md },
  heading: { gap: spacing.sm },
});
