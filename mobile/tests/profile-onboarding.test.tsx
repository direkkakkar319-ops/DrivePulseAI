// Verify optional local profile drafts, account isolation, and unchanged entry destinations.
import { act, fireEvent, render, screen, userEvent } from '@testing-library/react-native';
import Welcome from '../src/app/(auth)/welcome';
import ProfileSetupRoute from '../src/app/(main)/profile-setup';
import Index from '../src/app/index';
import { ProfileOnboardingForm } from '../src/components/profile-onboarding';
import { profileDisplayName, profileInitials, useProfileOnboarding } from '../src/hooks/use-profile-onboarding';
import { authService } from '../src/api/auth';
import type { AuthUser } from '../src/api/auth.types';
import type { PickProfilePhoto, ProfileIdentity, ProfilePhoto } from '../src/types/profile-onboarding';

const account: AuthUser = { uid: 'account-one', email: 'driver@example.com', displayName: null, emailVerified: true };
let mockUser: AuthUser | null = account;
const mockPush = jest.fn(), mockReplace = jest.fn(), mockContinue = jest.fn(), mockSkip = jest.fn();
jest.mock('../src/store/authStore', () => ({ useAuthStore: () => ({ user: mockUser }) }));
jest.mock('../src/api/auth', () => ({ authService: { saveUsername: jest.fn(), signUp: jest.fn() } }));
jest.mock('expo-router', () => {
  const React = require('react');
  const { Text } = require('react-native');
  return {
    useRouter: () => ({ push: mockPush, replace: mockReplace }),
    Redirect: ({ href }: { href: string }) => React.createElement(Text, null, `redirect:${href}`),
  };
});

function Draft({ identity = account, pickPhoto }: { identity?: ProfileIdentity; pickPhoto?: PickProfilePhoto }) {
  const form = useProfileOnboarding(identity, pickPhoto);
  return <ProfileOnboardingForm {...form} onContinue={() => mockContinue(form.result())} onSkip={mockSkip} />;
}

beforeEach(() => { jest.clearAllMocks(); mockUser = account; });

it('keeps Welcome Get started and login destinations unchanged', async () => {
  await render(<Welcome />);
  expect(screen.getByRole('header')).toHaveTextContent('Understand your vehicle.');
  await fireEvent.press(screen.getByRole('button', { name: 'Get started' }));
  expect(mockPush).toHaveBeenNthCalledWith(1, { pathname: '/(auth)/login', params: { mode: 'signup' } });
  await fireEvent.press(screen.getByRole('button', { name: 'Log in' }));
  expect(mockPush).toHaveBeenNthCalledWith(2, '/(auth)/login');
});

it.each([
  [null, '/(auth)/welcome'],
  [{ ...account, emailVerified: false }, '/verify-email'],
  [account, '/(main)/dashboard'],
] as const)('preserves the current entry redirect for %o', async (user, destination) => {
  mockUser = user;
  await render(<Index />);
  expect(screen.getByText(`redirect:${destination}`)).toBeTruthy();
  expect(mockReplace).not.toHaveBeenCalled();
});

it('continues with an empty name, email fallback, initials, and no licence answer', async () => {
  await render(<Draft />);
  expect(screen.getByLabelText('Full name')).toHaveProp('value', '');
  expect(screen.getByLabelText('Display name: driver')).toBeTruthy();
  expect(screen.getByLabelText('Profile initials: DR')).toBeTruthy();
  await fireEvent.changeText(screen.getByLabelText('Full name'), '   ');
  await fireEvent.press(screen.getByRole('button', { name: 'Continue' }));
  expect(mockContinue).toHaveBeenCalledWith({ userId: account.uid, fullName: null,
    displayName: 'driver', photo: null, drivingLicence: null });
});

it('prefills an existing account name and never writes draft edits to Firebase', async () => {
  const identity = { ...account, displayName: 'Alex Morgan' };
  await render(<Draft identity={identity} />);
  expect(screen.getByLabelText('Full name')).toHaveProp('value', 'Alex Morgan');
  expect(screen.getByLabelText('Profile initials: AM')).toBeTruthy();
  await fireEvent.changeText(screen.getByLabelText('Full name'), '  Taylor Lee  ');
  expect(screen.getByLabelText('Display name: Taylor Lee')).toBeTruthy();
  expect(screen.getByLabelText('Profile initials: TL')).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'Continue' }));
  expect(mockContinue).toHaveBeenCalledWith(expect.objectContaining({ fullName: 'Taylor Lee', displayName: 'Taylor Lee' }));
  expect(identity.displayName).toBe('Alex Morgan');
  expect(authService.saveUsername).not.toHaveBeenCalled();
  expect(authService.signUp).not.toHaveBeenCalled();
});

it.each([
  ['Yes', 'yes'], ['No', 'no'], ['Prefer not to say', 'prefer-not-to-say'],
])('allows Continue with licence answer %s', async (label, value) => {
  await render(<Draft />);
  await fireEvent.press(screen.getByRole('radio', { name: label }));
  expect(screen.getByRole('radio', { name: label })).toHaveProp('accessibilityState', { checked: true });
  expect(screen.getAllByRole('radio').filter(radio => radio.props.accessibilityState.checked)).toHaveLength(1);
  expect(screen.getByRole('button', { name: 'Continue' })).toBeEnabled();
  await fireEvent.press(screen.getByRole('button', { name: 'Continue' }));
  expect(mockContinue).toHaveBeenCalledWith(expect.objectContaining({ drivingLicence: value }));
});

it('replaces the selected licence answer without restricting access and allows Skip', async () => {
  await render(<Draft />);
  await fireEvent.press(screen.getByRole('radio', { name: 'Yes' }));
  await fireEvent.press(screen.getByRole('radio', { name: 'No' }));
  expect(screen.getByRole('radio', { name: 'Yes' })).toHaveProp('accessibilityState', { checked: false });
  await fireEvent.press(screen.getByRole('button', { name: 'Skip for now' }));
  expect(mockSkip).toHaveBeenCalledTimes(1);
  expect(mockContinue).not.toHaveBeenCalled();
});

const photo: ProfilePhoto = { uri: 'file:///selected-photo.jpg', width: 400, height: 400, mimeType: 'image/jpeg' };
it('previews a selected photo, preserves it on cancellation, and restores initials on removal', async () => {
  const picker = jest.fn().mockResolvedValueOnce(photo).mockResolvedValueOnce(null);
  await render(<Draft pickPhoto={picker} />);
  await fireEvent.press(screen.getByRole('button', { name: 'Choose photo' }));
  expect(screen.getByLabelText('Selected profile photo')).toHaveProp('source', { uri: photo.uri });
  expect(screen.queryByLabelText('Profile initials: DR')).toBeNull();
  await fireEvent.press(screen.getByRole('button', { name: 'Change photo' }));
  expect(screen.getByLabelText('Selected profile photo')).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'Continue' }));
  expect(mockContinue).toHaveBeenCalledWith(expect.objectContaining({ photo }));
  await fireEvent.press(screen.getByRole('button', { name: 'Remove photo' }));
  expect(screen.getByLabelText('Profile initials: DR')).toBeTruthy();
});

it('keeps photo cancellation and picker errors optional and recoverable', async () => {
  const picker = jest.fn().mockResolvedValueOnce(null).mockRejectedValueOnce(new Error('Permission denied')).mockResolvedValueOnce(photo);
  await render(<Draft pickPhoto={picker} />);
  await fireEvent.press(screen.getByRole('button', { name: 'Choose photo' }));
  expect(screen.queryByRole('alert')).toBeNull();
  expect(screen.getByLabelText('Profile initials: DR')).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'Choose photo' }));
  expect(screen.getByRole('alert')).toHaveTextContent(/Could not select a photo/);
  expect(screen.getByRole('button', { name: 'Continue' })).toBeEnabled();
  await fireEvent.press(screen.getByRole('button', { name: 'Choose photo' }));
  expect(screen.queryByRole('alert')).toBeNull();
  expect(screen.getByLabelText('Selected profile photo')).toBeTruthy();
  await fireEvent(screen.getByLabelText('Selected profile photo'), 'error');
  expect(screen.getByLabelText('Profile initials: DR')).toBeTruthy();
});

it('prevents duplicate photo selection while the system picker is open', async () => {
  let resolve!: (value: ProfilePhoto | null) => void;
  const picker = jest.fn(() => new Promise<ProfilePhoto | null>(done => { resolve = done; }));
  const user = userEvent.setup();
  await render(<Draft pickPhoto={picker} />);
  await user.press(screen.getByRole('button', { name: 'Choose photo' }));
  expect(screen.getByRole('button', { name: 'Choose photo' })).toBeDisabled();
  await fireEvent.press(screen.getByRole('button', { name: 'Choose photo' }));
  expect(picker).toHaveBeenCalledTimes(1);
  await act(async () => resolve(null));
  expect(screen.getByRole('button', { name: 'Continue' })).toBeEnabled();
});

it.each(['Continue', 'Skip for now'])('returns to the current dashboard with %s and no account writes', async action => {
  await render(<ProfileSetupRoute />);
  await fireEvent.changeText(screen.getByLabelText('Full name'), 'Optional name');
  await fireEvent.press(screen.getByRole('button', { name: action }));
  expect(mockReplace).toHaveBeenCalledWith('/(main)/dashboard');
  expect(mockPush).not.toHaveBeenCalled();
  expect(authService.saveUsername).not.toHaveBeenCalled();
});

it.each([null, { ...account, emailVerified: false }])('does not expose profile setup to an unavailable or unverified account', async user => {
  mockUser = user;
  await render(<ProfileSetupRoute />);
  expect(screen.queryByLabelText('Full name')).toBeNull();
  expect(mockReplace).not.toHaveBeenCalled();
});

it('resets the route draft when the Firebase account identity changes', async () => {
  const view = await render(<ProfileSetupRoute />);
  await fireEvent.changeText(screen.getByLabelText('Full name'), 'Private draft');
  mockUser = { ...account, uid: 'account-two', email: 'second@example.com' };
  await view.rerender(<ProfileSetupRoute />);
  expect(screen.getByLabelText('Full name')).toHaveProp('value', '');
  expect(screen.getByLabelText('Display name: second')).toBeTruthy();
});

it('handles missing email and Unicode initials without invented account data', () => {
  expect(profileDisplayName({ ...account, email: null, displayName: 'Existing name' }, '')).toBe('Existing name');
  expect(profileDisplayName({ ...account, email: null }, '')).toBe('Your profile');
  expect(profileInitials(' Élodie Martin ')).toBe('ÉM');
  expect(profileInitials('李')).toBe('李');
});
