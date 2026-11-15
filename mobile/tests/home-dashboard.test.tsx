// Exercise the real Home route and account provider with a controllable persistent-service boundary.
import { act, fireEvent, render, screen, userEvent } from '@testing-library/react-native';
import Home from '../src/app/(main)/(tabs)/home';
import { OnboardingProvider } from '../src/store/onboardingStore';
import type { OnboardingApi, OnboardingState, SavedVehicle } from '../src/api/onboarding';
import { accountState, savedVehicle, secondVehicleId } from './onboarding-fixtures';

const mockNavigate = jest.fn();
const mockPush = jest.fn();
jest.mock('expo-router', () => ({ useRouter: () => ({ navigate: mockNavigate, push: mockPush }) }));
jest.mock('../src/api/auth', () => ({ authService: { getToken: jest.fn() } }));

const secondVehicle: SavedVehicle = { ...savedVehicle(), id: secondVehicleId, nickname: null,
  manufacturer: 'Independent Motors', model: 'Tourer', year: 2022, powertrain: 'ice', fuel_type: 'petrol' };

function service(initial: OnboardingState = { ...accountState('home'), vehicles: [savedVehicle(), secondVehicle] }) {
  let server = initial;
  const api: OnboardingApi = {
    load: jest.fn(async () => server),
    selectActive: jest.fn(async (_uid, id) => { server = { ...server, active_vehicle_id: id }; return server; }),
    saveProfile: jest.fn(), saveFirstVehicle: jest.fn(),
  };
  return { api, current: () => server };
}
function Session({ api, uid = 'alice' }: { api: OnboardingApi; uid?: string }) {
  return <OnboardingProvider uid={uid} api={api}><Home /></OnboardingProvider>;
}
beforeEach(() => jest.clearAllMocks());

it('shows the account active vehicle and metadata without requiring demo or replay providers', async () => {
  const { api } = service();
  await render(<Session api={api} />);
  expect(await screen.findByText('Personal car')).toBeTruthy();
  expect(screen.getByText('Any Brand · Example EV · 2024')).toBeTruthy();
  expect(screen.getByText('Fully Electric (EV)')).toBeTruthy();
  expect(screen.queryByText(/^Fuel:/)).toBeNull();
  expect(screen.getByRole('header', { name: 'Home' })).toBeTruthy();
  expect(screen.getByText('DrivePulse AI')).toBeTruthy();
  expect(screen.queryByText(/My Sedan|Illustrative assessment|High-voltage battery/)).toBeNull();
});

it.each([
  ['ice', 'petrol', 'ICE', 'Petrol'], ['ice', 'cng', 'ICE', 'CNG'],
  ['hybrid', 'petrol-electric', 'Hybrid', 'Petrol + electric'],
  ['hybrid', 'diesel-electric', 'Hybrid', 'Diesel + electric'],
] as const)('renders %s / %s using the existing fuel labels', async (powertrain, fuel_type, label, fuelLabel) => {
  const vehicle: SavedVehicle = { ...savedVehicle(), nickname: null, powertrain, fuel_type };
  const { api } = service({ ...accountState('home'), vehicles: [vehicle] });
  await render(<Session api={api} />);
  expect(await screen.findByText('Any Brand Example EV')).toBeTruthy();
  expect(screen.getByText(label)).toBeTruthy();
  expect(screen.getByText(`Fuel: ${fuelLabel}`)).toBeTruthy();
  expect(screen.queryByRole('button', { name: 'Choose vehicle' })).toBeNull();
});

it('switches saved vehicles through the account API and restores the confirmed selection after remount', async () => {
  const { api, current } = service();
  const view = await render(<Session api={api} />);
  await fireEvent.press(await screen.findByRole('button', { name: 'Choose vehicle' }));
  expect(screen.getByRole('button', { name: 'Select Personal car, 2024' }))
    .toHaveProp('accessibilityState', expect.objectContaining({ selected: true }));
  await fireEvent.press(screen.getByRole('button', { name: 'Select Independent Motors Tourer, 2022' }));
  expect(api.selectActive).toHaveBeenCalledWith('alice', secondVehicleId);
  expect(current().active_vehicle_id).toBe(secondVehicleId);
  expect(screen.getByText('Independent Motors · Tourer · 2022')).toBeTruthy();
  expect(screen.queryByText('Personal car')).toBeNull();
  expect(screen.getByRole('button', { name: 'Choose vehicle' })).toHaveProp('accessibilityState', expect.objectContaining({ expanded: false }));
  await view.unmount();
  await render(<Session api={api} />);
  expect(await screen.findByText('Independent Motors Tourer')).toBeTruthy();
  expect(api.load).toHaveBeenCalledTimes(2);
});

it('closes selection without saving when the current vehicle is selected', async () => {
  const { api } = service();
  await render(<Session api={api} />);
  await fireEvent.press(await screen.findByRole('button', { name: 'Choose vehicle' }));
  await fireEvent.press(screen.getByRole('button', { name: 'Select Personal car, 2024' }));
  expect(api.selectActive).not.toHaveBeenCalled();
  expect(screen.queryByText('Choose a saved vehicle')).toBeNull();
});

it('keeps the confirmed vehicle during saving, disables selection, and prevents duplicate submissions', async () => {
  const { api } = service();
  let resolve!: (state: OnboardingState) => void;
  (api.selectActive as jest.Mock).mockImplementationOnce(() => new Promise(done => { resolve = done; }));
  await render(<Session api={api} />);
  await fireEvent.press(await screen.findByRole('button', { name: 'Choose vehicle' }));
  const user = userEvent.setup();
  await user.press(screen.getByRole('button', { name: 'Select Independent Motors Tourer, 2022' }));
  expect(screen.getByText('Any Brand · Example EV · 2024')).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Saving active vehicle…' })).toBeDisabled();
  const option = screen.getByRole('button', { name: 'Select Independent Motors Tourer, 2022' });
  expect(option).toBeDisabled();
  await fireEvent.press(option);
  expect(api.selectActive).toHaveBeenCalledTimes(1);
  await act(async () => resolve({ ...accountState('home'), vehicles: [savedVehicle(), secondVehicle], active_vehicle_id: secondVehicleId }));
  expect(screen.getByText('Independent Motors · Tourer · 2022')).toBeTruthy();
});

it('retains the previous vehicle on a backend error and retries the intended selection', async () => {
  const { api } = service();
  (api.selectActive as jest.Mock).mockRejectedValueOnce(new Error('Selection not saved'));
  await render(<Session api={api} />);
  await fireEvent.press(await screen.findByRole('button', { name: 'Choose vehicle' }));
  await fireEvent.press(screen.getByRole('button', { name: 'Select Independent Motors Tourer, 2022' }));
  expect(screen.getByRole('alert')).toHaveTextContent('Could not switch vehicle');
  expect(screen.getByText('Selection not saved')).toBeTruthy();
  expect(screen.getByText('Any Brand · Example EV · 2024')).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'Retry vehicle selection' }));
  expect(api.selectActive).toHaveBeenNthCalledWith(2, 'alice', secondVehicleId);
  expect(screen.getByText('Independent Motors · Tourer · 2022')).toBeTruthy();
  expect(screen.queryByRole('alert')).toBeNull();
});

it('handles an empty Garage without choosing a demo vehicle', async () => {
  const { api } = service(accountState('vehicle'));
  await render(<Session api={api} />);
  expect(await screen.findByText('No saved vehicles yet')).toBeTruthy();
  expect(screen.queryByRole('button', { name: 'Choose vehicle' })).toBeNull();
  await fireEvent.press(screen.getByRole('button', { name: 'Open Garage' }));
  expect(mockNavigate).toHaveBeenCalledWith('/(main)/(tabs)/vehicles');
  expect(api.selectActive).not.toHaveBeenCalled();
});

it('offers explicit selection if saved vehicles have no active record', async () => {
  const { api } = service({ ...accountState('home'), active_vehicle_id: null });
  await render(<Session api={api} />);
  expect(await screen.findByText('Choose an active vehicle')).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'Choose vehicle' }));
  await fireEvent.press(screen.getByRole('button', { name: 'Select Personal car, 2024' }));
  expect(api.selectActive).toHaveBeenCalledWith('alice', savedVehicle().id);
});

it('shows loading and recovers from load errors through the existing account reload', async () => {
  const { api } = service();
  let reject!: (error: Error) => void;
  (api.load as jest.Mock).mockImplementationOnce(() => new Promise((_done, fail) => { reject = fail; }));
  await render(<Session api={api} />);
  expect(screen.getByLabelText('Loading your vehicles')).toBeTruthy();
  expect(screen.queryByText('Personal car')).toBeNull();
  await act(async () => reject(new Error('Account service offline')));
  expect(screen.getByText('Account service offline')).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'Try again' }));
  expect(await screen.findByText('Personal car')).toBeTruthy();
  expect(api.load).toHaveBeenCalledTimes(2);
});

it('shows honest connection and analysis empty states, and navigates to History', async () => {
  const { api } = service();
  await render(<Session api={api} />);
  await screen.findByText('Personal car');
  expect(screen.getByText('OBD connectivity coming soon')).toBeTruthy();
  expect(screen.getByText('No saved analyses yet')).toBeTruthy();
  expect(screen.queryByText(/TRIP|health score|connected successfully/i)).toBeNull();
  await fireEvent.press(screen.getByRole('button', { name: 'View History' }));
  expect(mockNavigate).toHaveBeenCalledWith('/(main)/(tabs)/history');
});

it('opens generic demo Insights without fabricating history and preserves separate recorded tools', async () => {
  const { api } = service();
  await render(<Session api={api} />);
  await screen.findByText('Personal car');
  expect(screen.getByRole('header', { name: 'Explore Demo Data' })).toBeTruthy();
  expect(screen.queryByText(/Nissan Leaf/i)).toBeNull();
  expect(screen.getByText('No saved analyses yet')).toBeTruthy();
  expect(screen.queryByText('94.2%')).toBeNull();
  await fireEvent.press(screen.getByRole('button', { name: 'Explore Demo Data' }));
  expect(mockNavigate).toHaveBeenCalledWith({ pathname: '/(main)/(tabs)/insights', params: { demo: expect.any(String) } });
  expect(api.selectActive).not.toHaveBeenCalled();
  await fireEvent.press(screen.getByRole('button', { name: 'View recorded telemetry' }));
  expect(mockNavigate).toHaveBeenCalledWith('/(main)/(tabs)/telemetry');
  await fireEvent.press(screen.getByRole('button', { name: 'Open recorded replay' }));
  expect(mockPush).toHaveBeenCalledWith('/(main)/replay');
});

it('clears the old account vehicle and ignores its pending selection response after account switching', async () => {
  const { api } = service();
  let resolve!: (state: OnboardingState) => void;
  (api.selectActive as jest.Mock).mockImplementationOnce(() => new Promise(done => { resolve = done; }));
  const view = await render(<Session api={api} />);
  await fireEvent.press(await screen.findByRole('button', { name: 'Choose vehicle' }));
  await userEvent.setup().press(screen.getByRole('button', { name: 'Select Independent Motors Tourer, 2022' }));
  const bob = service({ ...accountState('home', 'bob'), vehicles: [{ ...savedVehicle('bob'), nickname: 'Bob car' }] });
  await view.rerender(<Session api={bob.api} uid="bob" />);
  expect(await screen.findByText('Bob car')).toBeTruthy();
  expect(screen.queryByText('Personal car')).toBeNull();
  await act(async () => resolve({ ...accountState('home'), vehicles: [savedVehicle(), secondVehicle], active_vehicle_id: secondVehicleId }));
  expect(screen.getByText('Bob car')).toBeTruthy();
  expect(screen.queryByText('Independent Motors Tourer')).toBeNull();
  expect(screen.queryByRole('alert')).toBeNull();
});
