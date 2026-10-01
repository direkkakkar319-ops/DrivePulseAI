// Resolve a nested route's vehicle before rendering data from shared selection state.
import { useCallback } from 'react';
import { useFocusEffect } from 'expo-router';
import { useVehicles } from '@/store/vehicleDataStore';
export function useRouteVehicle(id: string | undefined) {
  const { vehicles, activeId, selectVehicle, listState } = useVehicles();
  const vehicle = vehicles.find((v) => v.id === id);
  // A covered stack screen must not restore its old vehicle when another screen
  // changes selection. Synchronize only while this route is focused.
  useFocusEffect(
    useCallback(() => {
      if (vehicle && activeId !== vehicle.id) selectVehicle(vehicle.id);
    }, [vehicle, activeId, selectVehicle]),
  );
  return { vehicle, pending: listState === 'loading' || (!!vehicle && activeId !== vehicle.id) };
}
