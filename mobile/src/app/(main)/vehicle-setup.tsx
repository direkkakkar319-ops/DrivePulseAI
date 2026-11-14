// Opt-in first-vehicle route inside the existing verified-account guard; no auto-entry or writes.
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

export default function VehicleSetupRoute() {
  const { user } = useAuthStore();
  if (!user?.emailVerified) return null;
  return <FirstVehicleSetup key={user.uid} />;
}

function FirstVehicleSetup() {
  const router = useRouter();
  const leave = () => router.replace('/(main)/dashboard');
  return <AppScreen keyboardAvoiding contentContainerStyle={styles.page}>
    <StatusBar style="dark" />
    <AppBrand />
    <View style={styles.progress}>
      <AppText variant="caption" tone="secondary">Vehicle setup · Step 1 of 1</AppText>
      <View style={styles.progressLine} />
    </View>
    <AppHeader title="Your first vehicle" subtitle="Start with a few details about your vehicle."
      onBack={() => router.canGoBack() ? router.back() : leave()} />
    <AppText variant="caption" tone="secondary">These details are kept only while this screen is open. They are not saved to your Garage yet.</AppText>
    {/* Phase 3.4 can persist the validated callback value before navigating.
        Do not pass metadata to the simulator or attach unrelated recordings. */}
    <VehicleSetupForm onSubmit={leave} />
  </AppScreen>;
}

const styles = StyleSheet.create({
  page: { maxWidth: 480, padding: spacing.xl, paddingTop: spacing.xxl, gap: spacing.xl },
  progress: { gap: spacing.xs },
  progressLine: { height: 3, backgroundColor: colors.accent, borderRadius: 2 },
});
