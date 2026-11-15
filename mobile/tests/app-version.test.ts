// Installed binary version is optional and never substituted silently with a JS configuration value.
import { requireOptionalNativeModule } from 'expo-modules-core';
import { appVersion } from '../src/lib/app-version';
jest.mock('expo-modules-core', () => ({ ...jest.requireActual('expo-modules-core'), requireOptionalNativeModule: jest.fn() }));
jest.mock('expo-constants', () => ({ __esModule: true, default: { expoConfig: { version: 'configured-version' } } }));

it('shows the installed native version when the existing binary exposes it', () => {
  jest.mocked(requireOptionalNativeModule).mockReturnValue({ nativeApplicationVersion: 'native-version' });
  expect(appVersion()).toEqual({ installed: 'native-version', configured: 'configured-version' });
  expect(requireOptionalNativeModule).toHaveBeenCalledWith('ExpoApplication');
});
it('retains explicitly labeled configuration information when native version is unavailable', () => {
  jest.mocked(requireOptionalNativeModule).mockReturnValue(null);
  expect(appVersion()).toEqual({ installed: null, configured: 'configured-version' });
});
it('does not crash when optional native metadata cannot be read', () => {
  jest.mocked(requireOptionalNativeModule).mockImplementation(() => { throw new Error('Native module absent'); });
  expect(appVersion().installed).toBeNull();
});
