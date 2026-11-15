// Light welcome screen preserves the existing signup and login destinations.
import { StyleSheet, View } from 'react-native';
import { useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { AppBrand } from '@/components/app-brand';
import { AppButton } from '@/components/ui/app-button';
import { AppCard } from '@/components/ui/app-card';
import { AppIcon } from '@/components/ui/app-icon';
import { AppScreen } from '@/components/ui/app-screen';
import { AppText } from '@/components/ui/app-text';
import { colors, spacing } from '@/theme/tokens';

export default function Welcome() {
  const router = useRouter();
  return (
    <AppScreen contentContainerStyle={styles.page}>
      <StatusBar style="dark" />
      <AppBrand />
      <View style={styles.introduction}>
        <AppCard variant="filled" padding="xl" style={styles.illustration}>
          <AppIcon name="car" size={112} color={colors.accent} strokeWidth={1} />
        </AppCard>
        <AppText variant="display" accessibilityRole="header">Understand your vehicle.</AppText>
        <AppText tone="secondary">Explore vehicle signals and clearer maintenance insights, all in one place.</AppText>
        <AppText variant="caption" tone="secondary">Manufacturer-independent vehicle intelligence · Prototype</AppText>
      </View>
      <View style={styles.actions}>
        <AppButton
          title="Get started"
          onPress={() => router.push({ pathname: '/(auth)/login', params: { mode: 'signup' } })}
        />
        <AppText variant="label" tone="secondary" style={styles.returning}>Already have an account?</AppText>
        <AppButton title="Log in" variant="text" onPress={() => router.push('/(auth)/login')} />
      </View>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  page: { maxWidth: 480, padding: spacing.xl, paddingTop: spacing.xxl, gap: spacing.xxl },
  introduction: { flexGrow: 1, justifyContent: 'center', gap: spacing.md },
  illustration: { alignItems: 'center', justifyContent: 'center', minHeight: 184, marginBottom: spacing.sm },
  actions: { gap: spacing.xs },
  returning: { textAlign: 'center', marginTop: spacing.sm },
});
