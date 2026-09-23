// Password signup/login and Google sign-in with validation and retry feedback.
import { useRef, useState } from 'react';
import { Text, TextInput, Pressable, StyleSheet, ScrollView,
  KeyboardAvoidingView, Platform } from 'react-native';
import { authApi } from '@/api/client';
import { getGoogleIdToken, googleAvailable } from '@/auth/google';
import { useAuthStore } from '@/store/authStore';

export default function LoginScreen() {
  const auth = useAuthStore();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [signup, setSignup] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pending = useRef(false);
  async function submit(google = false) {
    if (pending.current) return;
    setError(null);
    if (!google && (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim()) || !password)) {
      setError('Enter your email address and password.'); return;
    }
    if (!google && signup && (password.length < 12 || password !== confirm)) {
      setError('Use at least 12 characters and make sure both passwords match.'); return;
    }
    pending.current = true; setBusy(true);
    try {
      if (google) {
        const token = await getGoogleIdToken();
        if (token) await auth.login(await authApi.google(token));
      } else {
        const credentials = { email: email.trim().toLowerCase(), password };
        await auth.login(await (signup ? authApi.register(credentials) : authApi.login(credentials)));
      }
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Sign-in failed. Please try again.');
    } finally { pending.current = false; setBusy(false); }
  }
  return <KeyboardAvoidingView style={styles.container} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
    <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
      <Text style={styles.title}>DrivePulseAI</Text>
      <Text style={styles.subtitle}>{signup ? 'Create your account' : 'Welcome back'}</Text>
      <TextInput style={styles.input} accessibilityLabel="Email" placeholder="Email"
        placeholderTextColor="#aaa" autoCapitalize="none" autoCorrect={false}
        keyboardType="email-address" autoComplete="email" value={email}
        onChangeText={setEmail} editable={!busy} maxLength={254} />
      <TextInput style={styles.input} accessibilityLabel="Password" placeholder="Password"
        placeholderTextColor="#aaa" secureTextEntry value={password} onChangeText={setPassword}
        autoComplete={signup ? 'new-password' : 'current-password'} maxLength={128} editable={!busy} />
      {signup && <TextInput style={styles.input} accessibilityLabel="Confirm password"
        placeholder="Confirm password" placeholderTextColor="#aaa" secureTextEntry
        value={confirm} onChangeText={setConfirm} maxLength={128} editable={!busy} />}
      {signup && <Text style={styles.hint}>Use at least 12 characters.</Text>}
      {(error || auth.error) && <Text accessibilityRole="alert" style={styles.error}>{error || auth.error}</Text>}
      {auth.error && <Pressable accessibilityRole="button" disabled={busy} onPress={() => void auth.restore()}>
        <Text style={styles.link}>Retry saved session</Text>
      </Pressable>}
      <Pressable accessibilityRole="button" disabled={busy} style={[styles.button, busy && styles.disabled]}
        onPress={() => void submit()}>
        <Text style={styles.buttonText}>{busy ? 'Please wait…' : signup ? 'Create account' : 'Log in'}</Text>
      </Pressable>
      <Pressable accessibilityRole="button" disabled={busy} onPress={() => {
        setSignup(!signup); setError(null); setPassword(''); setConfirm('');
      }}><Text style={styles.link}>{signup ? 'Already have an account? Log in' : 'New here? Create an account'}</Text></Pressable>
      {googleAvailable && <Pressable accessibilityRole="button" disabled={busy}
        style={[styles.button, styles.google, busy && styles.disabled]} onPress={() => void submit(true)}>
        <Text style={styles.googleText}>Continue with Google</Text>
      </Pressable>}
    </ScrollView>
  </KeyboardAvoidingView>;
}
const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#111' },
  content: { flexGrow: 1, justifyContent: 'center', padding: 24, maxWidth: 480, width: '100%', alignSelf: 'center' },
  title: { fontSize: 32, fontWeight: 'bold', color: '#fff', textAlign: 'center' },
  subtitle: { color: '#bbb', textAlign: 'center', marginTop: 10, marginBottom: 32 },
  input: { backgroundColor: '#222', color: '#fff', padding: 16, borderRadius: 8, marginBottom: 14 },
  button: { backgroundColor: '#1769cf', padding: 16, borderRadius: 8, alignItems: 'center', marginTop: 8 },
  buttonText: { color: '#fff', fontWeight: 'bold', fontSize: 16 },
  link: { color: '#84baff', textAlign: 'center', paddingVertical: 18 },
  error: { color: '#ffaaaa', marginBottom: 12 },
  hint: { color: '#bbb', marginBottom: 12 },
  google: { backgroundColor: '#fff' },
  googleText: { color: '#111', fontWeight: 'bold', fontSize: 16 },
  disabled: { opacity: 0.5 },
});
