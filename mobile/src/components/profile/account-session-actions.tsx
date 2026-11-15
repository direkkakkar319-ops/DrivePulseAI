// Reuse Firebase sign-out and existing profile-sync retry; no manual navigation or database deletion.
import { AppButton } from '@/components/ui/app-button';
import { AppCard } from '@/components/ui/app-card';
import { AppText } from '@/components/ui/app-text';
import { UsernameSaveNotice } from '@/components/username-save-notice';
import { useAuthStore } from '@/store/authStore';
import { useProfileSync } from '@/hooks/use-profile-sync';
import { useAccountAction } from '@/hooks/use-account-action';
import { authService } from '@/api/auth';
import { authErrorMessage } from '@/api/auth-errors';
import { ActionFeedback } from './action-feedback';

export function AccountSessionActions() {
  const { user } = useAuthStore();
  const sync = useProfileSync();
  const action = useAccountAction(authErrorMessage);
  return <>
    <UsernameSaveNotice />
    <AppCard>
      <AppText variant="subtitle">Account synchronization</AppText>
      <AppText tone="secondary">{sync.message}</AppText>
      {sync.failed && <AppButton title="Retry account sync" variant="secondary" onPress={sync.retry} disabled={action.busy} />}
    </AppCard>
    <ActionFeedback error={action.error} message={action.message} />
    <AppButton title="Log out" variant="secondary" loading={action.busy} disabled={!user}
      onPress={() => { void action.run(() => authService.signOut()); }} />
    <AppText variant="caption" tone="secondary">Logging out ends this session. Your saved profile and vehicles are kept.</AppText>
  </>;
}
