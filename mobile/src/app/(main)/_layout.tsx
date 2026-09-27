import { Stack } from 'expo-router';

export default function MainLayout() {
  return (
    <Stack screenOptions={{
      headerStyle: { backgroundColor: '#111' },
      headerTintColor: '#fff',
      contentStyle: { backgroundColor: '#000' }
    }}>
      <Stack.Screen name="dashboard" options={{ title: 'Your account' }} />
      <Stack.Screen name="vehicle/[id]" options={{ title: 'Vehicle Details' }} />
      <Stack.Screen name="report/[id]" options={{ title: 'Maintenance Report' }} />
    </Stack>
  );
}
