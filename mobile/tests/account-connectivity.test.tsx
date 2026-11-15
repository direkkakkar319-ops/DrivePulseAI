// Real signed-in layout, profile sync, API adapter and gate must fail closed on a LAN outage and recover on Retry.
import { fireEvent, render, screen } from '@testing-library/react-native';
import { authService } from '../src/api/auth';
import { accountState } from './onboarding-fixtures';

let mockUid = 'alice';
jest.mock('../src/store/authStore', () => ({ useAuthStore: () => ({ user: {
  uid: mockUid, email: `${mockUid}@example.com`, emailVerified: true, displayName: 'Driver',
} }) }));
jest.mock('../src/api/auth', () => ({ authService: { getToken: jest.fn(), signOut: jest.fn() } }));
jest.mock('expo-router', () => {
  const React = require('react'); const { Text } = require('react-native');
  const Stack = ({ children }: { children: React.ReactNode }) => children;
  Stack.Screen = () => React.createElement(Text, null, 'Protected tabs');
  return { Stack, useSegments: () => ['(main)', '(tabs)', 'home'],
    Redirect: ({ href }: { href: string }) => React.createElement(Text, null, `redirect:${href}`) };
});

const originalFetch = global.fetch;
const originalApiUrl = process.env.EXPO_PUBLIC_API_URL;
process.env.EXPO_PUBLIC_API_URL = 'http://192.0.2.10:8000';
const MainLayout = (require('../src/app/(main)/_layout') as typeof import('../src/app/(main)/_layout')).default;
beforeEach(() => {
  jest.clearAllMocks();
  global.fetch = jest.fn().mockRejectedValue(new TypeError('Network request failed'));
  (authService.getToken as jest.Mock).mockResolvedValue('firebase-id-token');
});
afterEach(() => { global.fetch = originalFetch; });
afterAll(() => {
  if (originalApiUrl === undefined) delete process.env.EXPO_PUBLIC_API_URL;
  else process.env.EXPO_PUBLIC_API_URL = originalApiUrl;
});

it.each([['existing', 'home'], ['new', 'profile']] as const)(
  'blocks the %s account when the API is unreachable, then restores genuine server routing on Retry', async (kind, step) => {
    mockUid = kind === 'existing' ? 'alice' : 'bob';
    await render(<MainLayout />);
    expect(await screen.findByText('Account unavailable')).toBeTruthy();
    expect(screen.getByText('Could not reach the account service. Check your connection and try again.')).toBeTruthy();
    expect(screen.queryByText('Protected tabs')).toBeNull();
    expect(screen.queryByText(/^redirect:/)).toBeNull();
    expect(fetch).toHaveBeenCalledWith('http://192.0.2.10:8000/api/v1/users/me', expect.objectContaining({
      method: 'PUT', headers: { Authorization: 'Bearer firebase-id-token' },
    }));
    expect(fetch).toHaveBeenCalledWith('http://192.0.2.10:8000/api/v1/onboarding', expect.objectContaining({
      method: 'GET', headers: { Authorization: 'Bearer firebase-id-token', 'X-Account-UID': mockUid },
    }));
    (fetch as jest.Mock).mockResolvedValue({ ok: true, status: 200, json: async () => accountState(step, mockUid) });
    await fireEvent.press(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByText(step === 'home' ? 'Protected tabs' : 'redirect:/(main)/profile-setup')).toBeTruthy();
    expect(screen.queryByText('Account unavailable')).toBeNull();
    expect(authService.signOut).not.toHaveBeenCalled();
  },
);

it('does not accept a successful response belonging to another account', async () => {
  mockUid = 'alice';
  (fetch as jest.Mock).mockResolvedValue({ ok: true, status: 200, json: async () => accountState('home', 'bob') });
  await render(<MainLayout />);
  expect(await screen.findByText('Account unavailable')).toBeTruthy();
  expect(screen.getByText('The account service returned an unexpected onboarding response.')).toBeTruthy();
  expect(screen.queryByText('Protected tabs')).toBeNull();
});
