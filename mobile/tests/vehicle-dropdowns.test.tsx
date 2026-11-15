// Local demo dependency filtering, explicit type/fuel selection and preservation of existing metadata.
import { fireEvent, render, screen, within } from '@testing-library/react-native';
import { VehicleSetupForm } from '../src/components/vehicle-setup-form';
import { chooseVehicleOption, chooseVehicleType, enterManualVehicle } from './vehicle-form-helpers';

const originalFetch = global.fetch;
beforeEach(() => { global.fetch = jest.fn(); });
afterEach(() => { global.fetch = originalFetch; });
async function chooseModel(manufacturer: string, model: string, year?: string) {
  await chooseVehicleOption('Manufacturer', manufacturer);
  await chooseVehicleOption('Model', model);
  if (year) await chooseVehicleOption('Model year', year);
}

it('uses only the local demo catalog and filters models by manufacturer without network requests', async () => {
  await render(<VehicleSetupForm onSubmit={jest.fn()} />);
  expect(screen.getByRole('button', { name: 'Model' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Model year' })).toBeDisabled();
  await fireEvent.press(screen.getByRole('button', { name: 'Manufacturer' }));
  for (const name of ['Mahindra', 'Hyundai', 'Ferrari']) expect(screen.getByRole('button', { name })).toBeTruthy();
  await fireEvent.changeText(screen.getByLabelText('Search manufacturer'), 'hyun');
  expect(screen.queryByRole('button', { name: 'Mahindra' })).toBeNull();
  await fireEvent.press(screen.getByRole('button', { name: 'Hyundai' }));
  await fireEvent.press(screen.getByRole('button', { name: 'Model' }));
  expect(screen.getByRole('button', { name: 'Creta' })).toBeTruthy();
  expect(screen.getByRole('button', { name: 'i20' })).toBeTruthy();
  expect(screen.queryByRole('button', { name: 'Thar' })).toBeNull();
  expect(fetch).not.toHaveBeenCalled();
});

it('resets year after a model change and resets model/year after a manufacturer change', async () => {
  await render(<VehicleSetupForm onSubmit={jest.fn()} />);
  await chooseModel('Mahindra', 'Thar', '2020');
  await chooseVehicleOption('Model', 'XUV700');
  expect(screen.getByRole('button', { name: 'Model year' })).toHaveProp('accessibilityValue', { text: 'Not selected' });
  await fireEvent.press(screen.getByRole('button', { name: 'Model year' }));
  const options = within(screen.getByTestId('Model year options'));
  expect(options.queryByRole('button', { name: '2020' })).toBeNull();
  expect(options.getAllByRole('button').map(button => button.props.accessibilityLabel).slice(1)).toEqual(['2024', '2023', '2022', '2021']);
  await fireEvent.press(options.getByRole('button', { name: '2024' }));
  await chooseVehicleOption('Manufacturer', 'Ferrari');
  for (const name of ['Model', 'Model year']) expect(screen.getByRole('button', { name })).toHaveProp('accessibilityValue', { text: 'Not selected' });
  expect(screen.getByRole('button', { name: 'Model year' })).toBeDisabled();
});

it('restricts verified Ferrari configurations without silently selecting a type or fuel', async () => {
  const submit = jest.fn(); await render(<VehicleSetupForm onSubmit={submit} />);
  await chooseVehicleType('ICE'); await chooseVehicleOption('Fuel type', 'Diesel');
  await chooseModel('Ferrari', '296 GTB', '2024');
  expect(screen.getByRole('button', { name: 'Engine / Vehicle Type' })).toHaveProp('accessibilityValue', { text: 'Not selected' });
  await fireEvent.press(screen.getByRole('button', { name: 'Engine / Vehicle Type' }));
  expect(screen.queryByRole('button', { name: 'Combustion engine (ICE)' })).toBeNull();
  expect(screen.queryByRole('button', { name: 'Fully Electric (EV)' })).toBeNull();
  await fireEvent.press(screen.getByRole('button', { name: 'Hybrid' }));
  await fireEvent.press(screen.getByRole('button', { name: 'Fuel type' }));
  expect(screen.queryByRole('button', { name: 'Diesel + electric' })).toBeNull();
  await fireEvent.press(screen.getByRole('button', { name: 'Petrol + electric' }));
  await fireEvent.press(screen.getByRole('button', { name: 'Continue' }));
  expect(submit).toHaveBeenCalledWith({ manufacturer: 'Ferrari', model: '296 GTB', year: 2024, powertrain: 'hybrid', fuelType: 'petrol-electric', nickname: null });
});

it('retains generic ICE/Hybrid/EV choices where no model configuration is certified', async () => {
  const submit = jest.fn(); await render(<VehicleSetupForm onSubmit={submit} />);
  await chooseModel('Hyundai', 'i20', '2024');
  await chooseVehicleType('ICE'); await chooseVehicleOption('Fuel type', 'CNG');
  await chooseVehicleType('Hybrid');
  expect(screen.getByRole('button', { name: 'Fuel type' })).toHaveProp('accessibilityValue', { text: 'Not selected' });
  await chooseVehicleOption('Fuel type', 'Diesel + electric');
  await chooseVehicleType('Fully Electric (EV)');
  expect(screen.queryByRole('button', { name: 'Fuel type' })).toBeNull();
  await fireEvent.press(screen.getByRole('button', { name: 'Continue' }));
  expect(submit).toHaveBeenCalledWith(expect.objectContaining({ powertrain: 'ev', fuelType: null }));
});

it('preserves unlisted saved vehicles and optional nickname without fetching a catalog', async () => {
  const submit = jest.fn(); await render(<VehicleSetupForm onSubmit={submit} submitLabel="Save vehicle" initialValues={{
    manufacturer: 'Unlisted Brand', model: 'Older model', year: '1990', powertrain: 'hybrid', fuelType: 'diesel-electric', nickname: 'My car',
  }} />);
  for (const [label, text] of [['Manufacturer', 'Unlisted Brand'], ['Model', 'Older model'], ['Model year', '1990'], ['Fuel type', 'Diesel + electric']]) {
    expect(screen.getByRole('button', { name: label })).toHaveProp('accessibilityValue', { text });
  }
  await fireEvent.press(screen.getByRole('button', { name: 'Save vehicle' }));
  expect(submit).toHaveBeenCalledWith(expect.objectContaining({ manufacturer: 'Unlisted Brand', year: 1990, nickname: 'My car' }));
  expect(fetch).not.toHaveBeenCalled();
});

it('does not erase a saved year or configuration outside the curated demo generation', async () => {
  const submit = jest.fn(); await render(<VehicleSetupForm onSubmit={submit} initialValues={{ manufacturer: 'Mahindra', model: 'Thar', year: '2010', powertrain: 'ev', fuelType: null, nickname: '' }} />);
  await fireEvent.press(screen.getByRole('button', { name: 'Model year' }));
  expect(within(screen.getByTestId('Model year options')).queryByRole('button', { name: '2010' })).toBeNull();
  await fireEvent.press(screen.getByRole('button', { name: 'Close model year selection' }));
  await fireEvent.press(screen.getByRole('button', { name: 'Continue' }));
  expect(submit).toHaveBeenCalledWith(expect.objectContaining({ year: 2010, powertrain: 'ev', fuelType: null }));
});

it('provides unrestricted manual entry for unlisted vehicles and searchable historic years', async () => {
  const submit = jest.fn(); await render(<VehicleSetupForm onSubmit={submit} />);
  await enterManualVehicle('Independent Brand', 'Legacy model', '1886');
  await chooseVehicleType('Fully Electric (EV)');
  await fireEvent.press(screen.getByRole('button', { name: 'Continue' }));
  expect(submit).toHaveBeenCalledWith(expect.objectContaining({ manufacturer: 'Independent Brand', model: 'Legacy model', year: 1886 }));
  expect(fetch).not.toHaveBeenCalled();
});

it('shows Retry only after failure and retries genuine submissions without losing the draft', async () => {
  const submit = jest.fn().mockRejectedValueOnce(new Error('Backend offline')).mockResolvedValueOnce(undefined);
  await render(<VehicleSetupForm onSubmit={submit} initialValues={{ manufacturer: 'Unlisted', model: 'Car', year: '2024', powertrain: 'ev', fuelType: null, nickname: '' }} />);
  expect(screen.queryByRole('button', { name: 'Retry' })).toBeNull();
  await fireEvent.press(screen.getByRole('button', { name: 'Continue' }));
  await fireEvent.press(screen.getByRole('button', { name: 'Retry' }));
  expect(submit).toHaveBeenCalledTimes(2);
  expect(screen.getByRole('button', { name: 'Model' })).toHaveProp('accessibilityValue', { text: 'Car' });
});
