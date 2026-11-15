// Functional account sync, sign-out, app information and privacy; no decorative settings.
import { AppHeader } from '@/components/ui/app-header';
import { AppScreen } from '@/components/ui/app-screen';
import { AccountSessionActions } from '@/components/profile/account-session-actions';
import { AppInformation } from '@/components/profile/app-information';
import { useProfileBack } from '@/hooks/use-profile-back';
import { useAuthStore } from '@/store/authStore';

export default function SettingsRoute() {
  const back = useProfileBack();
  const { user } = useAuthStore();
  return <AppScreen>
    <AppHeader title="App Settings" subtitle="App information and account controls" onBack={back} />
    <AppInformation />
    <AccountSessionActions key={user?.uid ?? 'signed-out'} />
  </AppScreen>;
}
