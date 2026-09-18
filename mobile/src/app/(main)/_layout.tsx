import { Stack } from 'expo-router';
import { Alert, Pressable, Text } from 'react-native';
import { useState } from 'react';
import { useAuthStore } from '@/store/authStore';

export default function MainLayout() {
  const { logout } = useAuthStore();
  const [busy, setBusy] = useState(false);
  async function signOut() {
    setBusy(true);
    try { await logout(); }
    catch (error) { Alert.alert('Could not log out', error instanceof Error ? error.message : 'Please try again.'); }
    finally { setBusy(false); }
  }
  return (
    <Stack screenOptions={{
      headerStyle: { backgroundColor: '#111' },
      headerTintColor: '#fff',
      headerRight: () => <Pressable accessibilityRole="button" disabled={busy} onPress={() => void signOut()}>
        <Text style={{ color: '#84baff', padding: 8 }}>{busy ? 'Logging out…' : 'Log out'}</Text>
      </Pressable>,
      contentStyle: { backgroundColor: '#000' }
    }}>
      <Stack.Screen name="index" options={{ title: 'Vehicles' }} />
      <Stack.Screen name="vehicle/[id]" options={{ title: 'Vehicle Details' }} />
      <Stack.Screen name="report/[id]" options={{ title: 'Maintenance Report' }} />
    </Stack>
  );
}
