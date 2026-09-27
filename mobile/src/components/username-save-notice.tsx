// Retry a failed profile write without recreating an already-created account.
import { useState } from 'react';
import { useAuthStore } from '@/store/authStore';
import { authErrorMessage } from '@/api/auth-errors';
import { AuthButton, AuthMessage } from './auth-form';

export function UsernameSaveNotice() {
  const { usernameSavePending, retryUsername } = useAuthStore();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  if (!usernameSavePending) return null;
  async function retry() {
    setBusy(true);
    setError('');
    try { await retryUsername(); }
    catch (failure) { setError(authErrorMessage(failure)); }
    finally { setBusy(false); }
  }
  return <>
    <AuthMessage message="Your account was created, but your username could not be saved. Retry before closing the app. You can still log in with your email and password." error />
    <AuthMessage message={error} error />
    <AuthButton title="Retry saving username" onPress={retry} loading={busy} secondary />
  </>;
}
