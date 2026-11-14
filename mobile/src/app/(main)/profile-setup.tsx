// Opt-in, verified-account profile route; never inserted into existing login redirects.
import { useRouter } from 'expo-router';
import { ProfileOnboardingForm } from '@/components/profile-onboarding';
import { useProfileOnboarding } from '@/hooks/use-profile-onboarding';
import { pickProfilePhoto } from '@/lib/profile-photo';
import { useAuthStore } from '@/store/authStore';
import type { ProfileIdentity } from '@/types/profile-onboarding';

export default function ProfileSetupRoute() {
  const { user } = useAuthStore();
  // The parent route guard handles navigation; never render another identity's draft.
  if (!user?.emailVerified) return null;
  return <ProfileSetup key={user.uid} identity={user} />;
}

function ProfileSetup({ identity }: { identity: ProfileIdentity }) {
  const form = useProfileOnboarding(identity, pickProfilePhoto);
  const router = useRouter();
  // Phase 3.4 can persist form.result() before leaving, and record Skip separately.
  // This phase deliberately writes no profile or onboarding-completion state.
  const leave = () => router.replace('/(main)/dashboard');
  return <ProfileOnboardingForm {...form} onContinue={leave} onSkip={leave} />;
}
