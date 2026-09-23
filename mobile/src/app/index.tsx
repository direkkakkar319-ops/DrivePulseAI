// Entry route follows validated authentication state.
import { Redirect } from 'expo-router';
import { useAuthStore } from '@/store/authStore';
export default function Index() {
  const { isAuthenticated } = useAuthStore();
  return <Redirect href={isAuthenticated ? '/(main)' : '/(auth)/login'} />;
}
