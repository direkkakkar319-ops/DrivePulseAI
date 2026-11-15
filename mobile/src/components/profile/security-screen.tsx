// Provider-aware Firebase security actions; no passwords or tokens enter screen state.
import { AppButton } from '@/components/ui/app-button';
import { AppCard } from '@/components/ui/app-card';
import { AppHeader } from '@/components/ui/app-header';
import { AppScreen } from '@/components/ui/app-screen';
import { AppStatus } from '@/components/ui/app-status';
import { AppText } from '@/components/ui/app-text';
import { authService } from '@/api/auth';
import { authErrorMessage } from '@/api/auth-errors';
import type { AuthUser } from '@/api/auth.types';
import { useAccountAction } from '@/hooks/use-account-action';
import { ActionFeedback } from './action-feedback';

export function SecurityScreen({ user, refreshUser, onBack }: {
  user: AuthUser | null;
  refreshUser: () => Promise<boolean>;
  onBack: () => void;
}) {
  const action = useAccountAction(authErrorMessage);
  const email = user?.email?.trim();
  const passwordAccount = Boolean(user?.providerIds?.includes('password'));
  const supported = Boolean(email && passwordAccount);
  return <AppScreen>
    <AppHeader title="Security" subtitle="Manage your sign-in security" onBack={onBack} />
    <AppCard>
      <AppText variant="subtitle">Email verification</AppText>
      <AppText tone="secondary" selectable>{email || 'Email unavailable'}</AppText>
      <AppStatus label={user?.emailVerified ? 'Email verified' : 'Email not verified'} tone={user?.emailVerified ? 'success' : 'warning'} />
      {!user?.emailVerified && (supported ? <>
        <AppButton title="Send verification email" disabled={action.busy} onPress={() => { void action.run(async () => {
          await authService.sendVerification(); return 'Verification email sent. Open the link in your inbox, then refresh verification status.';
        }); }} />
        <AppButton title="Refresh verification status" variant="secondary" disabled={action.busy} onPress={() => { void action.run(async () =>
          await refreshUser() ? 'Your email is verified.' : 'Your email is not verified yet. Open the email link first.'); }} />
      </> : <AppText tone="secondary">Verification emails are unavailable for this account here. Use your sign-in provider to manage verification.</AppText>)}
    </AppCard>
    <AppCard>
      <AppText variant="subtitle">Password reset</AppText>
      {supported ? <>
        <AppText tone="secondary">Send a reset link to your account email. Your password stays with Firebase Authentication.</AppText>
        <AppButton title="Send password-reset email" variant="secondary" disabled={action.busy}
          onPress={() => { void action.run(async () => {
            await authService.resetPassword(email!); return 'Password-reset email requested. Check your inbox and spam folder.';
          }); }} />
      </> : <AppText tone="secondary">{!email ? 'A password-reset email cannot be sent because this account has no email address.'
        : user?.providerIds === undefined ? 'Sign-in provider information is unavailable. Password reset cannot be offered safely here.'
          : 'This account does not use a Firebase password. Manage your password through your sign-in provider.'}</AppText>}
    </AppCard>
    {action.busy && <AppText accessibilityLiveRegion="polite" tone="secondary">Completing your security request…</AppText>}
    <ActionFeedback error={action.error} message={action.message} />
  </AppScreen>;
}
