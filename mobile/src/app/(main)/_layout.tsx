import { Stack } from 'expo-router';
import { Alert, Pressable, Text } from 'react-native';
import { useState } from 'react';
import { authService } from '@/api/auth';
import { authErrorMessage } from '@/api/auth-errors';

export default function MainLayout() {
  const [busy, setBusy] = useState(false);
  async function signOut() {
    setBusy(true);
    try { await authService.signOut(); }
    catch (error) { Alert.alert('Could not log out', authErrorMessage(error)); }
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
      <Stack.Screen name="dashboard" options={{ title: 'Your account' }} />
      <Stack.Screen name="vehicle/[id]" options={{ title: 'Vehicle Details' }} />
      <Stack.Screen name="report/[id]" options={{ title: 'Maintenance Report' }} />
    </Stack>
  );
}
