// Persist edits through the existing shared onboarding account API, preserving all milestones.
import { AppDataState } from '@/components/ui/app-data-state';
import { AppHeader } from '@/components/ui/app-header';
import { AppScreen } from '@/components/ui/app-screen';
import { EditProfileForm } from '@/components/profile/edit-profile-form';
import { useAuthStore } from '@/store/authStore';
import { useOnboarding } from '@/store/onboardingStore';
import { profileDisplayName } from '@/hooks/use-profile-onboarding';
import { useProfileBack } from '@/hooks/use-profile-back';
import { pickProfilePhoto } from '@/lib/profile-photo';

export default function EditProfileRoute() {
  const { user } = useAuthStore();
  const account = useOnboarding();
  const back = useProfileBack();
  const { resource } = account;
  const identity = { uid: user?.uid ?? '', email: user?.email ?? null, displayName: user?.displayName ?? null };
  return <AppScreen keyboardAvoiding>
    <AppHeader title="Edit Profile" onBack={back} />
    {resource.status !== 'ready' ? <AppDataState status={resource.status}
      title={resource.status === 'error' ? 'Could not load profile' : 'Loading profile'}
      message={resource.status === 'error' ? resource.message : undefined} retryLabel="Retry" onRetry={() => { void account.reload(); }} />
      : user ? <EditProfileForm key={user.uid} identity={{ ...identity,
        displayName: profileDisplayName(identity, resource.data.full_name ?? '') }}
        pickPhoto={pickProfilePhoto} onCancel={back} onSave={name => account.saveProfile({
          full_name: name, driving_licence: resource.data.driving_licence,
        })} /> : <AppDataState status="error" title="Please sign in again" />}
  </AppScreen>;
}
