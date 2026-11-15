// Reuse the existing Firebase session/refresh flow inside the protected product stack.
import { SecurityScreen } from '@/components/profile/security-screen';
import { useAuthStore } from '@/store/authStore';
import { useProfileBack } from '@/hooks/use-profile-back';

export default function SecurityRoute() {
  const { user, refreshUser } = useAuthStore();
  const back = useProfileBack();
  return <SecurityScreen key={user?.uid ?? 'signed-out'} user={user} refreshUser={refreshUser} onBack={back} />;
}
