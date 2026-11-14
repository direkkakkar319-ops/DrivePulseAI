// Persist the first vehicle and onboarding completion together through the account provider.
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { AppBrand } from '@/components/app-brand';
import { VehicleSetupForm } from '@/components/vehicle-setup-form';
import { AppHeader } from '@/components/ui/app-header';
import { AppScreen } from '@/components/ui/app-screen';
import { AppText } from '@/components/ui/app-text';
import { useAuthStore } from '@/store/authStore';
import { colors, spacing } from '@/theme/tokens';
import { useOnboarding } from '@/store/onboardingStore';
import { AppButton } from '@/components/ui/app-button';
import { AppStatus } from '@/components/ui/app-status';
import { authService } from '@/api/auth';
import { authErrorMessage } from '@/api/auth-errors';

export default function VehicleSetupRoute() {
  const { user } = useAuthStore();
  if (!user?.emailVerified) return null;
  return <FirstVehicleSetup key={user.uid} />;
}

function FirstVehicleSetup() {
  const router = useRouter();
  const account = useOnboarding();
  const [error, setError] = useState('');
  const leave = () => router.replace('/(main)/dashboard');
  const completed = account.resource.status === 'ready' && Boolean(account.resource.data.completed_at);
  async function logout() {
    try { await authService.signOut(); } catch (failure) { setError(authErrorMessage(failure)); }
  }
  return <AppScreen keyboardAvoiding contentContainerStyle={styles.page}>
    <StatusBar style="dark" />
    <AppBrand />
    <View style={styles.progress}>
      <AppText variant="caption" tone="secondary">Vehicle setup · Step 1 of 1</AppText>
      <View style={styles.progressLine} />
    </View>
    <AppHeader title="Your first vehicle" subtitle="Start with a few details about your vehicle."
      onBack={completed ? () => router.canGoBack() ? router.back() : leave() : undefined} />
    <AppText variant="caption" tone="secondary">Continue saves this vehicle to your Garage and makes it active. Telemetry will remain unavailable until a supported data source is connected.</AppText>
    <VehicleSetupForm onSubmit={async value => { await account.saveFirstVehicle(value); }} />
    {!!error && <AppStatus label={error} tone="error" variant="notice" />}
    <AppButton title="Reload account" variant="text" disabled={account.saving} onPress={() => { void account.reload(); }} />
    <AppButton title="Log out" variant="text" disabled={account.saving} onPress={logout} />
  </AppScreen>;
}

const styles = StyleSheet.create({
  page: { maxWidth: 480, padding: spacing.xl, paddingTop: spacing.xxl, gap: spacing.xl },
  progress: { gap: spacing.xs },
  progressLine: { height: 3, backgroundColor: colors.accent, borderRadius: 2 },
});
