// Profile uses the existing account provider; Firebase and network services are test boundaries.
import { act, fireEvent, render, screen } from '@testing-library/react-native';
import Profile from '../src/app/(main)/(tabs)/account';
import EditProfile from '../src/app/(main)/edit-profile';
import Security from '../src/app/(main)/security';
import Settings from '../src/app/(main)/settings';
import { EditProfileForm } from '../src/components/profile/edit-profile-form';
import { ProfileAvatar } from '../src/components/profile/profile-avatar';
import { SecurityScreen } from '../src/components/profile/security-screen';
import { OnboardingProvider } from '../src/store/onboardingStore';
import { ProfileSyncProvider } from '../src/hooks/use-profile-sync';
import { authService } from '../src/api/auth';
import type { AuthUser } from '../src/api/auth.types';
import type { OnboardingApi, OnboardingState } from '../src/api/onboarding';
import type { ProfilePhoto } from '../src/types/profile-onboarding';
import { accountState, savedVehicle } from './onboarding-fixtures';

const alice: AuthUser = { uid: 'alice', displayName: 'Firebase name', email: 'alice@example.com', emailVerified: true, providerIds: ['password'] };
let mockUser: AuthUser | null = alice;
const mockRefresh = jest.fn(), mockNavigate = jest.fn(), mockPush = jest.fn(), mockBack = jest.fn(), mockReplace = jest.fn();
let mockCanGoBack = true;
jest.mock('../src/store/authStore', () => ({ useAuthStore: () => ({ user: mockUser, refreshUser: mockRefresh, usernameSavePending: false }) }));
jest.mock('expo-router', () => ({ useRouter: () => ({ navigate: mockNavigate, push: mockPush, back: mockBack, replace: mockReplace, canGoBack: () => mockCanGoBack }) }));
jest.mock('../src/api/auth', () => ({ authService: { getToken: jest.fn(), signOut: jest.fn(), resetPassword: jest.fn(), sendVerification: jest.fn() } }));
jest.mock('../src/api/client', () => ({ ...jest.requireActual('../src/api/client'), syncProfile: jest.fn(async () => ({ firebase_uid: 'alice' })) }));
jest.mock('../src/lib/profile-photo', () => ({ pickProfilePhoto: jest.fn(async () => null) }));
jest.mock('../src/lib/app-version', () => ({ appVersion: () => ({ installed: null, configured: '1.0.0-test' }) }));

function service(initial = accountState('home')) {
  let server = initial;
  const api: OnboardingApi = {
    load: jest.fn(async () => server),
    saveProfile: jest.fn(async (_uid, input) => { server = { ...server, full_name: input.full_name, driving_licence: input.driving_licence }; return server; }),
    saveFirstVehicle: jest.fn(), selectActive: jest.fn(),
  };
  return { api, current: () => server };
}
function Session({ api, page = 'profile', uid = 'alice' }: { api: OnboardingApi; page?: 'profile' | 'edit'; uid?: string }) {
  return <OnboardingProvider uid={uid} api={api}>{page === 'profile' ? <Profile /> : <EditProfile />}</OnboardingProvider>;
}
beforeEach(() => {
  jest.clearAllMocks(); mockUser = alice; mockCanGoBack = true;
  jest.mocked(authService.resetPassword).mockResolvedValue(undefined);
  jest.mocked(authService.sendVerification).mockResolvedValue(undefined);
  jest.mocked(authService.signOut).mockResolvedValue(undefined);
});

it('prefers the persisted name, uses Firebase email/verification, and puts Logout in Settings', async () => {
  await render(<Session api={service().api} />);
  expect(await screen.findByText('Saved app name')).toBeTruthy();
  expect(screen.getByRole('header', { name: 'Profile' })).toBeTruthy();
  expect(screen.getByText('Manage your account and preferences')).toBeTruthy();
  expect(screen.getByText(alice.email!)).toBeTruthy();
  expect(screen.getByText('Email verified')).toBeTruthy();
  expect(screen.getByLabelText('Profile initials SN')).toBeTruthy();
  expect(screen.queryByText('Firebase name')).toBeNull();
  expect(screen.queryByRole('button', { name: 'Log out' })).toBeNull();
  await fireEvent.press(screen.getByRole('button', { name: 'Edit Profile' }));
  expect(mockPush).toHaveBeenCalledWith('/(main)/edit-profile');
  await fireEvent.press(screen.getByRole('button', { name: 'Security' }));
  expect(mockPush).toHaveBeenCalledWith('/(main)/security');
  await fireEvent.press(screen.getByRole('button', { name: 'App Settings' }));
  expect(mockPush).toHaveBeenCalledWith('/(main)/settings');
  expect(mockNavigate).not.toHaveBeenCalled();
});

it.each([0, 1, 2])('opens My Garage with %s saved vehicles', async count => {
  const vehicles = count ? [savedVehicle(), ...(count === 2 ? [{ ...savedVehicle(), id: 'other-vehicle' }] : [])] : [];
  await render(<Session api={service({ ...accountState('home'), vehicles, active_vehicle_id: count ? savedVehicle().id : null }).api} />);
  await screen.findByText('Saved app name');
  await fireEvent.press(screen.getByRole('button', { name: 'My Garage' }));
  expect(mockNavigate).toHaveBeenCalledWith('/(main)/(tabs)/vehicles');
  expect(mockReplace).not.toHaveBeenCalled();
});

it.each([
  [{ ...alice, displayName: null }, null, 'alice'],
  [{ ...alice, displayName: null, email: null }, null, 'Your profile'],
  [alice, '  ', 'Firebase name'],
] as const)('uses an honest name/avatar fallback for missing fields', async (user, full_name, name) => {
  mockUser = user;
  await render(<Session api={service({ ...accountState('home'), full_name }).api} />);
  expect(await screen.findByText(name)).toBeTruthy();
  if (!user.email) expect(screen.getByText('Email unavailable')).toBeTruthy();
  expect(screen.getAllByRole('image')).toHaveLength(1);
});

it('shows loading/error and retries a real account load instead of displaying invented profile data', async () => {
  const { api } = service();
  let reject!: (error: Error) => void;
  jest.mocked(api.load).mockImplementationOnce(() => new Promise((_resolve, fail) => { reject = fail; }));
  await render(<Session api={api} />);
  expect(screen.getByLabelText('Loading profile')).toBeTruthy();
  await act(async () => reject(new Error('Account service offline')));
  expect(screen.getByText('Account service offline')).toBeTruthy();
  expect(screen.queryByRole('button', { name: 'Edit Profile' })).toBeNull();
  await fireEvent.press(screen.getByRole('button', { name: 'Retry' }));
  expect(await screen.findByText('Saved app name')).toBeTruthy();
});

it('saves only after confirmation, preserves licence/milestones/vehicles, and reloads the saved name', async () => {
  const { api, current } = service();
  const original = current();
  let finish!: () => void;
  const save = jest.mocked(api.saveProfile).getMockImplementation()!;
  jest.mocked(api.saveProfile).mockImplementationOnce(async (uid, input) => {
    await new Promise<void>(resolve => { finish = resolve; });
    // Apply the same persistent-service mock after releasing the response.
    return save(uid, input);
  });
  const view = await render(<Session api={api} page="edit" />);
  await screen.findByDisplayValue('Saved app name');
  await fireEvent.changeText(screen.getByLabelText('Full name'), '  Updated name  ');
  await fireEvent.press(screen.getByRole('button', { name: 'Save changes' }));
  expect(screen.queryByText('Profile name saved.')).toBeNull();
  expect(screen.getByRole('button', { name: 'Save changes' })).toBeDisabled();
  await fireEvent.press(screen.getByRole('button', { name: 'Save changes' }));
  expect(api.saveProfile).toHaveBeenCalledTimes(1);
  await act(async () => finish());
  expect(await screen.findByText('Profile name saved.')).toBeTruthy();
  expect(api.saveProfile).toHaveBeenCalledWith('alice', { full_name: 'Updated name', driving_licence: original.driving_licence });
  expect(current()).toEqual({ ...original, full_name: 'Updated name' });
  expect(api.saveFirstVehicle).not.toHaveBeenCalled();
  await view.unmount();
  await render(<Session api={api} />);
  expect(await screen.findByText('Updated name')).toBeTruthy();
});

it('keeps failed edits retryable without success or changes to the confirmed profile', async () => {
  const { api, current } = service();
  jest.mocked(api.saveProfile).mockRejectedValueOnce(new Error('Could not save profile'));
  await render(<Session api={api} page="edit" />);
  await screen.findByDisplayValue('Saved app name');
  await fireEvent.changeText(screen.getByLabelText('Full name'), 'Retry name');
  await fireEvent.press(screen.getByRole('button', { name: 'Save changes' }));
  expect(screen.getByRole('alert')).toHaveTextContent(/Could not save profile/);
  expect(current().full_name).toBe('Saved app name');
  expect(screen.queryByText('Profile name saved.')).toBeNull();
  expect(screen.getByDisplayValue('Retry name')).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'Save changes' }));
  expect(await screen.findByText('Profile name saved.')).toBeTruthy();
});

it.each([true, false])('cancels without saving and handles Back history availability (%s)', async canGoBack => {
  mockCanGoBack = canGoBack;
  const { api } = service();
  await render(<Session api={api} page="edit" />);
  await screen.findByDisplayValue('Saved app name');
  await fireEvent.changeText(screen.getByLabelText('Full name'), 'Unsaved name');
  await fireEvent.press(screen.getByRole('button', { name: 'Cancel' }));
  expect(api.saveProfile).not.toHaveBeenCalled();
  if (canGoBack) expect(mockBack).toHaveBeenCalledTimes(1);
  else expect(mockReplace).toHaveBeenCalledWith('/(main)/(tabs)/account');
});

it('validates names and keeps photo previews out of save payloads', async () => {
  const save = jest.fn(async () => {}), cancel = jest.fn();
  const photo: ProfilePhoto = { uri: 'file:///test-photo.jpg', width: 400, height: 400 };
  await render(<EditProfileForm identity={alice} onSave={save} onCancel={cancel} pickPhoto={async () => photo} />);
  await fireEvent.changeText(screen.getByLabelText('Full name'), '  ');
  await fireEvent.press(screen.getByRole('button', { name: 'Save changes' }));
  expect(screen.getByRole('alert')).toHaveTextContent(/between 1 and 120/);
  expect(save).not.toHaveBeenCalled();
  await fireEvent.changeText(screen.getByLabelText('Full name'), 'Photo name');
  await fireEvent.press(screen.getByRole('button', { name: 'Choose photo' }));
  expect(screen.getByLabelText('Local profile photo preview')).toBeTruthy();
  expect(screen.getByText(/not uploaded, synced, or permanently stored/)).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'Save changes' }));
  expect(save).toHaveBeenCalledWith('Photo name');
  await fireEvent.press(screen.getByRole('button', { name: 'Remove photo' }));
  expect(screen.queryByLabelText('Local profile photo preview')).toBeNull();
  expect(screen.getByLabelText('Profile initials PN')).toBeTruthy();
});

it('falls back to initials if a preview cannot load', async () => {
  await render(<ProfileAvatar name="Saved name" photo={{ uri: 'file:///missing.jpg', width: 1, height: 1 }} />);
  await fireEvent(screen.getByLabelText('Local profile photo preview'), 'error');
  expect(screen.getByLabelText('Profile initials SN')).toBeTruthy();
});

it.each([{ providerIds: ['password'] }, { providerIds: ['google.com', 'password'] }])('supports reset for linked password providers ($providerIds)', async ({ providerIds }) => {
  await render(<SecurityScreen user={{ ...alice, providerIds }} refreshUser={mockRefresh} onBack={mockBack} />);
  expect(screen.getByText('Email verified')).toBeTruthy();
  expect(screen.queryByRole('button', { name: 'Send verification email' })).toBeNull();
  await fireEvent.press(screen.getByRole('button', { name: 'Send password-reset email' }));
  expect(authService.resetPassword).toHaveBeenCalledWith(alice.email);
  expect(screen.getByText(/Password-reset email requested/)).toBeTruthy();
});

it.each([{ providerIds: ['google.com'] }, { providerIds: ['oidc.example'] }, { providerIds: [] }])('explains unsupported provider actions ($providerIds)', async ({ providerIds }) => {
  await render(<SecurityScreen user={{ ...alice, emailVerified: false, providerIds }} refreshUser={mockRefresh} onBack={mockBack} />);
  expect(screen.getByText('Email not verified')).toBeTruthy();
  expect(screen.queryByRole('button', { name: 'Send password-reset email' })).toBeNull();
  expect(screen.queryByRole('button', { name: 'Send verification email' })).toBeNull();
  expect(screen.getByText(/Manage your password through your sign-in provider/)).toBeTruthy();
});

it('does not guess password support when provider information or email is absent', async () => {
  const view = await render(<SecurityScreen user={{ ...alice, providerIds: undefined }} refreshUser={mockRefresh} onBack={mockBack} />);
  expect(screen.getByText(/provider information is unavailable/)).toBeTruthy();
  await view.rerender(<SecurityScreen user={{ ...alice, email: null }} refreshUser={mockRefresh} onBack={mockBack} />);
  expect(screen.getByText('Email unavailable')).toBeTruthy();
  expect(screen.queryByRole('button', { name: 'Send password-reset email' })).toBeNull();
});

it('uses existing verification delivery/refresh and safely reports Firebase errors', async () => {
  mockUser = { ...alice, emailVerified: false };
  mockRefresh.mockResolvedValue(false);
  await render(<Security />);
  await fireEvent.press(screen.getByRole('button', { name: 'Send verification email' }));
  expect(authService.sendVerification).toHaveBeenCalledTimes(1);
  expect(screen.getByText(/Verification email sent/)).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'Refresh verification status' }));
  expect(mockRefresh).toHaveBeenCalledTimes(1);
  expect(screen.getByText(/not verified yet/)).toBeTruthy();
  jest.mocked(authService.resetPassword).mockRejectedValueOnce({ code: 'auth/too-many-requests', token: 'never-show' });
  await fireEvent.press(screen.getByRole('button', { name: 'Send password-reset email' }));
  expect(screen.getByRole('alert')).toHaveTextContent(/Too many attempts/);
  expect(screen.queryByText(/never-show/)).toBeNull();
});

it('waits for Firebase confirmation and prevents duplicate password reset requests', async () => {
  let finish!: () => void;
  jest.mocked(authService.resetPassword).mockImplementationOnce(() => new Promise<void>(resolve => { finish = resolve; }));
  await render(<SecurityScreen user={alice} refreshUser={mockRefresh} onBack={mockBack} />);
  await fireEvent.press(screen.getByRole('button', { name: 'Send password-reset email' }));
  expect(screen.getByRole('button', { name: 'Send password-reset email' })).toBeDisabled();
  expect(screen.queryByText(/Password-reset email requested/)).toBeNull();
  await fireEvent.press(screen.getByRole('button', { name: 'Send password-reset email' }));
  expect(authService.resetPassword).toHaveBeenCalledTimes(1);
  await act(async () => finish());
  expect(screen.getByText(/Password-reset email requested/)).toBeTruthy();
});

it('contains real app/privacy information, no decorative toggles, and retryable Firebase logout', async () => {
  jest.mocked(authService.signOut).mockRejectedValueOnce({ code: 'auth/network-request-failed' });
  await render(<ProfileSyncProvider><Settings /></ProfileSyncProvider>);
  expect(screen.getByText('DrivePulse AI')).toBeTruthy();
  expect(screen.getByText('App configuration version: 1.0.0-test')).toBeTruthy();
  expect(screen.getByText('Installed app version: Unavailable in this build')).toBeTruthy();
  expect(screen.getByText(/not real ML predictions/)).toBeTruthy();
  expect(screen.queryAllByRole('switch')).toHaveLength(0);
  await fireEvent.press(screen.getByRole('button', { name: 'Log out' }));
  expect(screen.getByRole('alert')).toHaveTextContent(/Could not connect/);
  await fireEvent.press(screen.getByRole('button', { name: 'Log out' }));
  expect(authService.signOut).toHaveBeenCalledTimes(2);
  expect(mockReplace).not.toHaveBeenCalled();
});

it('clears the previous account profile and draft on UID changes', async () => {
  const aliceApi = service().api, bobApi = service({ ...accountState('home', 'bob'), full_name: 'Bob saved name' }).api;
  const view = await render(<Session api={aliceApi} page="edit" />);
  await screen.findByDisplayValue('Saved app name');
  await fireEvent.changeText(screen.getByLabelText('Full name'), 'Alice unsaved');
  mockUser = { ...alice, uid: 'bob', email: 'bob@example.com' };
  await view.rerender(<Session api={bobApi} uid="bob" page="edit" />);
  expect(await screen.findByDisplayValue('Bob saved name')).toBeTruthy();
  expect(screen.queryByDisplayValue('Alice unsaved')).toBeNull();
});
