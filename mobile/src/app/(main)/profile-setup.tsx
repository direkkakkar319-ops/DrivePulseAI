// Persist optional app profile data separately from Firebase account identity.
import { useState } from 'react';
import { ProfileOnboardingForm } from '@/components/profile-onboarding';
import { useProfileOnboarding } from '@/hooks/use-profile-onboarding';
import { pickProfilePhoto } from '@/lib/profile-photo';
import { useAuthStore } from '@/store/authStore';
import type { ProfileIdentity } from '@/types/profile-onboarding';
import { useOnboarding } from '@/store/onboardingStore';
import { authService } from '@/api/auth';
import { authErrorMessage } from '@/api/auth-errors';

export default function ProfileSetupRoute() {
  const { user } = useAuthStore();
  // The parent route guard handles navigation; never render another identity's draft.
  if (!user?.emailVerified) return null;
  return <ProfileSetup key={user.uid} identity={user} />;
}

function ProfileSetup({ identity }: { identity: ProfileIdentity }) {
  const account = useOnboarding();
  const savedName = account.resource.status === 'ready' ? account.resource.data.full_name : null;
  const form = useProfileOnboarding({ ...identity, displayName: savedName ?? identity.displayName }, pickProfilePhoto);
  const [error, setError] = useState('');
  async function save(skip: boolean) {
    setError('');
    try { await account.saveProfile({ full_name: skip ? null : form.draft.fullName.trim() || null,
      driving_licence: skip ? null : form.draft.drivingLicence }); }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not save your profile. Please try again.'); }
  }
  async function logout() {
    try { await authService.signOut(); } catch (failure) { setError(authErrorMessage(failure)); }
  }
  return <ProfileOnboardingForm {...form} saving={account.saving} submitError={error}
    onContinue={() => { void save(false); }} onSkip={() => { void save(true); }} onLogout={logout} />;
}
