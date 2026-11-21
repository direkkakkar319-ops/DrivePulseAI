// Keep all product screens inside the existing verified-account route guard.
import { Stack } from 'expo-router';
import { VehicleDataProvider } from '@/store/vehicleDataStore';
import { ProfileSyncProvider } from '@/hooks/use-profile-sync';
import { useAuthStore } from '@/store/authStore';
import { colors } from '@/theme/tokens';
import { StatusBar } from 'expo-status-bar';
import { OnboardingProvider } from '@/store/onboardingStore';
import { OnboardingGate } from '@/components/onboarding-gate';
export default function MainLayout() {
  const { user } = useAuthStore();
  if (!user?.emailVerified) return null;
  return (
    <ProfileSyncProvider key={user?.uid}>
      <OnboardingProvider uid={user.uid}>
        <VehicleDataProvider>
          <StatusBar style="dark" />
          <OnboardingGate>
            <Stack
              screenOptions={{
                headerShown: false,
                contentStyle: { backgroundColor: colors.background },
                animation: 'fade_from_bottom',
              }}
            >
              <Stack.Screen name="(tabs)" />
            </Stack>
          </OnboardingGate>
        </VehicleDataProvider>
      </OnboardingProvider>
    </ProfileSyncProvider>
  );
}
