// Show the verified account and logout while vehicle storage is unimplemented.
import { useState } from 'react';
import { authService } from '@/api/auth';
import { authErrorMessage } from '@/api/auth-errors';
import { AuthButton, AuthForm, AuthMessage } from '@/components/auth-form';
import { useAuthStore } from '@/store/authStore';
import { UsernameSaveNotice } from '@/components/username-save-notice';

export default function Dashboard() {
  const { user } = useAuthStore();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
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
      <AuthMessage message="Your account is ready. Vehicle features are still in development." />
      <AuthMessage message={error} error />
      <AuthButton title="Log out" onPress={logout} loading={busy} />
    </AuthForm>
  );
}
