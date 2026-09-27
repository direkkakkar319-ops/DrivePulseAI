// Keep unverified accounts out of the app and support retrying email delivery.
import { useState } from 'react';
import { authService } from '@/api/auth';
import { authErrorMessage } from '@/api/auth-errors';
import { AuthButton, AuthForm, AuthMessage } from '@/components/auth-form';
import { useAuthStore } from '@/store/authStore';
import { UsernameSaveNotice } from '@/components/username-save-notice';

export default function VerifyEmailScreen() {
  const { user, refreshUser } = useAuthStore();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  async function run(action: 'send' | 'check' | 'logout') {
    if (busy) return;
    setBusy(true);
    setError('');
    setMessage('');
    try {
      if (action === 'send') {
        await authService.sendVerification();
        setMessage('Verification email sent. Open the link in your inbox, then return here and tap “I have verified my email”. Check spam if it does not arrive.');
      } else if (action === 'check') {
        if (!(await refreshUser())) setMessage('Your email is not verified yet. Open the verification link first, then try again.');
      } else {
        await authService.signOut();
      }
    } catch (failure) {
      setError(authErrorMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthForm title="Verify your email" subtitle={`You are signed in as ${user?.email ?? 'your account'}. Send a verification email to confirm this address.`}>
      <UsernameSaveNotice />
      <AuthMessage message={error} error />
      <AuthMessage message={message} />
      <AuthButton title="Send verification email" onPress={() => run('send')} disabled={busy} />
      <AuthButton title="I have verified my email" onPress={() => run('check')} disabled={busy} secondary />
      <AuthButton title="Log out" onPress={() => run('logout')} disabled={busy} secondary />
    </AuthForm>
  );
}
