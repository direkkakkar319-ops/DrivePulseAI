// Keep all product screens inside the existing verified-account route guard.
import { Stack } from 'expo-router';
import { VehicleDataProvider } from '@/store/vehicleDataStore';
import { ProfileSyncProvider } from '@/hooks/use-profile-sync';
import { useAuthStore } from '@/store/authStore';
import { colors } from '@/theme/colors';
export default function MainLayout() {
  const { user } = useAuthStore();
  return (
    <ProfileSyncProvider key={user?.uid}>
      <VehicleDataProvider>
        <Stack
          screenOptions={{
            headerShown: false,
            contentStyle: { backgroundColor: colors.background },
          }}
        >
          <Stack.Screen name="(tabs)" />
        </Stack>
      </VehicleDataProvider>
    </ProfileSyncProvider>
  );
}
