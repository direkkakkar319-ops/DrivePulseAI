// Root session provider and protected navigation.
import { Stack, DarkTheme, ThemeProvider } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { ActivityIndicator, View } from 'react-native';
import { AuthProvider, useAuthStore } from '@/store/authStore';
export default function RootLayout() {
  return <AuthProvider><Navigation /></AuthProvider>;
}
function Navigation() {
  const { isLoading, isAuthenticated } = useAuthStore();
  if (isLoading) return <View style={{ flex: 1, backgroundColor: '#111', justifyContent: 'center' }}>
    <ActivityIndicator accessibilityLabel="Restoring your session" />
  </View>;
  return <ThemeProvider value={DarkTheme}>
    <StatusBar style="light" />
    <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: '#000' } }}>
      <Stack.Screen name="index" />
      <Stack.Protected guard={!isAuthenticated}>
        <Stack.Screen name="(auth)" />
      </Stack.Protected>
      <Stack.Protected guard={isAuthenticated}>
        <Stack.Screen name="(main)" />
        <Stack.Screen name="explore" />
      </Stack.Protected>
    </Stack>
  </ThemeProvider>;
}
