// Show the verified account and logout while vehicle storage is unimplemented.
import { useEffect, useState } from 'react';
import { syncProfile } from '@/api/client';
import { authService } from '@/api/auth';
import { authErrorMessage } from '@/api/auth-errors';
import { AuthButton, AuthForm, AuthMessage } from '@/components/auth-form';
import { useAuthStore } from '@/store/authStore';
import { UsernameSaveNotice } from '@/components/username-save-notice';

export default function Dashboard() {
  const { user } = useAuthStore();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [syncState, setSyncState] = useState('Syncing your account…');
  const [syncFailed, setSyncFailed] = useState(false);
  const [retry, setRetry] = useState(0);
  const { uid, emailVerified, email, displayName } = user ?? {};
  useEffect(() => {
    if (!uid || !emailVerified) return;
    let active = true;
    // Ignore results from an old account or unmounted screen after logout.
    void Promise.resolve().then(async () => {
      if (!active) return;
      setSyncFailed(false);
      setSyncState('Syncing your account…');
      try {
        await syncProfile(uid);
        if (active) setSyncState('Your account is synced.');
      } catch (failure) {
        if (active) {
          setSyncFailed(true);
          setSyncState(failure instanceof Error ? failure.message : 'Could not sync your account.');
        }
      }
    });
    return () => { active = false; };
  }, [uid, emailVerified, email, displayName, retry]);
  async function logout() {
    setBusy(true);
    setError('');
    try { await authService.signOut(); }
    catch (failure) { setError(authErrorMessage(failure)); }
    finally { setBusy(false); }
  }
  return (
    <AuthForm title="You’re signed in" subtitle={user?.email ?? 'Your email is verified.'}>
      {user?.displayName && <AuthMessage message={`Welcome, ${user.displayName}`} />}
      <UsernameSaveNotice />
      <AuthMessage message={syncState} error={syncFailed} />
      {syncFailed && <AuthButton title="Retry account sync" secondary onPress={() => setRetry((value) => value + 1)} />}
      <AuthMessage message="Your account is ready. Vehicle features are still in development." />
      <AuthMessage message={error} error />
      <AuthButton title="Log out" onPress={logout} loading={busy} />
    </AuthForm>
  );
}
