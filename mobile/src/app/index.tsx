// Send cold starts to the screen allowed by the restored Firebase session.
import { Redirect } from 'expo-router';
import { useAuthStore } from '@/store/authStore';

export default function Index() {
  const { user } = useAuthStore();
  if (!user) return <Redirect href="/(auth)/login" />;
  if (!user.emailVerified) return <Redirect href="/verify-email" />;
  return <Redirect href="/(main)/dashboard" />;
}
