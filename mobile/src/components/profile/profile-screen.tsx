// Profile uses the shared account snapshot and Firebase identity, with no duplicate profile store.
import { StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import { AppButton } from '@/components/ui/app-button';
import { AppCard } from '@/components/ui/app-card';
import { AppDataState } from '@/components/ui/app-data-state';
import { AppHeader } from '@/components/ui/app-header';
import { AppScreen } from '@/components/ui/app-screen';
import { AppStatus } from '@/components/ui/app-status';
import { AppText } from '@/components/ui/app-text';
import { UsernameSaveNotice } from '@/components/username-save-notice';
import { useAuthStore } from '@/store/authStore';
import { useOnboarding } from '@/store/onboardingStore';
import { profileDisplayName } from '@/hooks/use-profile-onboarding';
import { ProfileAvatar } from './profile-avatar';

export function ProfileScreen({ onBack }: { onBack?: () => void } = {}) {
  const { user } = useAuthStore();
  const { resource, reload, saving } = useOnboarding();
  const router = useRouter();
  const name = profileDisplayName({ uid: user?.uid ?? '', displayName: user?.displayName ?? null, email: user?.email ?? null },
    resource.status === 'ready' ? resource.data.full_name ?? '' : '');
  return <AppScreen edges={['top', 'left', 'right']}>
    <AppHeader title="Profile" subtitle="Manage your account and preferences" onBack={onBack} />
    <UsernameSaveNotice />
    {resource.status === 'ready' ? <AppCard style={styles.identity}>
      <ProfileAvatar name={name} />
      <AppText variant="title">{name}</AppText>
      <AppText tone="secondary" selectable>{user?.email?.trim() || 'Email unavailable'}</AppText>
      <AppStatus label={user?.emailVerified ? 'Email verified' : 'Email not verified'} tone={user?.emailVerified ? 'success' : 'warning'} />
      <AppButton title="Edit Profile" variant="secondary" disabled={saving || !user}
        onPress={() => router.push('/(main)/edit-profile')} />
    </AppCard> : <AppDataState status={resource.status} title={resource.status === 'error' ? 'Could not load profile' : 'Loading profile'}
      message={resource.status === 'error' ? resource.message : undefined} onRetry={() => { void reload(); }} retryLabel="Retry" />}
    <AppCard>
      <AppButton title="My Garage" icon="car" variant="text" onPress={() => router.navigate('/(main)/(tabs)/vehicles')} />
      <AppButton title="Security" variant="text" onPress={() => router.push('/(main)/security')} />
      <AppButton title="App Settings" variant="text" onPress={() => router.push('/(main)/settings')} />
    </AppCard>
  </AppScreen>;
}
const styles = StyleSheet.create({ identity: { alignItems: 'center' } });
