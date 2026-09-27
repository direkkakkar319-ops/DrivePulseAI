// Android Firebase Auth adapter; the native SDK owns credentials and persistence.
import {
  createUserWithEmailAndPassword, getAuth, getIdToken, onIdTokenChanged,
  reload, sendEmailVerification, sendPasswordResetEmail,
  signInWithEmailAndPassword, signOut, updateProfile, type User,
} from '@react-native-firebase/auth';
import type { AuthService, AuthUser } from './auth.types';

function snapshot(user: User | null): AuthUser | null {
  return user ? { uid: user.uid, email: user.email, emailVerified: user.emailVerified, displayName: user.displayName } : null;
}

function requireUser(): User {
  const user = getAuth().currentUser;
  if (!user) throw new Error('Please sign in again.');
  return user;
}

const listeners = new Set<(user: AuthUser | null) => void>();
function publishCurrentUser() {
  const current = snapshot(getAuth().currentUser);
  listeners.forEach((listener) => listener(current));
}

export const authService: AuthService = {
  subscribe(listener) {
    const unsubscribe = onIdTokenChanged(getAuth(), (user) => listener(snapshot(user)));
    listeners.add(listener);
    return () => { listeners.delete(listener); unsubscribe(); };
  },
  async signIn(email, password) {
    await signInWithEmailAndPassword(getAuth(), email.trim(), password);
    // The SDK has updated currentUser when this resolves. Keep navigation in
    // sync even if the separate native token event is delayed.
    publishCurrentUser();
  },
  async signUp(email, password, username) {
    const { user } = await createUserWithEmailAndPassword(getAuth(), email.trim(), password);
    try {
      await updateProfile(user, { displayName: username.trim() });
    } catch {
      // Account creation already succeeded. Let the session-level UI offer a
      // profile retry even if the auth event has unmounted the signup screen.
      publishCurrentUser();
      return { uid: user.uid, profileSaved: false };
    }
    // Send from the verification screen so delivery failures can be retried
    // without accidentally trying to create the account again.
    publishCurrentUser();
    return { uid: user.uid, profileSaved: true };
  },
  async saveUsername(uid, username) {
    const user = requireUser();
    if (user.uid !== uid) throw new Error('The account has changed.');
    await updateProfile(user, { displayName: username.trim() });
    publishCurrentUser();
  },
  async sendVerification() {
    await sendEmailVerification(requireUser());
  },
  async refreshUser() {
    const user = requireUser();
    await reload(user);
    const current = getAuth().currentUser;
    if (!current || current.uid !== user.uid) return null;
    // Refresh the email_verified token claim as well as the local snapshot.
    await getIdToken(current, true);
    return snapshot(getAuth().currentUser);
  },
  async resetPassword(email) {
    try {
      await sendPasswordResetEmail(getAuth(), email.trim());
    } catch (error) {
      // Keep the UI response identical for existing and unknown addresses.
      if ((error as { code?: string }).code !== 'auth/user-not-found') throw error;
    }
  },
  async signOut() {
    await signOut(getAuth());
    publishCurrentUser();
  },
  async getToken(forceRefresh = false) {
    const user = requireUser();
    if (!user.emailVerified) throw new Error('Please verify your email first.');
    // Retrieve on demand: the SDK refreshes expired tokens; never cache JWTs in UI state.
    return getIdToken(user, forceRefresh);
  },
};
