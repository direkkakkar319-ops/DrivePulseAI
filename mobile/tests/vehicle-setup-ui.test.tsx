// Exercise first-vehicle metadata entry, conditional controls, and the future storage callback.
import { act, fireEvent, render, screen, userEvent } from '@testing-library/react-native';
import { VehicleSetupForm } from '../src/components/vehicle-setup-form';
import VehicleSetupRoute from '../src/app/(main)/vehicle-setup';
import Index from '../src/app/index';
import type { AuthUser } from '../src/api/auth.types';
import type { VehicleSetupDraft } from '../src/types/vehicle-setup';

const account: AuthUser = { uid: 'vehicle-account', email: 'driver@example.com', displayName: 'Driver', emailVerified: true };
let mockUser: AuthUser | null = account;
let mockCanGoBack = true;
const mockReplace = jest.fn(), mockBack = jest.fn();
const mockSaveVehicle = jest.fn();
jest.mock('../src/store/onboardingStore', () => ({ useOnboarding: () => ({
  resource: { status: 'ready', data: { completed_at: '2026-01-01T00:00:00Z' } }, saving: false,
  saveFirstVehicle: mockSaveVehicle, reload: jest.fn(),
}) }));
jest.mock('../src/store/authStore', () => ({ useAuthStore: () => ({ user: mockUser }) }));
jest.mock('../src/api/auth', () => ({ authService: { signOut: jest.fn() } }));
jest.mock('expo-router', () => {
  const React = require('react');
  const { Text } = require('react-native');
  return {
    useRouter: () => ({ replace: mockReplace, back: mockBack, canGoBack: () => mockCanGoBack }),
    Redirect: ({ href }: { href: string }) => React.createElement(Text, null, `redirect:${href}`),
  };
});

beforeEach(() => { jest.clearAllMocks(); mockUser = account; mockCanGoBack = true; mockSaveVehicle.mockResolvedValue(undefined); });

async function enterVehicle() {
  await fireEvent.changeText(screen.getByLabelText('Manufacturer'), ' Any Manufacturer ');
  await fireEvent.changeText(screen.getByLabelText('Model'), ' Example Model ');
  await fireEvent.changeText(screen.getByLabelText('Model year'), '2024');
}

it('shows required errors on Continue and never submits an incomplete form', async () => {
  const onSubmit = jest.fn();
  await render(<VehicleSetupForm onSubmit={onSubmit} />);
  expect(screen.queryByRole('alert')).toBeNull();
  await fireEvent.press(screen.getByRole('button', { name: 'Continue' }));
  expect(screen.getByText('Choose a powertrain.')).toBeTruthy();
  expect(screen.getByText('Enter a manufacturer.')).toBeTruthy();
  expect(screen.getByText('Enter a model.')).toBeTruthy();
  expect(screen.getByText('Enter a model year.')).toBeTruthy();
  expect(onSubmit).not.toHaveBeenCalled();
});

it('shows ICE fuel choices and submits normalized metadata without an optional nickname', async () => {
  const onSubmit = jest.fn();
  await render(<VehicleSetupForm onSubmit={onSubmit} />);
  await fireEvent.press(screen.getByRole('radio', { name: 'ICE' }));
  for (const name of ['Petrol', 'Diesel', 'CNG']) expect(screen.getByRole('radio', { name })).toBeTruthy();
  await enterVehicle();
  await fireEvent.press(screen.getByRole('button', { name: 'Continue' }));
  expect(screen.getByText('Choose a fuel type for this powertrain.')).toBeTruthy();
  expect(onSubmit).not.toHaveBeenCalled();
  await fireEvent.press(screen.getByRole('radio', { name: 'CNG' }));
  await fireEvent.press(screen.getByRole('button', { name: 'Continue' }));
  expect(onSubmit).toHaveBeenCalledWith({ manufacturer: 'Any Manufacturer', model: 'Example Model', year: 2024,
    powertrain: 'ice', fuelType: 'cng', nickname: null });
});

it('requires a fresh compatible fuel choice when switching from ICE to Hybrid and back', async () => {
  const onSubmit = jest.fn();
  await render(<VehicleSetupForm onSubmit={onSubmit} />);
  await enterVehicle();
  await fireEvent.press(screen.getByRole('radio', { name: 'ICE' }));
  await fireEvent.press(screen.getByRole('radio', { name: 'Petrol' }));
  await fireEvent.press(screen.getByRole('radio', { name: 'Hybrid' }));
  expect(screen.queryByRole('radio', { name: 'Petrol' })).toBeNull();
  expect(screen.getByRole('radio', { name: 'Petrol + electric' })).toHaveProp('accessibilityState', expect.objectContaining({ checked: false }));
  expect(screen.getByRole('radio', { name: 'Diesel + electric' })).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'Continue' }));
  expect(onSubmit).not.toHaveBeenCalled();
  await fireEvent.press(screen.getByRole('radio', { name: 'Petrol + electric' }));
  await fireEvent.press(screen.getByRole('button', { name: 'Continue' }));
  expect(onSubmit).toHaveBeenLastCalledWith(expect.objectContaining({ powertrain: 'hybrid', fuelType: 'petrol-electric' }));
  await fireEvent.press(screen.getByRole('radio', { name: 'ICE' }));
  expect(screen.getByRole('radio', { name: 'Petrol' })).toHaveProp('accessibilityState', expect.objectContaining({ checked: false }));
});

it('hides fuel selection for EV and never submits a previous combustion fuel', async () => {
  const onSubmit = jest.fn();
  await render(<VehicleSetupForm onSubmit={onSubmit} />);
  await enterVehicle();
  await fireEvent.press(screen.getByRole('radio', { name: 'ICE' }));
  await fireEvent.press(screen.getByRole('radio', { name: 'Diesel' }));
  await fireEvent.press(screen.getByRole('radio', { name: 'Fully Electric (EV)' }));
  expect(screen.queryByText('Fuel type')).toBeNull();
  expect(screen.queryByRole('radio', { name: 'Diesel' })).toBeNull();
  await fireEvent.changeText(screen.getByLabelText('Vehicle nickname'), ' My Car ');
  await fireEvent.press(screen.getByRole('button', { name: 'Continue' }));
  expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ powertrain: 'ev', fuelType: null, nickname: 'My Car' }));
  await fireEvent.press(screen.getByRole('radio', { name: 'Hybrid' }));
  expect(screen.getByRole('radio', { name: 'Diesel + electric' })).toHaveProp('accessibilityState', expect.objectContaining({ checked: false }));
});

it('uses a numeric year field and allows correcting validation errors', async () => {
  const onSubmit = jest.fn();
  await render(<VehicleSetupForm onSubmit={onSubmit} />);
  await enterVehicle();
  await fireEvent.press(screen.getByRole('radio', { name: 'Fully Electric (EV)' }));
  expect(screen.getByLabelText('Model year')).toHaveProp('keyboardType', 'number-pad');
  await fireEvent.changeText(screen.getByLabelText('Model year'), '20ab');
  await fireEvent.press(screen.getByRole('button', { name: 'Continue' }));
  expect(screen.getByRole('alert')).toHaveTextContent('Enter a four-digit year using numbers only.');
  expect(onSubmit).not.toHaveBeenCalled();
  await fireEvent.changeText(screen.getByLabelText('Model year'), '2024');
  expect(screen.queryByRole('alert')).toBeNull();
  await fireEvent.press(screen.getByRole('button', { name: 'Continue' }));
  expect(onSubmit).toHaveBeenCalledTimes(1);
});

const initialValues: VehicleSetupDraft = { powertrain: 'ev', manufacturer: 'Any Brand', model: 'Vehicle Model', year: '2024', fuelType: null, nickname: '' };
it('accepts an initial draft and custom submit label for later Garage reuse', async () => {
  const onSubmit = jest.fn();
  await render(<VehicleSetupForm initialValues={initialValues} onSubmit={onSubmit} submitLabel="Add vehicle" />);
  expect(screen.getByLabelText('Manufacturer')).toHaveProp('value', 'Any Brand');
  await fireEvent.press(screen.getByRole('button', { name: 'Add vehicle' }));
  expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ manufacturer: 'Any Brand', powertrain: 'ev' }));
});

it('locks inputs during an asynchronous submit, prevents duplicates, and recovers from failure', async () => {
  let reject!: (reason: Error) => void;
  const onSubmit = jest.fn().mockImplementationOnce(() => new Promise<void>((_, fail) => { reject = fail; })).mockResolvedValueOnce(undefined);
  const user = userEvent.setup();
  await render(<VehicleSetupForm initialValues={initialValues} onSubmit={onSubmit} />);
  await user.press(screen.getByRole('button', { name: 'Continue' }));
  expect(screen.getByRole('button', { name: 'Continue' })).toBeDisabled();
  expect(screen.getByLabelText('Model')).toHaveProp('editable', false);
  for (const radio of screen.getAllByRole('radio')) expect(radio).toBeDisabled();
  await fireEvent.press(screen.getByRole('button', { name: 'Continue' }));
  expect(onSubmit).toHaveBeenCalledTimes(1);
  await act(async () => reject(new Error('Private storage adapter details')));
  expect(screen.getByRole('alert')).toHaveTextContent('Could not continue. Please try again.');
  expect(screen.getByRole('button', { name: 'Continue' })).toBeEnabled();
  expect(screen.getByLabelText('Model')).toHaveProp('value', 'Vehicle Model');
  await fireEvent.press(screen.getByRole('button', { name: 'Continue' }));
  expect(onSubmit).toHaveBeenCalledTimes(2);
  expect(screen.queryByRole('alert')).toBeNull();
});

it('submits valid vehicle metadata to persistent onboarding without navigating before confirmation', async () => {
  await render(<VehicleSetupRoute />);
  expect(mockReplace).not.toHaveBeenCalled();
  expect(screen.getByText('Vehicle setup · Step 1 of 1')).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'Continue' }));
  expect(mockReplace).not.toHaveBeenCalled();
  await enterVehicle();
  await fireEvent.press(screen.getByRole('radio', { name: 'Fully Electric (EV)' }));
  await fireEvent.press(screen.getByRole('button', { name: 'Continue' }));
  expect(mockSaveVehicle).toHaveBeenCalledWith(expect.objectContaining({ powertrain: 'ev', manufacturer: 'Any Manufacturer', fuelType: null }));
  expect(mockReplace).not.toHaveBeenCalled();
});

it('preserves the existing verified-account entry redirect', async () => {
  await render(<Index />);
  expect(screen.getByText('redirect:/(main)/dashboard')).toBeTruthy();
});

it.each([null, { ...account, emailVerified: false }])('does not expose a draft to an unavailable or unverified account', async user => {
  mockUser = user;
  await render(<VehicleSetupRoute />);
  expect(screen.queryByLabelText('Manufacturer')).toBeNull();
});

it('clears a previous account draft on identity change', async () => {
  const view = await render(<VehicleSetupRoute />);
  await enterVehicle();
  mockUser = { ...account, uid: 'another-account' };
  await view.rerender(<VehicleSetupRoute />);
  expect(screen.getByLabelText('Manufacturer')).toHaveProp('value', '');
});

it.each([true, false])('supports Back with existing stack history: %s', async hasHistory => {
  mockCanGoBack = hasHistory;
  await render(<VehicleSetupRoute />);
  await fireEvent.press(screen.getByRole('button', { name: 'Back' }));
  if (hasHistory) expect(mockBack).toHaveBeenCalledTimes(1);
  else expect(mockReplace).toHaveBeenCalledWith('/(main)/dashboard');
});
