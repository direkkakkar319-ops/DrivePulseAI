// Session-only garage with explicit active-vehicle selection.
import { useRouter } from 'expo-router';
import { useVehicles } from '@/store/vehicleDataStore';
import { Button, Copy, Page, State } from '@/components/vehicle-health/ui';
import { VehicleCard } from '@/components/vehicle-health/cards';
export default function Vehicles() {
  const { vehicles, selectVehicle, activeId, listState, retry } = useVehicles();
  const router = useRouter();
  return (
    <Page title="My vehicles">
      <Copy muted>Demo garage · changes reset when this session ends.</Copy>
      <Button title="Add vehicle" onPress={() => router.push('/(main)/vehicle/add')} />
      {listState === 'loading' ? (
        <State title="Loading vehicles" loading />
      ) : listState === 'error' ? (
        <State title="Could not load vehicles" retry={retry} />
      ) : vehicles.length ? (
        vehicles.map((vehicle) => (
          <VehicleCard
            key={vehicle.id}
            vehicle={{
              ...vehicle,
              name: `${vehicle.name}${vehicle.id === activeId ? ' · Selected' : ''}`,
            }}
            compact
            onPress={() => {
              selectVehicle(vehicle.id);
              router.push({ pathname: '/(main)/vehicle/[id]', params: { id: vehicle.id } });
            }}
          />
        ))
      ) : (
        <State
          title="Your garage is empty"
          message="Add your first vehicle to explore the prototype."
        />
      )}
    </Page>
  );
}
