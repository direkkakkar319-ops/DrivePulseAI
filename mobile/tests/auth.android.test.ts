// Exercise the Firebase boundary without contacting the real project or sending email.
import { authService } from '../src/api/auth.android';
import {
  createUserWithEmailAndPassword, getAuth, getIdToken, onIdTokenChanged,
  reload, sendEmailVerification, sendPasswordResetEmail,
  signInWithEmailAndPassword, signOut, updateProfile,
} from '@react-native-firebase/auth';

jest.mock('@react-native-firebase/auth', () => ({
  getAuth: jest.fn(), getIdToken: jest.fn(), onIdTokenChanged: jest.fn(),
  reload: jest.fn(), sendEmailVerification: jest.fn(), sendPasswordResetEmail: jest.fn(),
  signInWithEmailAndPassword: jest.fn(), createUserWithEmailAndPassword: jest.fn(), signOut: jest.fn(), updateProfile: jest.fn(),
}));

const user = { uid: 'test-user', email: 'user@example.com', emailVerified: false, displayName: null };
let auth: { currentUser: typeof user | null };

beforeEach(() => {
  jest.resetAllMocks();
  auth = { currentUser: { ...user } };
  (getAuth as jest.Mock).mockReturnValue(auth);
  (createUserWithEmailAndPassword as jest.Mock).mockResolvedValue({ user: auth.currentUser });
});

it('trims email but preserves password exactly for login and signup', async () => {
  await authService.signIn(' user@example.com ', ' password ');
  await authService.signUp(' user@example.com ', ' password ', ' Driver ');
  expect(signInWithEmailAndPassword).toHaveBeenCalledWith(auth, 'user@example.com', ' password ');
  expect(createUserWithEmailAndPassword).toHaveBeenCalledWith(auth, 'user@example.com', ' password ');
  expect(updateProfile).toHaveBeenCalledWith(auth.currentUser, { displayName: 'Driver' });
});

it('does not issue API tokens for signed-out or unverified accounts', async () => {
  await expect(authService.getToken()).rejects.toThrow('verify');
  auth.currentUser = null;
  await expect(authService.getToken()).rejects.toThrow('sign in');
  expect(getIdToken).not.toHaveBeenCalled();
});

it('reloads verification and forces a fresh token before reporting success', async () => {
  (reload as jest.Mock).mockImplementation(async () => { auth.currentUser = { ...user, emailVerified: true }; });
  const updated = await authService.refreshUser();
  expect(updated?.emailVerified).toBe(true);
  expect(getIdToken).toHaveBeenCalledWith(auth.currentUser, true);
  (getIdToken as jest.Mock).mockResolvedValue('fresh-token');
  await expect(authService.getToken()).resolves.toBe('fresh-token');
});

it('does not restore a user who signed out while verification was refreshing', async () => {
  (reload as jest.Mock).mockImplementation(async () => { auth.currentUser = null; });
  await expect(authService.refreshUser()).resolves.toBeNull();
  expect(getIdToken).not.toHaveBeenCalled();
});

it('does not disclose an unknown email during password reset but surfaces network failures', async () => {
  (sendPasswordResetEmail as jest.Mock).mockRejectedValueOnce({ code: 'auth/user-not-found' });
  await expect(authService.resetPassword(' nobody@example.com ')).resolves.toBeUndefined();
  expect(sendPasswordResetEmail).toHaveBeenCalledWith(auth, 'nobody@example.com');
  const failure = { code: 'auth/network-request-failed' };
  (sendPasswordResetEmail as jest.Mock).mockRejectedValueOnce(failure);
  await expect(authService.resetPassword('user@example.com')).rejects.toEqual(failure);
});

it('allows verification delivery to be retried and delegates logout to Firebase', async () => {
  (sendEmailVerification as jest.Mock).mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce(undefined);
  await expect(authService.sendVerification()).rejects.toThrow('offline');
  await authService.sendVerification();
  expect(sendEmailVerification).toHaveBeenCalledTimes(2);
  await authService.signOut();
  expect(signOut).toHaveBeenCalledWith(auth);
});

it('subscribes to restored sessions and forwards logout without exposing tokens', () => {
  const unsubscribe = jest.fn();
  (onIdTokenChanged as jest.Mock).mockReturnValue(unsubscribe);
  const listener = jest.fn();
  const stop = authService.subscribe(listener);
  const callback = (onIdTokenChanged as jest.Mock).mock.calls[0][1];
  callback({ ...user, refreshToken: 'never-in-react-state' });
  expect(listener).toHaveBeenLastCalledWith(user);
  callback(null);
  expect(listener).toHaveBeenLastCalledWith(null);
  stop();
  expect(unsubscribe).toHaveBeenCalledTimes(1);
});


it('publishes logout then a successful re-login even before a native token event', async () => {
  (onIdTokenChanged as jest.Mock).mockReturnValue(jest.fn());
  const listener = jest.fn();
  const stop = authService.subscribe(listener);
  (signOut as jest.Mock).mockImplementation(async () => { auth.currentUser = null; });
  (signInWithEmailAndPassword as jest.Mock).mockImplementation(async () => {
    auth.currentUser = { ...user };
    return { user: auth.currentUser };
  });
  await authService.signOut();
  expect(listener).toHaveBeenLastCalledWith(null);
  await authService.signIn(user.email, 'unchanged-password');
  expect(listener).toHaveBeenLastCalledWith(user);
  expect(createUserWithEmailAndPassword).not.toHaveBeenCalled();
  stop();
  listener.mockClear();
  await authService.signOut();
  expect(listener).not.toHaveBeenCalled();
});

it('reports partial signup and retries only the username write', async () => {
  (updateProfile as jest.Mock).mockRejectedValueOnce({ code: 'auth/network-request-failed' });
  await expect(authService.signUp(user.email, 'password', 'Driver')).resolves.toEqual({ uid: user.uid, profileSaved: false });
  await authService.saveUsername(user.uid, 'Driver');
  expect(createUserWithEmailAndPassword).toHaveBeenCalledTimes(1);
  expect(updateProfile).toHaveBeenCalledTimes(2);
  await expect(authService.saveUsername('another-account', 'Driver')).rejects.toThrow('account has changed');
  expect(updateProfile).toHaveBeenCalledTimes(2);
});
