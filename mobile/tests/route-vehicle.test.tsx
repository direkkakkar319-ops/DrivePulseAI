// Covered stack routes must not override the active screen's vehicle selection.
import { renderHook, waitFor } from '@testing-library/react-native';
import { useRouteVehicle } from '../src/hooks/use-route-vehicle';
const mockSelect = jest.fn();
let mockFocused = false;
jest.mock('expo-router', () => ({
  useFocusEffect: (callback: () => void) => {
    const React = require('react');
    React.useEffect(() => {
      if (mockFocused) return callback();
    }, [callback]);
  },
}));
jest.mock('../src/store/vehicleDataStore', () => ({
  useVehicles: () => ({
    vehicles: [{ id: 'SIM-001' }, { id: 'SIM-002' }],
    activeId: 'SIM-002',
    selectVehicle: mockSelect,
    listState: 'ready',
  }),
}));
it('only restores the route vehicle when focused', async () => {
  mockSelect.mockClear();
  mockFocused = false;
  const { rerender } = await renderHook(() => useRouteVehicle('SIM-001'));
  expect(mockSelect).not.toHaveBeenCalled();
  mockFocused = true;
  await rerender(undefined);
  await waitFor(() => expect(mockSelect).toHaveBeenCalledWith('SIM-001'));
});
it('does not select unknown vehicles', async () => {
  mockSelect.mockClear();
  mockFocused = true;
  const { result } = await renderHook(() => useRouteVehicle('missing'));
  expect(result.current.vehicle).toBeUndefined();
  expect(mockSelect).not.toHaveBeenCalled();
});
