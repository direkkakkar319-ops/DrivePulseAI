// Retain the session-only simulated Garage outside account-owned vehicle management.
import { useRouter } from 'expo-router';
import { useVehicles } from '@/store/vehicleDataStore';
import { Button, Copy, Page, State } from '@/components/vehicle-health/ui';
import { VehicleCard } from '@/components/vehicle-health/cards';

export default function DemoGarage() {
  const { vehicles, selectVehicle, activeId, listState, retry } = useVehicles();
  const router = useRouter();
  return <Page title="Demo garage" back={() => router.back()}>
    <Copy muted>Simulated vehicles · changes reset when this session ends. Separate from saved account vehicles and recorded Nissan Leaf data.</Copy>
    <Button title="Add demo vehicle" onPress={() => router.push('/(main)/vehicle/add')} />
    {listState === 'loading' ? <State title="Loading vehicles" loading />
      : listState === 'error' ? <State title="Could not load vehicles" retry={retry} />
        : vehicles.length ? vehicles.map(vehicle => <VehicleCard key={vehicle.id} vehicle={{ ...vehicle,
          name: `${vehicle.name}${vehicle.id === activeId ? ' · Selected' : ''}` }} compact onPress={() => {
          selectVehicle(vehicle.id); router.push({ pathname: '/(main)/vehicle/[id]', params: { id: vehicle.id } });
        }} />) : <State title="No simulated vehicles" />}
  </Page>;
}
