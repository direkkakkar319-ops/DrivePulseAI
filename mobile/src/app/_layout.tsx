// Restore authentication before rendering routes and protect all account screens.
import { Stack, DarkTheme, ThemeProvider } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';
import { AuthProvider, useAuthStore } from '@/store/authStore';

export default function RootLayout() {
  return (
    <AuthProvider>
      <RootNavigator />
    </AuthProvider>
  );
}

export function RootNavigator() {
  const { user, initializing, startupError } = useAuthStore();
  if (initializing || startupError) {
    return (
      <View style={styles.loading}>
        {startupError ? (
          <Text style={styles.error}>{startupError}</Text>
        ) : (
          <ActivityIndicator accessibilityLabel="Restoring your session" color="#a6f4c5" />
        )}
      </View>
    );
  }
  return (
    <ThemeProvider value={DarkTheme}>
      <StatusBar style="light" />
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: '#020d16' } }}>
        <Stack.Screen name="index" />
        <Stack.Protected guard={!user}>
          <Stack.Screen name="(auth)" />
        </Stack.Protected>
        <Stack.Protected guard={!!user && !user.emailVerified}>
          <Stack.Screen name="verify-email" />
        </Stack.Protected>
        <Stack.Protected guard={!!user?.emailVerified}>
          <Stack.Screen name="(main)" />
          <Stack.Screen name="explore" />
        </Stack.Protected>
      </Stack>
    </ThemeProvider>
  );
}

const styles = StyleSheet.create({
  loading: {
    flex: 1,
    backgroundColor: '#090d10',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  },
  error: { color: '#edf2f3', textAlign: 'center', lineHeight: 24 },
});
