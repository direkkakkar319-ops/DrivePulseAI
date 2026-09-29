// Exercise observable state transitions and screen navigation using the real demo provider.
import * as Native from 'react-native';
import { makeSnapshot } from '../src/demo/fixtures';
import { act, fireEvent, render, screen } from '@testing-library/react-native';
import { VehicleDataProvider, useVehicles } from '../src/store/vehicleDataStore';
import { DataGate, DemoControls } from '../src/components/vehicle-health/data-state';
import { Freshness, HealthCard, SensorCards } from '../src/components/vehicle-health/cards';
import { Copy, Button } from '../src/components/vehicle-health/ui';
import Home from '../src/app/(main)/(tabs)/home';
import { VehicleForm } from '../src/components/vehicle-health/vehicle-form';
const mockPush = jest.fn(),
  mockReplace = jest.fn();
jest.mock('expo-router', () => ({
  useRouter: () => ({ push: mockPush, replace: mockReplace, back: jest.fn() }),
}));
jest.mock('../src/store/authStore', () => ({
  useAuthStore: () => ({ user: { displayName: 'Actual user' } }),
}));
function Harness() {
  const { selectVehicle, activeId } = useVehicles();
  return (
    <>
      <Copy>{activeId}</Copy>
      <Button title="Switch vehicle" onPress={() => selectVehicle('SIM-002')} />
      <DataGate>
        {(data) => (
          <>
            <Freshness data={data} />
            {data.assessment && <HealthCard assessment={data.assessment} />}
            <SensorCards data={data} onSelect={jest.fn()} />
          </>
        )}
      </DataGate>
      <DemoControls />
    </>
  );
}
beforeEach(() => jest.clearAllMocks());
it('exposes missing, loading, failed, stale, disconnected and empty states without fake scores', async () => {
  await render(
    <VehicleDataProvider>
      <Harness />
    </VehicleDataProvider>,
  );
  expect(await screen.findByText('Illustrative assessment')).toBeTruthy();
  await fireEvent.press(screen.getByText('Missing sensor values'));
  expect(await screen.findAllByText('Unavailable')).toHaveLength(2);
  expect(screen.queryByText('86')).toBeNull();
  await fireEvent.press(screen.getByText('Stale readings'));
  expect(await screen.findByText(/Stale data/)).toBeTruthy();
  await fireEvent.press(screen.getByText('Disconnected'));
  expect(await screen.findByText(/Disconnected · Stale data/)).toBeTruthy();
  await fireEvent.press(screen.getByText('Failed load'));
  expect(await screen.findByText('Could not load readings')).toBeTruthy();
  await fireEvent.press(screen.getByText('Loading'));
  expect(await screen.findByLabelText('Loading readings')).toBeTruthy();
  await fireEvent.press(screen.getByText('Voltage deviation'));
  expect(await screen.findByText('86')).toBeTruthy();
  await fireEvent.press(screen.getByText('Show empty garage'));
  expect(await screen.findByText('Add your first vehicle')).toBeTruthy();
  await fireEvent.press(screen.getByText('Reset demo vehicles'));
  expect(await screen.findByText('86')).toBeTruthy();
});
it('changes the active vehicle without retaining the prior vehicle assessment', async () => {
  await render(
    <VehicleDataProvider>
      <Harness />
    </VehicleDataProvider>,
  );
  expect(await screen.findByText('86')).toBeTruthy();
  await fireEvent.press(screen.getByText('Switch vehicle'));
  expect(await screen.findByText('SIM-002')).toBeTruthy();
  await act(async () => {});
  expect(screen.queryByText('86')).toBeNull();
});
it('uses real account identity and routes cards with explicit vehicle context', async () => {
  await render(
    <VehicleDataProvider>
      <Home />
    </VehicleDataProvider>,
  );
  expect(await screen.findByText('Hello, Actual user')).toBeTruthy();
  await fireEvent.press(await screen.findByText('Battery voltage deviation'));
  expect(mockPush).toHaveBeenCalledWith({
    pathname: '/(main)/insight/[id]',
    params: { id: 'SIM-001-voltage', vehicleId: 'SIM-001' },
  });
  await fireEvent.press(screen.getByText('View report preview'));
  expect(mockPush).toHaveBeenCalledWith({
    pathname: '/(main)/report/[id]',
    params: { id: 'SIM-001' },
  });
});
it('saves a session-only vehicle without requesting inferred telemetry', async () => {
  await render(
    <VehicleDataProvider>
      <VehicleForm />
    </VehicleDataProvider>,
  );
  await fireEvent.press(screen.getByText('Save demo vehicle'));
  expect(await screen.findByText('Enter a vehicle name.')).toBeTruthy();
  await fireEvent.changeText(screen.getByLabelText('Vehicle name'), 'My new car');
  await fireEvent.press(screen.getByText('Save demo vehicle'));
  expect(mockReplace).toHaveBeenCalledWith({
    pathname: '/(main)/vehicle/[id]',
    params: { id: 'SIM-004' },
  });
});

it('shows waiting, collecting and unavailable assessment without a numeric score', async () => {
  await render(
    <VehicleDataProvider>
      <Home />
      <DemoControls />
    </VehicleDataProvider>,
  );
  await fireEvent.press(await screen.findByText('Waiting for readings'));
  expect(await screen.findByText('Last updated unavailable')).toBeTruthy();
  expect(screen.queryByText('86')).toBeNull();
  await fireEvent.press(screen.getByText('Collecting data'));
  expect(
    await screen.findByText('This demo represents an incomplete assessment window.'),
  ).toBeTruthy();
  await fireEvent.press(screen.getAllByText('Assessment unavailable')[0]);
  expect(
    await screen.findByText(
      'No model assessment is available. Missing assessments are not health scores.',
    ),
  ).toBeTruthy();
});

it.each([
  { width: 320, fontScale: 1, expected: '100%' },
  { width: 390, fontScale: 1, expected: '48%' },
  { width: 768, fontScale: 1, expected: '48%' },
  { width: 390, fontScale: 1.6, expected: '100%' },
])(
  'adapts sensor cards at $width px with font scale $fontScale',
  async ({ width, fontScale, expected }) => {
    const original = Native.Dimensions.get('window');
    Native.Dimensions.set({ window: { width, height: 844, scale: 1, fontScale } });
    try {
      await render(
        <SensorCards preview data={makeSnapshot('SIM-001', 'voltage')} onSelect={jest.fn()} />,
      );
      const card = screen.getByLabelText('Battery voltage history');
      expect(Native.StyleSheet.flatten(card.props.style).width).toBe(expected);
    } finally {
      await act(async () => Native.Dimensions.set({ window: original }));
    }
  },
);
