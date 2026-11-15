// Real Garage/Home/provider integration with controlled authenticated-service responses.
import { useState } from 'react';
import { Alert, Text } from 'react-native';
import { act, fireEvent, render, screen, userEvent } from '@testing-library/react-native';
import Garage from '../src/app/(main)/(tabs)/vehicles';
import Home from '../src/app/(main)/(tabs)/home';
import DemoGarage from '../src/app/(main)/demo-garage';
import { OnboardingProvider } from '../src/store/onboardingStore';
import { VehicleDataProvider } from '../src/store/vehicleDataStore';
import { OnboardingGate } from '../src/components/onboarding-gate';
import type { OnboardingApi, OnboardingState, SavedVehicle, VehicleManagementApi } from '../src/api/onboarding';
import type { VehicleSetupValue } from '../src/types/vehicle-setup';
import { accountState, savedVehicle, secondVehicleId } from './onboarding-fixtures';
import { chooseVehicleType, enterManualVehicle } from './vehicle-form-helpers';

const newId = '00000000-0000-4000-8000-000000000003';
const mockPush = jest.fn();
jest.mock('expo-modules-core', () => ({ ...jest.requireActual('expo-modules-core'), uuid: { v4: () => '00000000-0000-4000-8000-000000000003' } }));
jest.mock('../src/api/auth', () => ({ authService: { getToken: jest.fn() } }));
jest.mock('expo-router', () => {
  const React = require('react'); const { Text } = require('react-native');
  return { useRouter: () => ({ push: mockPush, navigate: mockPush, back: jest.fn() }),
    useSegments: () => ['(main)', '(tabs)', 'vehicles'], Redirect: () => React.createElement(Text, null, 'Unexpected onboarding redirect') };
});

const second: SavedVehicle = { ...savedVehicle(), id: secondVehicleId, nickname: 'Second car', powertrain: 'hybrid', fuel_type: 'petrol-electric' };
function service(initial: OnboardingState = { ...accountState('home'), vehicles: [savedVehicle(), second] }) {
  let state = initial;
  const metadata = (value: VehicleSetupValue) => ({ manufacturer: value.manufacturer, model: value.model, year: value.year,
    powertrain: value.powertrain, fuel_type: value.fuelType, nickname: value.nickname });
  const api: OnboardingApi = { load: jest.fn(async () => state), saveProfile: jest.fn(), saveFirstVehicle: jest.fn(),
    selectActive: jest.fn(async (_uid, id) => { state = { ...state, active_vehicle_id: id }; return state; }) };
  const vehicleApi: VehicleManagementApi = {
    create: jest.fn(async (uid, value, id) => { state = { ...state, vehicles: [...state.vehicles, { ...savedVehicle(uid), ...metadata(value), id }],
      active_vehicle_id: state.active_vehicle_id ?? id }; return state; }),
    update: jest.fn(async (_uid, id, value) => { state = { ...state, vehicles: state.vehicles.map(vehicle => vehicle.id === id ? { ...vehicle, ...metadata(value) } : vehicle) }; return state; }),
    remove: jest.fn(async (_uid, id) => {
      const vehicles = state.vehicles.filter(vehicle => vehicle.id !== id);
      state = { ...state, vehicles, first_vehicle_id: state.first_vehicle_id === id ? null : state.first_vehicle_id,
        active_vehicle_id: state.active_vehicle_id === id ? vehicles[0]?.id ?? null : state.active_vehicle_id }; return state;
    }),
  };
  return { api, vehicleApi, current: () => state };
}
function Content() {
  const [home, setHome] = useState(false);
  return <><Text onPress={() => setHome(value => !value)}>Switch tab</Text>{home ? <Home /> : <Garage />}</>;
}
function Session({ api, vehicleApi, uid = 'alice' }: { api: OnboardingApi; vehicleApi: VehicleManagementApi; uid?: string }) {
  return <OnboardingProvider uid={uid} api={api} vehicleApi={vehicleApi}><OnboardingGate><Content /></OnboardingGate></OnboardingProvider>;
}
let alert: jest.SpyInstance;
beforeEach(() => { jest.clearAllMocks(); alert = jest.spyOn(Alert, 'alert').mockImplementation(() => {}); });
afterEach(() => jest.restoreAllMocks());
async function confirm() {
  const buttons = alert.mock.calls.at(-1)![2] as { text: string; onPress?: () => void }[];
  await act(async () => { buttons.find(button => button.text === 'Remove')!.onPress!(); });
}
async function fillNew() {
  await fireEvent.press(await screen.findByRole('button', { name: 'Add Vehicle' }));
  await chooseVehicleType('Fully Electric (EV)');
  await enterManualVehicle('Independent Brand', 'New EV');
}

it('renders saved metadata, active status and separate demo access', async () => {
  const data = service(); await render(<Session {...data} />);
  expect(await screen.findByText('Personal car')).toBeTruthy();
  expect(screen.getByText('Hybrid · Petrol + electric')).toBeTruthy();
  expect(screen.getByText('Active vehicle')).toBeTruthy();
  expect(screen.queryByText('My Sedan')).toBeNull();
  expect(screen.getByRole('button', { name: 'Edit Personal car' })).toBeEnabled();
  await fireEvent.press(screen.getByRole('button', { name: 'Explore simulated Garage' }));
  expect(mockPush).toHaveBeenCalledWith('/(main)/demo-garage');
});

it('adds without switching active vehicle and shares the saved selection with Home', async () => {
  const data = service(); await render(<Session {...data} />); await fillNew();
  await fireEvent.press(screen.getByRole('button', { name: 'Save vehicle' }));
  expect(data.vehicleApi.create).toHaveBeenCalledWith('alice', expect.objectContaining({ manufacturer: 'Independent Brand', nickname: null }), newId);
  expect(await screen.findByText('Independent Brand New EV')).toBeTruthy();
  expect(data.current().active_vehicle_id).toBe(savedVehicle().id);
  await fireEvent.press(screen.getByRole('button', { name: 'Set Independent Brand New EV active' }));
  await fireEvent.press(screen.getByText('Switch tab'));
  expect(await screen.findByText('Independent Brand · New EV · 2024')).toBeTruthy();
  expect(data.current().active_vehicle_id).toBe(newId);
});

it('prefills and edits metadata, retaining the draft after a failed save', async () => {
  const data = service(); (data.vehicleApi.update as jest.Mock).mockRejectedValueOnce(new Error('Offline'));
  await render(<Session {...data} />);
  await fireEvent.press(await screen.findByRole('button', { name: 'Edit Personal car' }));
  expect(screen.getByRole('button', { name: 'Manufacturer' })).toHaveProp('accessibilityValue', { text: 'Any Brand' });
  await fireEvent.changeText(screen.getByLabelText('Vehicle nickname'), 'Renamed car');
  await fireEvent.press(screen.getByRole('button', { name: 'Save vehicle' }));
  expect(screen.getByRole('alert')).toHaveTextContent(/Could not continue/);
  expect(screen.getByLabelText('Vehicle nickname')).toHaveProp('value', 'Renamed car');
  await fireEvent.press(screen.getByRole('button', { name: 'Save vehicle' }));
  expect(await screen.findByText('Renamed car')).toBeTruthy();
  await fireEvent.press(screen.getByText('Switch tab'));
  expect(screen.getByText('Renamed car')).toBeTruthy();
});

it('requires confirmation, explains replacement, and updates Home after active/first deletion', async () => {
  const data = service(); await render(<Session {...data} />);
  await fireEvent.press(await screen.findByRole('button', { name: 'Remove Personal car' }));
  expect(data.vehicleApi.remove).not.toHaveBeenCalled();
  expect(alert.mock.calls[0][1]).toMatch(/oldest remaining saved vehicle/);
  expect(alert.mock.calls[0][1]).toMatch(/onboarding stays complete/);
  await confirm();
  expect(data.current().first_vehicle_id).toBeNull();
  expect(data.current().active_vehicle_id).toBe(secondVehicleId);
  expect(screen.queryByText('Personal car')).toBeNull();
  await fireEvent.press(screen.getByText('Switch tab'));
  expect(screen.getByText('Second car')).toBeTruthy();
});

it('cancels removal without touching the backend', async () => {
  const data = service(); await render(<Session {...data} />);
  await fireEvent.press(await screen.findByRole('button', { name: 'Remove Personal car' }));
  expect(alert.mock.calls[0][2][0]).toMatchObject({ text: 'Cancel', style: 'cancel' });
  expect(data.vehicleApi.remove).not.toHaveBeenCalled();
});

it('keeps onboarding complete after last deletion, restores empty state, and activates a subsequent add', async () => {
  const data = service(accountState('home'));
  const view = await render(<Session {...data} />);
  await fireEvent.press(await screen.findByRole('button', { name: 'Remove Personal car' })); await confirm();
  expect(screen.getByText('No saved vehicles yet')).toBeTruthy();
  expect(screen.queryByText('Unexpected onboarding redirect')).toBeNull();
  expect(data.current().completed_at).toBe(accountState('home').completed_at);
  await view.unmount(); await render(<Session {...data} />);
  await screen.findByText('No saved vehicles yet'); await fillNew();
  await fireEvent.press(screen.getByRole('button', { name: 'Save vehicle' }));
  expect(await screen.findByText('Independent Brand New EV')).toBeTruthy();
  expect(data.current().active_vehicle_id).toBe(newId);
});

it('retains the card after failed deletion and supports retry through confirmation', async () => {
  const data = service(); (data.vehicleApi.remove as jest.Mock).mockRejectedValueOnce(new Error('Delete failed'));
  await render(<Session {...data} />);
  await fireEvent.press(await screen.findByRole('button', { name: 'Remove Personal car' })); await confirm();
  expect(screen.getByRole('alert')).toHaveTextContent('Delete failed');
  expect(screen.getByText('Personal car')).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'Remove Personal car' })); await confirm();
  expect(data.vehicleApi.remove).toHaveBeenCalledTimes(2);
  expect(screen.queryByText('Personal car')).toBeNull();
});

it('shows loading and error/retry states without invented vehicles', async () => {
  const data = service(); let reject!: (error: Error) => void;
  (data.api.load as jest.Mock).mockImplementationOnce(() => new Promise((_done, fail) => { reject = fail; }));
  await render(<OnboardingProvider api={data.api} uid="alice"><Garage /></OnboardingProvider>);
  expect(screen.getByLabelText('Loading your vehicles')).toBeTruthy();
  await act(async () => reject(new Error('Garage unavailable')));
  await fireEvent.press(screen.getByRole('button', { name: 'Try again' }));
  expect(await screen.findByText('Personal car')).toBeTruthy();
});

it('disables add/edit/remove and prevents duplicate creation while saving', async () => {
  const data = service(); let resolve!: (state: OnboardingState) => void;
  (data.vehicleApi.create as jest.Mock).mockImplementationOnce(() => new Promise(done => { resolve = done; }));
  await render(<Session {...data} />); await fillNew();
  await userEvent.setup().press(screen.getByRole('button', { name: 'Save vehicle' }));
  expect(screen.getByRole('button', { name: 'Cancel' })).toBeDisabled();
  expect(screen.getByLabelText('Manufacturer')).toHaveProp('editable', false);
  await fireEvent.press(screen.getByRole('button', { name: 'Save vehicle' }));
  expect(data.vehicleApi.create).toHaveBeenCalledTimes(1);
  await act(async () => resolve(data.current()));
});

it('reuses the creation ID when retrying a failed request', async () => {
  const data = service(); (data.vehicleApi.create as jest.Mock).mockRejectedValueOnce(new Error('Response lost'));
  await render(<Session {...data} />); await fillNew();
  await fireEvent.press(screen.getByRole('button', { name: 'Save vehicle' }));
  await fireEvent.press(screen.getByRole('button', { name: 'Save vehicle' }));
  expect((data.vehicleApi.create as jest.Mock).mock.calls.map(call => call[2])).toEqual([newId, newId]);
});

it('clears editing state on account switch and ignores old-account responses', async () => {
  const data = service(); let resolve!: (state: OnboardingState) => void;
  (data.vehicleApi.update as jest.Mock).mockImplementationOnce(() => new Promise(done => { resolve = done; }));
  const view = await render(<Session {...data} />);
  await fireEvent.press(await screen.findByRole('button', { name: 'Edit Personal car' }));
  await userEvent.setup().press(screen.getByRole('button', { name: 'Save vehicle' }));
  const bob = service({ ...accountState('home', 'bob'), vehicles: [{ ...savedVehicle('bob'), nickname: 'Bob car' }] });
  await view.rerender(<Session {...bob} uid="bob" />);
  expect(await screen.findByText('Bob car')).toBeTruthy();
  await act(async () => resolve(data.current()));
  expect(screen.getByText('Bob car')).toBeTruthy();
  expect(screen.queryByText('Personal car')).toBeNull();
});

it('retains simulated vehicle selection and legacy detail destinations on their separate route', async () => {
  await render(<VehicleDataProvider><DemoGarage /></VehicleDataProvider>);
  await fireEvent.press(await screen.findByRole('button', { name: 'View My Sedan · Selected' }));
  expect(mockPush).toHaveBeenCalledWith(expect.objectContaining({ pathname: '/(main)/vehicle/[id]' }));
});
