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

it.each([
  ['http://localhost/home', 'Garage'], ['http://localhost/', 'Garage'], ['http://localhost/', 'Profile'],
  ['http://localhost/vehicles', 'direct'],
])('opens My Garage without a navigation state update loop after entering at %s through %s', async (location, tab) => {
  const context = getMockContext({
    _layout: RootNavigator,
    index: Index,
    '(auth)/_layout': () => <Stack />,
    '(auth)/welcome': () => <Text>Welcome</Text>,
    'verify-email': () => <Text>Verify email</Text>,
    explore: () => <Text>Explore</Text>,
    '(main)/dashboard': Dashboard,
    '(main)/account': Account,
    '(main)/_layout': MainLayout,
    '(main)/(tabs)/_layout': ProductTabs,
    '(main)/(tabs)/home': Home,
    '(main)/(tabs)/vehicles': Garage,
    '(main)/(tabs)/history': History,
    '(main)/(tabs)/insights': () => <Text>Insights</Text>,
    '(main)/(tabs)/account': Account,
    '(main)/(tabs)/telemetry': () => <Text>Telemetry</Text>,
  });
  await render(<ExpoRoot context={context} location={location} />);
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
});
