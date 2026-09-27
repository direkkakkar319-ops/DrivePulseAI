// Email/password account creation, sign-in, and password recovery using Firebase.
import { useState } from 'react';
import { authService } from '@/api/auth';
import { authErrorMessage } from '@/api/auth-errors';
import { googleAvailable } from '@/auth/google';
import { AuthButton, AuthForm, AuthInput, AuthMessage, AuthPasswordInput } from '@/components/auth-form';
import { useAuthStore } from '@/store/authStore';

type Mode = 'login' | 'signup' | 'reset';

export default function LoginScreen() {
  const { createAccount } = useAuthStore();
  const [mode, setMode] = useState<Mode>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [username, setUsername] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  function changeMode(next: Mode) {
    setMode(next);
    setPassword('');
    setError('');
    setMessage('');
  }

  async function submit() {
    if (busy) return;
    setError('');
    setMessage('');
    if (!email.trim() || (mode !== 'reset' && !password)) {
      setError('Enter your email' + (mode === 'reset' ? '.' : ' and password.'));
      return;
    }
    if (mode === 'signup' && !username.trim()) {
      setError('Enter a username.');
      return;
    }
    setBusy(true);
    try {
      if (mode === 'reset') {
        await authService.resetPassword(email);
        setMessage('If an account exists for this email, a password-reset link has been sent. Check your inbox and spam folder.');
      } else if (mode === 'signup') {
        await createAccount(email, password, username.trim());
      } else {
        await authService.signIn(email, password);
      }
      // Auth state, rather than a button press, controls navigation.
      setPassword('');
    } catch (failure) {
      setError(authErrorMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  async function googleLogin() {
    if (busy) return;
    setBusy(true);
    setError('');
    setMessage('');
    try { await authService.signInWithGoogle(); }
    catch (failure) { setError(authErrorMessage(failure)); }
    finally { setBusy(false); }
  }

  const title = mode === 'signup' ? 'Create your account' : mode === 'reset' ? 'Reset your password' : 'Welcome back';
  return (
    <AuthForm title={title} subtitle={mode === 'signup' ? 'Sign up with your email. You will verify it before entering the app.' : mode === 'reset' ? 'Enter your account email to request a reset link.' : 'Log in to your DrivePulseAI account.'}>
      {mode === 'signup' && <AuthInput label="Username" value={username} onChangeText={setUsername} editable={!busy} autoCapitalize="none" autoCorrect={false} autoComplete="username-new" />}
      <AuthInput label="Email" value={email} onChangeText={setEmail} editable={!busy} keyboardType="email-address" autoCapitalize="none" autoCorrect={false} autoComplete="email" />
      {mode !== 'reset' && <AuthPasswordInput key={mode} value={password} onChangeText={setPassword} editable={!busy} autoComplete={mode === 'signup' ? 'new-password' : 'current-password'} />}
      <AuthMessage message={error} error />
      <AuthMessage message={message} />
      <AuthButton title={mode === 'signup' ? 'Create account' : mode === 'reset' ? 'Send reset link' : 'Log in'} onPress={submit} loading={busy} />
      {mode === 'login' && googleAvailable && <AuthButton title="Continue with Google" secondary disabled={busy} onPress={googleLogin} />}
      {mode === 'login' && <AuthButton title="Forgot password?" secondary disabled={busy} onPress={() => changeMode('reset')} />}
      <AuthButton title={mode === 'login' ? 'Create an account' : 'Back to login'} secondary disabled={busy} onPress={() => changeMode(mode === 'login' ? 'signup' : 'login')} />
    </AuthForm>
  );
}
