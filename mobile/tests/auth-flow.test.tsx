// Check account UI and route guards with a controllable authentication boundary.
import { act, fireEvent, render, screen } from '@testing-library/react-native';
import type { AuthUser } from '../src/api/auth.types';
import { authService } from '../src/api/auth';
import { syncProfile } from '../src/api/client';
import { AuthProvider } from '../src/store/authStore';
import { RootNavigator } from '../src/app/_layout';
import LoginScreen from '../src/app/(auth)/login';
import Dashboard from '../src/app/(main)/dashboard';
import { UsernameSaveNotice } from '../src/components/username-save-notice';
import VerifyEmailScreen from '../src/app/verify-email';

jest.mock('../src/api/client', () => ({ syncProfile: jest.fn() }));
jest.mock('../src/auth/google', () => ({ googleAvailable: true }));

jest.mock('../src/api/auth', () => ({ authService: {
  subscribe: jest.fn(), signIn: jest.fn(), signInWithGoogle: jest.fn(), signUp: jest.fn(), saveUsername: jest.fn(),
  resetPassword: jest.fn(), sendVerification: jest.fn(), refreshUser: jest.fn(), signOut: jest.fn(),
} }));

// Test which screen groups our real root layout exposes, without native navigation.
jest.mock('expo-router', () => {
  const React = require('react');
  const { Text } = require('react-native');
  const Stack = ({ children }: { children: React.ReactNode }) => children;
  Stack.Protected = ({ guard, children }: { guard: boolean; children: React.ReactNode }) => guard ? children : null;
  Stack.Screen = ({ name }: { name: string }) => React.createElement(Text, null, `route:${name}`);
  return { Stack, DarkTheme: {}, ThemeProvider: ({ children }: { children: React.ReactNode }) => children };
});

let notify: (user: AuthUser | null) => void;
const unverified = { uid: 'test-user', email: 'user@example.com', emailVerified: false, displayName: null };

beforeEach(() => {
  jest.resetAllMocks();
  (authService.subscribe as jest.Mock).mockImplementation((listener) => { notify = listener; return jest.fn(); });
});

it('waits for restoration and gates routes for logged-out, unverified, verified, and logged-out-again states', async () => {
  await render(<AuthProvider><RootNavigator /></AuthProvider>);
  expect(screen.getByLabelText('Restoring your session')).toBeTruthy();
  expect(screen.queryByText('route:(main)')).toBeNull();
  await act(async () => notify(null));
  expect(screen.getByText('route:(auth)')).toBeTruthy();
  expect(screen.queryByText('route:(main)')).toBeNull();
  await act(async () => notify(unverified));
  expect(screen.getByText('route:verify-email')).toBeTruthy();
  expect(screen.queryByText('route:(auth)')).toBeNull();
  expect(screen.queryByText('route:(main)')).toBeNull();
  await act(async () => notify({ ...unverified, emailVerified: true }));
  expect(screen.getByText('route:(main)')).toBeTruthy();
  expect(screen.queryByText('route:verify-email')).toBeNull();
  await act(async () => notify(null));
  expect(screen.queryByText('route:(main)')).toBeNull();
});

it('keeps all routes closed if authentication initialization fails', async () => {
  (authService.subscribe as jest.Mock).mockImplementation(() => { throw new Error('configuration'); });
  await render(<AuthProvider><RootNavigator /></AuthProvider>);
  expect(screen.getByText(/Open the Android development build/)).toBeTruthy();
  expect(screen.queryByText('route:(main)')).toBeNull();
});

it('shows a failed login instead of navigating past authentication', async () => {
  (authService.signIn as jest.Mock).mockRejectedValue({ code: 'auth/invalid-credential' });
  await render(<AuthProvider><LoginScreen /></AuthProvider>);
  await fireEvent.changeText(screen.getByLabelText('Email'), 'user@example.com');
  await fireEvent.changeText(screen.getByLabelText('Password'), 'incorrect');
  await fireEvent.press(screen.getByText('Log in'));
  expect(await screen.findByText('The email or password is incorrect.')).toBeTruthy();
  expect(authService.signIn).toHaveBeenCalledWith('user@example.com', 'incorrect');
});

it('enters protected routes only after Google establishes a verified Firebase session', async () => {
  (authService.signInWithGoogle as jest.Mock).mockImplementation(async () => {
    notify({ ...unverified, emailVerified: true });
  });
  await render(<AuthProvider><LoginScreen /><RootNavigator /></AuthProvider>);
  await act(async () => notify(null));
  await fireEvent.press(screen.getByText('Continue with Google'));
  expect(authService.signInWithGoogle).toHaveBeenCalledTimes(1);
  expect(screen.getByText('route:(main)')).toBeTruthy();
  expect(authService.signIn).not.toHaveBeenCalled();
});

it('keeps routes closed after Google cancellation or an account conflict', async () => {
  (authService.signInWithGoogle as jest.Mock).mockResolvedValueOnce(undefined)
    .mockRejectedValueOnce({ code: 'auth/account-exists-with-different-credential' });
  await render(<AuthProvider><LoginScreen /><RootNavigator /></AuthProvider>);
  await act(async () => notify(null));
  await fireEvent.press(screen.getByText('Continue with Google'));
  expect(screen.queryByText('route:(main)')).toBeNull();
  await fireEvent.press(screen.getByText('Continue with Google'));
  expect(await screen.findByText(/Use your existing sign-in method/)).toBeTruthy();
  expect(screen.queryByText('route:(main)')).toBeNull();
});

it('requires a username and submits exactly the three signup fields', async () => {
  (authService.signUp as jest.Mock).mockResolvedValue({ uid: unverified.uid, profileSaved: true });
  await render(<AuthProvider><LoginScreen /></AuthProvider>);
  await fireEvent.press(screen.getByText('Create an account'));
  expect(screen.queryByLabelText('Confirm password')).toBeNull();
  await fireEvent.changeText(screen.getByLabelText('Email'), 'user@example.com');
  await fireEvent.changeText(screen.getByLabelText('Password'), 'password-one');
  await fireEvent.press(screen.getByText('Create account'));
  expect(screen.getByText('Enter a username.')).toBeTruthy();
  expect(authService.signUp).not.toHaveBeenCalled();
  await fireEvent.changeText(screen.getByLabelText('Username'), ' Driver ');
  await fireEvent.press(screen.getByText('Create account'));
  expect(authService.signUp).toHaveBeenCalledWith('user@example.com', 'password-one', 'Driver');
});

it('toggles password visibility without changing its value and hides it on mode changes', async () => {
  await render(<AuthProvider><LoginScreen /></AuthProvider>);
  await fireEvent.changeText(screen.getByLabelText('Password'), ' secret ');
  expect(screen.getByLabelText('Password').props.secureTextEntry).toBe(true);
  await fireEvent.press(screen.getByLabelText('Show password'));
  expect(screen.getByLabelText('Password').props.secureTextEntry).toBe(false);
  expect(screen.getByLabelText('Password').props.value).toBe(' secret ');
  await fireEvent.press(screen.getByLabelText('Hide password'));
  expect(screen.getByLabelText('Password').props.secureTextEntry).toBe(true);
  await fireEvent.press(screen.getByLabelText('Show password'));
  await fireEvent.press(screen.getByText('Create an account'));
  expect(screen.getByLabelText('Password').props.secureTextEntry).toBe(true);
  expect(screen.getByLabelText('Password').props.value).toBe('');
});

it('offers password recovery without requesting a password', async () => {
  (authService.resetPassword as jest.Mock).mockResolvedValue(undefined);
  await render(<AuthProvider><LoginScreen /></AuthProvider>);
  await fireEvent.press(screen.getByText('Forgot password?'));
  expect(screen.queryByLabelText('Password')).toBeNull();
  await fireEvent.changeText(screen.getByLabelText('Email'), 'user@example.com');
  await fireEvent.press(screen.getByText('Send reset link'));
  expect(await screen.findByText(/If an account exists/)).toBeTruthy();
});

it('keeps verification pending until Firebase confirms it', async () => {
  (authService.refreshUser as jest.Mock).mockResolvedValue(unverified);
  await render(<AuthProvider><VerifyEmailScreen /><RootNavigator /></AuthProvider>);
  await act(async () => notify(unverified));
  await fireEvent.press(screen.getByText('I have verified my email'));
  expect(await screen.findByText(/Your email is not verified yet/)).toBeTruthy();
  expect(screen.queryByText('route:(main)')).toBeNull();
  (authService.refreshUser as jest.Mock).mockResolvedValue({ ...unverified, emailVerified: true });
  await fireEvent.press(screen.getByText('I have verified my email'));
  expect(await screen.findByText('route:(main)')).toBeTruthy();
});


it('keeps profile-save failures visible after signup navigation and retries safely', async () => {
  (authService.signUp as jest.Mock).mockImplementation(async () => {
    notify(unverified);
    return { uid: unverified.uid, profileSaved: false };
  });
  await render(<AuthProvider><LoginScreen /><UsernameSaveNotice /></AuthProvider>);
  await fireEvent.press(screen.getByText('Create an account'));
  await fireEvent.changeText(screen.getByLabelText('Username'), 'Driver');
  await fireEvent.changeText(screen.getByLabelText('Email'), unverified.email);
  await fireEvent.changeText(screen.getByLabelText('Password'), 'password-one');
  await fireEvent.press(screen.getByText('Create account'));
  expect(await screen.findByText(/Your account was created, but/)).toBeTruthy();
  await fireEvent.press(screen.getByText('Retry saving username'));
  expect(authService.saveUsername).toHaveBeenCalledWith(unverified.uid, 'Driver');
  expect(screen.queryByText('Retry saving username')).toBeNull();
  expect(authService.signUp).toHaveBeenCalledTimes(1);
});

it('allows the same verified account to log in after using the logout button', async () => {
  const verified = { ...unverified, emailVerified: true };
  (authService.signOut as jest.Mock).mockImplementation(async () => notify(null));
  (authService.signIn as jest.Mock).mockImplementation(async () => notify(verified));
  await render(<AuthProvider><LoginScreen /><Dashboard /><RootNavigator /></AuthProvider>);
  await act(async () => notify(verified));
  await fireEvent.press(screen.getByText('Log out'));
  expect(screen.getByText('route:(auth)')).toBeTruthy();
  await fireEvent.changeText(screen.getByLabelText('Email'), verified.email);
  await fireEvent.changeText(screen.getByLabelText('Password'), 'same-password');
  await fireEvent.press(screen.getByText('Log in'));
  expect(authService.signIn).toHaveBeenCalledWith(verified.email, 'same-password');
  expect(screen.getByText('route:(main)')).toBeTruthy();
  expect(authService.signUp).not.toHaveBeenCalled();
});


it('keeps Firebase login available when the backend is offline and can retry profile sync', async () => {
  (syncProfile as jest.Mock).mockRejectedValueOnce(new Error('Account service is offline')).mockResolvedValueOnce({ firebase_uid: unverified.uid });
  await render(<AuthProvider><Dashboard /></AuthProvider>);
  await act(async () => notify({ ...unverified, emailVerified: true }));
  expect(await screen.findByText('Account service is offline')).toBeTruthy();
  expect(authService.signOut).not.toHaveBeenCalled();
  await fireEvent.press(screen.getByText('Retry account sync'));
  expect(await screen.findByText('Your account is synced.')).toBeTruthy();
  expect(syncProfile).toHaveBeenCalledWith(unverified.uid);
});
