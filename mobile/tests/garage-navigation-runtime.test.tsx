// Exercise Garage tab activation through the actual Expo Router navigator rather than mocked tabs.
import 'expo-router/build/testing-library/mocks';
import { Text } from 'react-native';
import { render, fireEvent, screen } from '@testing-library/react-native';
import { ExpoRoot } from 'expo-router/build/ExpoRoot';
import { getMockContext } from 'expo-router/build/testing-library/mock-config';
import { Stack } from 'expo-router';
import ProductTabs from '../src/app/(main)/(tabs)/_layout';
import MainLayout from '../src/app/(main)/_layout';
import Home from '../src/app/(main)/(tabs)/home';
import Garage from '../src/app/(main)/(tabs)/vehicles';
import History from '../src/app/(main)/(tabs)/history';
import { RootNavigator } from '../src/app/_layout';
import Index from '../src/app/index';
import Dashboard from '../src/app/(main)/dashboard';
import Account from '../src/app/(main)/(tabs)/account';
import Insights from '../src/app/(main)/(tabs)/insights';
import Settings from '../src/app/(main)/settings';
import EditProfile from '../src/app/(main)/edit-profile';
import Security from '../src/app/(main)/security';
import { onboardingApi } from '../src/api/onboarding';
import { accountState } from './onboarding-fixtures';

// Match native scheduling: the package falls back to passive effects in Jest
// unless navigator.product is ReactNative. Android flushes these in layout effects.
jest.mock('expo-router/build/react-navigation/core/useClientLayoutEffect', () => ({
  useClientLayoutEffect: require('react').useLayoutEffect,
}));

jest.mock('../src/store/authStore', () => ({ useAuthStore: () => ({ user: {
  uid: 'alice', email: 'alice@example.com', emailVerified: true, displayName: 'Driver',
} }) }));
jest.mock('../src/api/auth', () => ({ authService: { getToken: jest.fn(), signOut: jest.fn() } }));
jest.mock('../src/api/client', () => ({ ...jest.requireActual('../src/api/client'), syncProfile: jest.fn(async () => ({ firebase_uid: 'alice' })) }));
jest.mock('../src/api/onboarding', () => ({ ...jest.requireActual('../src/api/onboarding'), onboardingApi: {
  load: jest.fn(async () => require('./onboarding-fixtures').accountState('home')), selectActive: jest.fn(),
} }));

function appContext() {
  return getMockContext({
    _layout: RootNavigator,
    index: Index,
    '(auth)/_layout': () => <Stack />,
    '(auth)/welcome': () => <Text>Welcome</Text>,
    'verify-email': () => <Text>Verify email</Text>,
    explore: () => <Text>Explore</Text>,
    '(main)/dashboard': Dashboard,
    '(main)/account': Account,
    '(main)/settings': Settings,
    '(main)/edit-profile': EditProfile,
    '(main)/security': Security,
    '(main)/_layout': MainLayout,
    '(main)/(tabs)/_layout': ProductTabs,
    '(main)/(tabs)/home': Home,
    '(main)/(tabs)/vehicles': Garage,
    '(main)/(tabs)/history': History,
    '(main)/(tabs)/insights': Insights,
    '(main)/(tabs)/account': Account,
  });
}

it.each([
  ['http://localhost/home', 'Garage'], ['http://localhost/', 'Garage'], ['http://localhost/', 'Profile'],
  ['http://localhost/vehicles', 'direct'],
])('opens My Garage without a navigation state update loop after entering at %s through %s', async (location, tab) => {
  await render(<ExpoRoot context={appContext()} location={location} />);
  if (tab !== 'direct') {
    await screen.findByRole('header', { name: 'Home' });
    await fireEvent.press(screen.getByText(tab));
    if (tab === 'Profile') await fireEvent.press(await screen.findByRole('button', { name: 'My Garage' }));
  }
  expect(await screen.findByRole('header', { name: 'My Garage' })).toBeTruthy();
  expect(screen.getByText('Personal car')).toBeTruthy();
  // Re-enter an already mounted tab as well as testing its initial mount.
  await fireEvent.press(screen.getByText('Home'));
  await screen.findByRole('header', { name: 'Home' });
  await fireEvent.press(screen.getByText('Garage'));
  expect(await screen.findByRole('header', { name: 'My Garage' })).toBeTruthy();
  await fireEvent.press(screen.getByText('Home'));
  await fireEvent.press(await screen.findByRole('button', { name: 'Explore Demo Data' }));
  expect(await screen.findByRole('header', { name: 'AI Insights' })).toBeTruthy();
  expect(screen.getByText('94.2%')).toBeTruthy();
  await fireEvent.press(screen.getByText('Home'));
  expect(await screen.findByText('No saved analyses yet')).toBeTruthy();
  expect(screen.queryByText('94.2%')).toBeNull();
  await fireEvent.press(screen.getByText('History'));
  expect(await screen.findByText('No analysis history yet')).toBeTruthy();
  expect(screen.queryByText('94.2%')).toBeNull();
  await fireEvent.press(screen.getByRole('button', { name: 'Explore AI Insights' }));
  expect(await screen.findByRole('header', { name: 'AI Insights' })).toBeTruthy();
  await fireEvent.press(screen.getByText('History'));
  expect(await screen.findByText('No analysis history yet')).toBeTruthy();
});

it('opens History on a completed account with an empty Garage and navigates on explicit actions only', async () => {
  jest.mocked(onboardingApi.load).mockResolvedValueOnce({ ...accountState('home'), vehicles: [],
    active_vehicle_id: null, first_vehicle_id: null });
  await render(<ExpoRoot context={appContext()} location="http://localhost/history" />);
  expect(await screen.findByRole('header', { name: 'History' })).toBeTruthy();
  expect(screen.getByText('No analysis history yet')).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'Explore AI Insights' }));
  expect(await screen.findByRole('header', { name: 'AI Insights' })).toBeTruthy();
  expect(screen.getByText('No analysis results yet')).toBeTruthy();
  await fireEvent.press(screen.getByText('Home'));
  expect(await screen.findByText('No saved vehicles yet')).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'View History' }));
  expect(await screen.findByText('No analysis history yet')).toBeTruthy();
});

it('opens Profile edit, security, and Settings with stable explicit Back navigation', async () => {
  await render(<ExpoRoot context={appContext()} location="http://localhost/home" />);
  await screen.findByRole('header', { name: 'Home' });
  await fireEvent.press(screen.getByText('Profile'));
  await screen.findByRole('header', { name: 'Profile' });
  await fireEvent.press(screen.getByRole('button', { name: 'Edit Profile' }));
  expect(await screen.findByRole('header', { name: 'Edit Profile' })).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'Cancel' }));
  expect(await screen.findByRole('header', { name: 'Profile' })).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'Security' }));
  expect(await screen.findByRole('header', { name: 'Security' })).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'Back' }));
  expect(await screen.findByRole('header', { name: 'Profile' })).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'App Settings' }));
  expect(await screen.findByRole('header', { name: 'App Settings' })).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Log out' })).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'Back' }));
  expect(await screen.findByRole('header', { name: 'Profile' })).toBeTruthy();
});
