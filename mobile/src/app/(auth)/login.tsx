// Email/password account creation, sign-in, and password recovery using Firebase.
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import { authService } from '@/api/auth';
import { authErrorMessage } from '@/api/auth-errors';
import { googleAvailable } from '@/auth/google';
import { AuthScreen } from '@/components/auth-screen';
import { AppButton } from '@/components/ui/app-button';
import { AppStatus } from '@/components/ui/app-status';
import { AppText } from '@/components/ui/app-text';
import { AppTextField } from '@/components/ui/app-text-field';
import { colors, spacing } from '@/theme/tokens';
import { useAuthStore } from '@/store/authStore';

type Mode = 'login' | 'signup' | 'reset';

export default function LoginScreen() {
  const { createAccount } = useAuthStore();
  const params = useLocalSearchParams<{ mode?: string }>();
  const [mode, setMode] = useState<Mode>(params.mode === 'signup' ? 'signup' : 'login');
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
        setMessage(
          'If an account exists for this email, a password-reset link has been sent. Check your inbox and spam folder.',
        );
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
    try {
      await authService.signInWithGoogle();
    } catch (failure) {
      setError(authErrorMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  const title =
    mode === 'signup'
      ? 'Create your account'
      : mode === 'reset'
        ? 'Reset your password'
        : 'Welcome back';
  return (
    <AuthScreen
      title={title}
      subtitle={
        mode === 'signup'
          ? 'Sign up with your email. You will verify it before entering the app.'
          : mode === 'reset'
            ? 'Enter your account email to request a reset link.'
            : 'Log in to your DrivePulseAI account.'
      }
    >
      <View style={styles.fields}>
        {mode === 'signup' && (
          <AppTextField
            label="Username"
            value={username}
            onChangeText={setUsername}
            editable={!busy}
            autoCapitalize="none"
            autoCorrect={false}
            autoComplete="username-new"
          />
        )}
        <AppTextField
          label="Email"
          value={email}
          onChangeText={setEmail}
          editable={!busy}
          keyboardType="email-address"
          autoCapitalize="none"
          autoCorrect={false}
          autoComplete="email"
        />
        {mode !== 'reset' && (
          <AppTextField
            key={mode}
            label="Password"
            password
            value={password}
            onChangeText={setPassword}
            editable={!busy}
            autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
          />
        )}
        {mode === 'login' && (
          <AppButton title="Forgot password?" variant="text" disabled={busy}
            style={styles.forgot} onPress={() => changeMode('reset')} />
        )}
      </View>
      {!!error && <AppStatus label={error} tone="error" variant="notice" />}
      {!!message && <AppStatus label={message} tone="success" variant="notice" />}
      <View style={styles.actions}>
        <AppButton
          title={
            mode === 'signup' ? 'Create account' : mode === 'reset' ? 'Send reset link' : 'Log in'
          }
          onPress={submit}
          loading={busy}
        />
        {mode === 'login' && googleAvailable && (
          <>
            <View style={styles.dividerRow}>
              <View style={styles.divider} />
              <AppText variant="caption" tone="secondary">or</AppText>
              <View style={styles.divider} />
            </View>
            <AppButton title="Continue with Google" variant="secondary" disabled={busy} onPress={googleLogin} />
          </>
        )}
      </View>
      <View style={styles.switcher}>
        <AppText variant="label" tone="secondary">
          {mode === 'login' ? 'New to DrivePulse AI?' : mode === 'signup' ? 'Already have an account?' : 'Remember your password?'}
        </AppText>
        <AppButton
          title={mode === 'login' ? 'Create an account' : 'Back to login'}
          variant="text"
          disabled={busy}
          onPress={() => changeMode(mode === 'login' ? 'signup' : 'login')}
        />
      </View>
    </AuthScreen>
  );
}

const styles = StyleSheet.create({
  fields: { gap: spacing.md },
  actions: { gap: spacing.md },
  forgot: { alignSelf: 'flex-end' },
  switcher: { alignItems: 'center', gap: spacing.xxs },
  dividerRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  divider: { flex: 1, height: StyleSheet.hairlineWidth, backgroundColor: colors.border },
});
