// Shared real dropdown interactions used by onboarding and persisted Garage regression tests.
import { fireEvent, screen } from '@testing-library/react-native';

export async function chooseVehicleOption(label: string, value: string) {
  await fireEvent.press(screen.getByRole('button', { name: label }));
  if (label === 'Model year') await fireEvent.changeText(screen.getByLabelText('Search model year'), value);
  await fireEvent.press(await screen.findByRole('button', { name: value }));
}

export async function chooseVehicleType(value: string) {
  await chooseVehicleOption('Engine / Vehicle Type', value === 'ICE' ? 'Combustion engine (ICE)' : value);
}

export async function enterManualVehicle(manufacturer: string, model: string, year = '2024') {
  if (screen.queryByRole('button', { name: 'Manufacturer' })) await chooseVehicleOption('Manufacturer', 'Other / Not Listed');
  await fireEvent.changeText(screen.getByLabelText('Manufacturer'), manufacturer);
  if (screen.queryByRole('button', { name: 'Model' })) await chooseVehicleOption('Model', 'Other / Not Listed');
  await fireEvent.changeText(screen.getByLabelText('Model'), model);
  await chooseVehicleOption('Model year', year);
}
