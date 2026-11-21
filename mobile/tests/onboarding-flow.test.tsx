// Integrate real account state, routing gate, setup forms and Garage with a controlled server boundary.
import { Text } from 'react-native';
import { act, fireEvent, render, screen, userEvent } from '@testing-library/react-native';
import { OnboardingProvider, useOnboarding } from '../src/store/onboardingStore';
import { OnboardingGate } from '../src/components/onboarding-gate';
import ProfileSetupRoute from '../src/app/(main)/profile-setup';
import VehicleSetupRoute from '../src/app/(main)/vehicle-setup';
import Garage from '../src/app/(main)/(tabs)/vehicles';
import { VehicleDataProvider } from '../src/store/vehicleDataStore';
import { authService } from '../src/api/auth';
import type { OnboardingApi, OnboardingState } from '../src/api/onboarding';
import type { AuthUser } from '../src/api/auth.types';
import { accountState, savedVehicle, secondVehicleId } from './onboarding-fixtures';
import { chooseVehicleType, enterManualVehicle } from './vehicle-form-helpers';

const account: AuthUser = { uid: 'alice', email: 'alice@example.com', displayName: 'Firebase name', emailVerified: true };
let mockUser: AuthUser | null = account;
let mockRoute = 'dashboard';
const mockPush = jest.fn();
jest.mock('../src/store/authStore', () => ({ useAuthStore: () => ({ user: mockUser }) }));
jest.mock('../src/api/auth', () => ({ authService: { signOut: jest.fn() } }));
jest.mock('expo-router', () => {
  const React = require('react');
  const { Text } = require('react-native');
  return {
    useSegments: () => ['(main)', mockRoute],
    useRouter: () => ({ push: mockPush, replace: jest.fn(), back: jest.fn(), canGoBack: () => false }),
    Redirect: ({ href }: { href: string }) => React.createElement(Text, null, `redirect:${href}`),
  };
});

function makeApi(step: 'profile' | 'vehicle' | 'home' = 'profile') {
  let server = accountState(step);
  const api: OnboardingApi = {
    load: jest.fn(async () => server),
    saveProfile: jest.fn(async (_uid, input) => {
      server = { ...server, full_name: input.full_name || account.displayName, driving_licence: input.driving_licence || 'prefer-not-to-say', profile_completed_at: '2026-01-01T00:00:00Z' };
      return server;
    }),
    saveFirstVehicle: jest.fn(async () => { server = { ...accountState('home'), full_name: server.full_name }; return server; }),
    selectActive: jest.fn(async (_uid, id) => { server = { ...server, active_vehicle_id: id }; return server; }),
  };
  return { api, setState: (state: OnboardingState) => { server = state; } };
}
function Content() {
  const { resource } = useOnboarding();
  if (mockRoute === 'profile-setup') return <ProfileSetupRoute />;
  if (mockRoute === 'vehicle-setup') return <VehicleSetupRoute />;
  if (mockRoute === 'vehicles') return <Garage />;
  return <Text>{`Home:${resource.status === 'ready' ? resource.data.active_vehicle_id : ''}`}</Text>;
}
function Session({ api }: { api: OnboardingApi }) {
  if (!mockUser) return <Text>Signed out</Text>;
  if (!mockUser.emailVerified) return <Text>Verify email</Text>;
  return <OnboardingProvider uid={mockUser.uid} api={api}><VehicleDataProvider>
    <OnboardingGate><Content /></OnboardingGate>
  </VehicleDataProvider></OnboardingProvider>;
}
beforeEach(() => { jest.clearAllMocks(); mockUser = account; mockRoute = 'dashboard'; });

it('walks first-time users through profile, vehicle and Home using only confirmed server milestones', async () => {
  const { api } = makeApi();
  const view = await render(<Session api={api} />);
  expect(await screen.findByText('redirect:/(main)/profile-setup')).toBeTruthy();
  mockRoute = 'profile-setup'; await view.rerender(<Session api={api} />);
  await fireEvent.changeText(screen.getByLabelText('Full name'), 'Chosen app name');
  await fireEvent.press(screen.getByRole('radio', { name: 'No' }));
  await fireEvent.press(screen.getByRole('button', { name: 'Continue' }));
  expect(await screen.findByText('redirect:/(main)/vehicle-setup')).toBeTruthy();
  expect(api.saveProfile).toHaveBeenCalledWith('alice', { full_name: 'Chosen app name', driving_licence: 'no' });
  mockRoute = 'vehicle-setup'; await view.rerender(<Session api={api} />);
  await chooseVehicleType('Fully Electric (EV)');
  await enterManualVehicle('Any Brand', 'Example EV');
  await fireEvent.press(screen.getByRole('button', { name: 'Continue' }));
  expect(await screen.findByText('redirect:/(main)/dashboard')).toBeTruthy();
  expect(api.saveFirstVehicle).toHaveBeenCalledWith('alice', expect.objectContaining({ powertrain: 'ev', fuelType: null }));
  mockRoute = 'dashboard'; await view.rerender(<Session api={api} />);
  expect(screen.getByText(/^Home:/)).toHaveTextContent(/000000000001/);
});

describe.each(['home', 'vehicles', 'insights', 'history', 'account', 'edit-profile', 'security', 'settings', 'vehicle'])('%s protected destination', route => {
  it.each(['profile', 'vehicle'] as const)('resumes incomplete %s onboarding before exposing the destination', async step => {
    mockRoute = route;
    const { api } = makeApi(step);
    await render(<Session api={api} />);
    expect(await screen.findByText(`redirect:/(main)/${step}-setup`)).toBeTruthy();
    expect(screen.queryByText(/^Home:/)).toBeNull();
  });

  it('allows completed accounts without an onboarding redirect', async () => {
    mockRoute = route;
    const { api } = makeApi('home');
    await render(<Session api={api} />);
    await screen.findByText(route === 'vehicles' ? 'Personal car' : /^Home:/);
    expect(screen.queryByText(/^redirect:/)).toBeNull();
  });
});

it.each(['profile', 'vehicle', 'home'] as const)('restores %s server state after a restart', async step => {
  const { api } = makeApi(step);
  const first = await render(<Session api={api} />);
  await screen.findByText(step === 'home' ? /^Home:/ : `redirect:/(main)/${step}-setup`);
  await first.unmount();
  await render(<Session api={api} />);
  expect(await screen.findByText(step === 'home' ? /^Home:/ : `redirect:/(main)/${step}-setup`)).toBeTruthy();
  expect(api.load).toHaveBeenCalledTimes(2);
});

it('returns completed accounts directly to Home after logout and a restored login without resaving onboarding', async () => {
  const { api } = makeApi('home');
  const view = await render(<Session api={api} />);
  await screen.findByText(/^Home:/);
  mockUser = null; await view.rerender(<Session api={api} />);
  expect(screen.getByText('Signed out')).toBeTruthy();
  mockUser = account; await view.rerender(<Session api={api} />);
  expect(await screen.findByText(/^Home:/)).toBeTruthy();
  expect(screen.queryByText(/^redirect:/)).toBeNull();
  expect(api.load).toHaveBeenCalledTimes(2);
  expect(api.saveProfile).not.toHaveBeenCalled();
  expect(api.saveFirstVehicle).not.toHaveBeenCalled();
});

it('restores completed onboarding with an empty Garage into Home rather than first-vehicle setup', async () => {
  const { api, setState } = makeApi('home');
  setState({ ...accountState('home'), vehicles: [], first_vehicle_id: null, active_vehicle_id: null });
  const view = await render(<Session api={api} />);
  expect(await screen.findByText('Home:null')).toBeTruthy();
  await view.unmount(); await render(<Session api={api} />);
  expect(await screen.findByText('Home:null')).toBeTruthy();
  expect(screen.queryByText(/^redirect:/)).toBeNull();
  expect(api.saveFirstVehicle).not.toHaveBeenCalled();
});

it('offers account Retry only after a failed save and follows the reloaded server completion', async () => {
  const { api, setState } = makeApi('vehicle'); mockRoute = 'vehicle-setup';
  (api.saveFirstVehicle as jest.Mock).mockRejectedValueOnce(new Error('Response unavailable'));
  await render(<Session api={api} />);
  await screen.findByRole('button', { name: 'Engine / Vehicle Type' });
  expect(screen.queryByRole('button', { name: 'Reload account' })).toBeNull();
  expect(screen.queryByRole('button', { name: 'Retry' })).toBeNull();
  expect(screen.getByRole('button', { name: 'Log out' })).toBeEnabled();
  await chooseVehicleType('Fully Electric (EV)');
  await enterManualVehicle('Any Brand', 'Example EV');
  await fireEvent.press(screen.getByRole('button', { name: 'Continue' }));
  expect(screen.queryByText(/^redirect:/)).toBeNull();
  setState(accountState('home'));
  await fireEvent.press(screen.getByRole('button', { name: 'Retry' }));
  expect(await screen.findByText('redirect:/(main)/dashboard')).toBeTruthy();
  expect(api.load).toHaveBeenCalledTimes(2);
  expect(api.saveFirstVehicle).toHaveBeenCalledTimes(1);
});

it('redirects completed accounts away from onboarding deep links without a redirect loop', async () => {
  const { api } = makeApi('home'); mockRoute = 'profile-setup';
  const view = await render(<Session api={api} />);
  expect(await screen.findByText('redirect:/(main)/dashboard')).toBeTruthy();
  mockRoute = 'dashboard'; await view.rerender(<Session api={api} />);
  expect(screen.queryByText(/^redirect:/)).toBeNull();
  expect(screen.getByText(/^Home:/)).toBeTruthy();
});

it('keeps backend load failures outside Home and offers Retry and Logout', async () => {
  const { api } = makeApi();
  (api.load as jest.Mock).mockRejectedValueOnce(new Error('Backend offline'));
  await render(<Session api={api} />);
  expect(await screen.findByText('Backend offline')).toBeTruthy();
  expect(screen.queryByText(/^Home:/)).toBeNull();
  expect(screen.getByRole('button', { name: 'Log out' })).toBeEnabled();
  await fireEvent.press(screen.getByRole('button', { name: 'Retry' }));
  expect(await screen.findByText('redirect:/(main)/profile-setup')).toBeTruthy();
});

it('keeps failed profile saves on the current step and retries without losing the draft', async () => {
  const { api } = makeApi(); mockRoute = 'profile-setup';
  (api.saveProfile as jest.Mock).mockRejectedValueOnce(new Error('Profile storage unavailable'));
  await render(<Session api={api} />);
  await fireEvent.changeText(await screen.findByLabelText('Full name'), 'Keep my draft');
  await fireEvent.press(screen.getByRole('button', { name: 'Continue' }));
  expect(await screen.findByText('Profile storage unavailable')).toBeTruthy();
  expect(screen.getByLabelText('Full name')).toHaveProp('value', 'Keep my draft');
  expect(screen.queryByText(/^redirect:/)).toBeNull();
  await fireEvent.press(screen.getByRole('button', { name: 'Continue' }));
  expect(await screen.findByText('redirect:/(main)/vehicle-setup')).toBeTruthy();
});

it('persists Skip using backend identity fallback rather than completing the entire journey', async () => {
  const { api } = makeApi(); mockRoute = 'profile-setup';
  await render(<Session api={api} />);
  await fireEvent.press(await screen.findByRole('button', { name: 'Skip for now' }));
  expect(api.saveProfile).toHaveBeenCalledWith('alice', { full_name: null, driving_licence: null });
  expect(await screen.findByText('redirect:/(main)/vehicle-setup')).toBeTruthy();
});

it('retains the vehicle draft after a backend failure and advances only after retry succeeds', async () => {
  const { api } = makeApi('vehicle'); mockRoute = 'vehicle-setup';
  (api.saveFirstVehicle as jest.Mock).mockRejectedValueOnce(new Error('Backend unavailable'));
  await render(<Session api={api} />);
  await screen.findByRole('button', { name: 'Engine / Vehicle Type' }); await chooseVehicleType('Fully Electric (EV)');
  await enterManualVehicle('Any Brand', 'Example EV');
  await fireEvent.press(screen.getByRole('button', { name: 'Continue' }));
  expect(await screen.findByText('Could not continue. Please try again.')).toBeTruthy();
  expect(screen.queryByText(/^redirect:/)).toBeNull();
  expect(screen.getByLabelText('Manufacturer')).toHaveProp('value', 'Any Brand');
  await fireEvent.press(screen.getByRole('button', { name: 'Continue' }));
  expect(await screen.findByText('redirect:/(main)/dashboard')).toBeTruthy();
});

it('does not optimistically switch the saved active vehicle when the backend rejects selection', async () => {
  const { api, setState } = makeApi('home'); mockRoute = 'vehicles';
  setState({ ...accountState('home'), vehicles: [savedVehicle(), { ...savedVehicle(), id: secondVehicleId, nickname: 'Second car' }] });
  (api.selectActive as jest.Mock).mockRejectedValueOnce(new Error('Selection not saved'));
  await render(<Session api={api} />);
  await fireEvent.press(await screen.findByRole('button', { name: 'Set Second car active' }));
  expect(await screen.findByText('Selection not saved')).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Set Second car active' })).toBeEnabled();
  expect(screen.getByText('Active vehicle')).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'Set Second car active' }));
  expect(screen.queryByText('Selection not saved')).toBeNull();
  expect(api.selectActive).toHaveBeenCalledTimes(2);
});

it('reloads owned vehicles and active selection into Garage without sending them to the demo provider', async () => {
  const { api, setState } = makeApi('home'); mockRoute = 'vehicles';
  setState({ ...accountState('home'), vehicles: [savedVehicle(), { ...savedVehicle(), id: secondVehicleId, nickname: 'Second car' }] });
  const view = await render(<Session api={api} />);
  expect(await screen.findByText('Personal car')).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Explore simulated Garage' })).toBeTruthy();
  expect(screen.queryByText('My Sedan · Selected')).toBeNull();
  expect(screen.queryByRole('button', { name: 'View Personal car' })).toBeNull();
  await fireEvent.press(screen.getByRole('button', { name: 'Set Second car active' }));
  expect(api.selectActive).toHaveBeenCalledWith('alice', secondVehicleId);
  await view.unmount(); await render(<Session api={api} />);
  expect(await screen.findByText('Second car')).toBeTruthy();
  expect(screen.getByText('Active vehicle')).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'Explore simulated Garage' }));
  expect(mockPush).toHaveBeenCalledWith('/(main)/demo-garage');
  expect(api.selectActive).toHaveBeenCalledTimes(1);
});

it('ignores previous-account responses and restores the new account independently', async () => {
  const { api } = makeApi();
  let resolve!: (state: OnboardingState) => void;
  (api.load as jest.Mock).mockImplementationOnce(() => new Promise(done => { resolve = done; }))
    .mockResolvedValueOnce(accountState('vehicle', 'bob'));
  const view = await render(<Session api={api} />);
  mockUser = { ...account, uid: 'bob', email: 'bob@example.com' };
  await view.rerender(<Session api={api} />);
  expect(await screen.findByText('redirect:/(main)/vehicle-setup')).toBeTruthy();
  await act(async () => resolve(accountState('home', 'alice')));
  expect(screen.queryByText(/^Home:/)).toBeNull();
  expect(screen.getByText('redirect:/(main)/vehicle-setup')).toBeTruthy();
});

it('logs out during onboarding and rechecks the server on the next login', async () => {
  const { api } = makeApi(); mockRoute = 'profile-setup';
  (authService.signOut as jest.Mock).mockImplementation(async () => { mockUser = null; });
  const view = await render(<Session api={api} />);
  await fireEvent.press(await screen.findByRole('button', { name: 'Log out' }));
  await view.rerender(<Session api={api} />);
  expect(screen.getByText('Signed out')).toBeTruthy();
  mockUser = account; mockRoute = 'dashboard'; await view.rerender(<Session api={api} />);
  expect(await screen.findByText('redirect:/(main)/profile-setup')).toBeTruthy();
  expect(api.load).toHaveBeenCalledTimes(2);
});

it('does not request onboarding for signed-out or unverified sessions', async () => {
  const { api } = makeApi(); mockUser = { ...account, emailVerified: false };
  await render(<Session api={api} />);
  expect(screen.getByText('Verify email')).toBeTruthy();
  expect(api.load).not.toHaveBeenCalled();
});

it('prevents a second vehicle mutation while the first is in flight', async () => {
  const { api } = makeApi('vehicle'); mockRoute = 'vehicle-setup';
  let resolve!: (state: OnboardingState) => void;
  (api.saveFirstVehicle as jest.Mock).mockImplementationOnce(() => new Promise(done => { resolve = done; }));
  const user = userEvent.setup();
  await render(<Session api={api} />);
  await screen.findByRole('button', { name: 'Engine / Vehicle Type' }); await chooseVehicleType('Fully Electric (EV)');
  await enterManualVehicle('Any Brand', 'Example EV');
  await user.press(screen.getByRole('button', { name: 'Continue' }));
  await fireEvent.press(screen.getByRole('button', { name: 'Continue' }));
  expect(api.saveFirstVehicle).toHaveBeenCalledTimes(1);
  expect(screen.queryByText(/^redirect:/)).toBeNull();
  await act(async () => resolve(accountState('home')));
  expect(await screen.findByText('redirect:/(main)/dashboard')).toBeTruthy();
});
