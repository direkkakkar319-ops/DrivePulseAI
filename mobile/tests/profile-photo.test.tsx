// Test the real photo adapter and profile route against a controlled native picker boundary.
import { act, fireEvent, render, screen, userEvent } from '@testing-library/react-native';
import * as ImagePicker from 'expo-image-picker';
import ProfileSetupRoute from '../src/app/(main)/profile-setup';
import { pickProfilePhoto } from '../src/lib/profile-photo';
import { authService } from '../src/api/auth';

const mockReplace = jest.fn();
let mockUser = { uid: 'photo-account', email: 'driver@example.com', displayName: null as string | null, emailVerified: true };
jest.mock('../src/store/authStore', () => ({ useAuthStore: () => ({ user: mockUser }) }));
jest.mock('../src/api/auth', () => ({ authService: { saveUsername: jest.fn(), signUp: jest.fn() } }));
jest.mock('expo-router', () => ({ useRouter: () => ({ replace: mockReplace }) }));
jest.mock('expo-image-picker', () => ({
  launchImageLibraryAsync: jest.fn(),
  requestMediaLibraryPermissionsAsync: jest.fn(),
  requestCameraPermissionsAsync: jest.fn(),
}));

const launch = ImagePicker.launchImageLibraryAsync as jest.Mock;
const image = { uri: 'file:///local-profile.jpg', width: 600, height: 400, type: 'image', mimeType: 'image/jpeg' };
beforeEach(() => {
  jest.resetAllMocks();
  mockUser = { uid: 'photo-account', email: 'driver@example.com', displayName: null, emailVerified: true };
  launch.mockResolvedValue({ canceled: true, assets: null });
});

it('opens an image-only system picker and returns only local preview metadata', async () => {
  launch.mockResolvedValue({ canceled: false, assets: [{ ...image, fileName: 'private.jpg', exif: { private: true }, base64: 'private-content' }] });
  await expect(pickProfilePhoto()).resolves.toEqual({ uri: image.uri, width: 600, height: 400, mimeType: 'image/jpeg' });
  expect(launch).toHaveBeenCalledWith({ mediaTypes: ['images'], allowsMultipleSelection: false,
    allowsEditing: false, quality: 0.8, exif: false, base64: false });
  expect(ImagePicker.requestMediaLibraryPermissionsAsync).not.toHaveBeenCalled();
  expect(ImagePicker.requestCameraPermissionsAsync).not.toHaveBeenCalled();
});

it('returns null for picker cancellation', async () => {
  await expect(pickProfilePhoto()).resolves.toBeNull();
});

it.each(['E_NO_LIBRARY_PERMISSION', 'ERR_MISSING_CAMERA_PERMISSION', 'ERR_USER_REJECTED_PERMISSIONS'])('normalizes native permission rejection %s', async code => {
  launch.mockRejectedValue({ code, message: 'Raw native error with a private path' });
  await expect(pickProfilePhoto()).rejects.toMatchObject({ reason: 'permission', message: 'Profile photo selection failed' });
});

it('categorizes an unavailable native picker without crashing the app', async () => {
  launch.mockRejectedValue({ code: 'ERR_UNAVAILABLE' });
  await expect(pickProfilePhoto()).rejects.toMatchObject({ reason: 'unavailable' });
});

it.each([
  [], [{ ...image, uri: '' }], [{ ...image, width: 0 }], [{ ...image, height: NaN }],
  [{ ...image, type: 'video' }], [{ ...image, mimeType: 'video/mp4' }],
])('rejects malformed or non-image native results (%#)', async (...assets) => {
  launch.mockResolvedValue({ canceled: false, assets });
  await expect(pickProfilePhoto()).rejects.toMatchObject({ reason: 'invalid-image' });
});

it('connects Choose, Change and Remove controls to the real adapter without account writes', async () => {
  const replacement = { ...image, uri: 'file:///replacement.jpg' };
  launch.mockResolvedValueOnce({ canceled: false, assets: [image] })
    .mockResolvedValueOnce({ canceled: false, assets: [replacement] });
  await render(<ProfileSetupRoute />);
  expect(screen.getByRole('button', { name: 'Choose photo' })).toBeEnabled();
  await fireEvent.press(screen.getByRole('button', { name: 'Choose photo' }));
  expect(screen.getByLabelText('Selected profile photo')).toHaveProp('source', { uri: image.uri });
  await fireEvent.press(screen.getByRole('button', { name: 'Change photo' }));
  expect(screen.getByLabelText('Selected profile photo')).toHaveProp('source', { uri: replacement.uri });
  await fireEvent.press(screen.getByRole('button', { name: 'Remove photo' }));
  expect(screen.queryByLabelText('Selected profile photo')).toBeNull();
  expect(screen.getByLabelText('Profile initials: DR')).toBeTruthy();
  expect(launch).toHaveBeenCalledTimes(2);
  expect(authService.saveUsername).not.toHaveBeenCalled();
  expect(authService.signUp).not.toHaveBeenCalled();
  expect(mockReplace).not.toHaveBeenCalled();
});

it('keeps the prior selection after replacement cancellation or denied access', async () => {
  launch.mockResolvedValueOnce({ canceled: false, assets: [image] })
    .mockResolvedValueOnce({ canceled: true, assets: null })
    .mockRejectedValueOnce({ code: 'ERR_USER_REJECTED_PERMISSIONS', message: 'Do not display raw SDK text' });
  await render(<ProfileSetupRoute />);
  await fireEvent.press(screen.getByRole('button', { name: 'Choose photo' }));
  await fireEvent.press(screen.getByRole('button', { name: 'Change photo' }));
  expect(screen.getByLabelText('Selected profile photo')).toHaveProp('source', { uri: image.uri });
  expect(screen.queryByRole('alert')).toBeNull();
  await fireEvent.press(screen.getByRole('button', { name: 'Change photo' }));
  expect(screen.getByLabelText('Selected profile photo')).toHaveProp('source', { uri: image.uri });
  expect(screen.getByRole('alert')).toHaveTextContent(/device settings/);
  expect(screen.queryByText('Do not display raw SDK text')).toBeNull();
  expect(screen.getByRole('button', { name: 'Continue' })).toBeEnabled();
  expect(screen.getByRole('button', { name: 'Skip for now' })).toBeEnabled();
});

it.each([
  [{ code: 'ERR_UNAVAILABLE' }, /unavailable in this build/],
  [new Error('private implementation error'), /Could not select a photo/],
])('keeps picker errors optional and recoverable (%#)', async (failure, message) => {
  launch.mockRejectedValueOnce(failure).mockResolvedValueOnce({ canceled: false, assets: [image] });
  await render(<ProfileSetupRoute />);
  await fireEvent.press(screen.getByRole('button', { name: 'Choose photo' }));
  expect(screen.getByRole('alert')).toHaveTextContent(message as RegExp);
  expect(screen.getByLabelText('Profile initials: DR')).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Skip for now' })).toBeEnabled();
  await fireEvent.press(screen.getByRole('button', { name: 'Choose photo' }));
  expect(screen.queryByRole('alert')).toBeNull();
  expect(screen.getByLabelText('Selected profile photo')).toBeTruthy();
});

it('ignores a picker result from a previous account', async () => {
  let resolve!: (result: unknown) => void;
  launch.mockImplementationOnce(() => new Promise(done => { resolve = done; }));
  const user = userEvent.setup();
  const view = await render(<ProfileSetupRoute />);
  await user.press(screen.getByRole('button', { name: 'Choose photo' }));
  mockUser = { ...mockUser, uid: 'another-account', email: 'second@example.com' };
  await view.rerender(<ProfileSetupRoute />);
  await act(async () => resolve({ canceled: false, assets: [image] }));
  expect(screen.queryByLabelText('Selected profile photo')).toBeNull();
  expect(screen.getByLabelText('Profile initials: SE')).toBeTruthy();
});
