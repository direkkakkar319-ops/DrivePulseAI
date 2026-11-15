// Real Firebase session/account providers verify logout cleanup and per-account server restoration.
import { Text } from 'react-native';
import { act, fireEvent, render, screen } from '@testing-library/react-native';
import type { AuthUser } from '../src/api/auth.types';
import type { OnboardingApi } from '../src/api/onboarding';
import { authService } from '../src/api/auth';
import { AuthProvider, useAuthStore } from '../src/store/authStore';
import { OnboardingProvider, useOnboarding } from '../src/store/onboardingStore';
import { ProfileSyncProvider } from '../src/hooks/use-profile-sync';
import { OnboardingGate } from '../src/components/onboarding-gate';
import Profile from '../src/app/(main)/(tabs)/account';
import Settings from '../src/app/(main)/settings';
import { accountState } from './onboarding-fixtures';

jest.mock('../src/api/auth', () => ({ authService: { subscribe: jest.fn(), signOut: jest.fn(), getToken: jest.fn() } }));
jest.mock('../src/api/client', () => ({ ...jest.requireActual('../src/api/client'), syncProfile: jest.fn(async () => ({})) }));
jest.mock('../src/lib/app-version', () => ({ appVersion: () => ({ installed: null, configured: null }) }));
jest.mock('expo-router', () => {
  const Text = require('react-native').Text;
  return {
    useSegments: () => ['(main)', '(tabs)', 'account'],
    useRouter: () => ({ navigate: jest.fn(), push: jest.fn(), back: jest.fn(), replace: jest.fn(), canGoBack: () => true }),
    Redirect: ({ href }: { href: string }) => <Text>Unexpected redirect: {href}</Text>,
  };
});

let notify!: (user: AuthUser | null) => void;
const alice: AuthUser = { uid: 'alice', email: 'alice@example.com', displayName: 'Firebase Alice', emailVerified: true, providerIds: ['password'] };
const server = {
  alice: { ...accountState('home'), full_name: 'Persisted Alice' },
  bob: { ...accountState('home', 'bob'), full_name: 'Persisted Bob', vehicles: [], active_vehicle_id: null, first_vehicle_id: null },
};
function Snapshot() {
  const { resource } = useOnboarding();
  return <Text>{resource.status === 'ready' ? `Saved vehicles: ${resource.data.vehicles.length}` : 'Loading vehicles'}</Text>;
}
function AccountArea({ api }: { api: OnboardingApi }) {
  const { user } = useAuthStore();
  return user?.emailVerified ? <ProfileSyncProvider key={user.uid}><OnboardingProvider uid={user.uid} api={api}>
    <OnboardingGate><Profile /><Snapshot /><Settings /></OnboardingGate>
  </OnboardingProvider></ProfileSyncProvider> : <Text>Authentication required</Text>;
}
beforeEach(() => {
  jest.clearAllMocks();
  jest.mocked(authService.subscribe).mockImplementation(callback => { notify = callback; callback(null); return jest.fn(); });
  jest.mocked(authService.signOut).mockImplementation(async () => notify(null));
});

it('clears protected profile/vehicles on logout and restores the correct durable account on login', async () => {
  const api: OnboardingApi = { load: jest.fn(async uid => server[uid as keyof typeof server]),
    saveProfile: jest.fn(), saveFirstVehicle: jest.fn(), selectActive: jest.fn() };
  const original = JSON.stringify(server);
  await render(<AuthProvider><AccountArea api={api} /></AuthProvider>);
  expect(screen.getByText('Authentication required')).toBeTruthy();
  await act(async () => notify(alice));
  expect(await screen.findByText('Persisted Alice')).toBeTruthy();
  expect(screen.getByText('Saved vehicles: 1')).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'Log out' }));
  expect(screen.getByText('Authentication required')).toBeTruthy();
  expect(screen.queryByText('Persisted Alice')).toBeNull();
  expect(screen.queryByText('Saved vehicles: 1')).toBeNull();
  await act(async () => notify({ ...alice, uid: 'bob', email: 'bob@example.com' }));
  expect(await screen.findByText('Persisted Bob')).toBeTruthy();
  expect(screen.getByText('Saved vehicles: 0')).toBeTruthy();
  expect(screen.queryByText('Persisted Alice')).toBeNull();
  await fireEvent.press(screen.getByRole('button', { name: 'Log out' }));
  await act(async () => notify(alice));
  expect(await screen.findByText('Persisted Alice')).toBeTruthy();
  expect(screen.getByText('Saved vehicles: 1')).toBeTruthy();
  expect(api.load).toHaveBeenNthCalledWith(1, 'alice');
  expect(api.load).toHaveBeenNthCalledWith(2, 'bob');
  expect(api.load).toHaveBeenNthCalledWith(3, 'alice');
  expect(api.saveFirstVehicle).not.toHaveBeenCalled();
  expect(api.saveProfile).not.toHaveBeenCalled();
  expect(screen.queryByText(/Unexpected redirect/)).toBeNull();
  expect(JSON.stringify(server)).toBe(original);
});
