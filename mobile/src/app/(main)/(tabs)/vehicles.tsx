// Session-only garage with explicit active-vehicle selection.
import { useRouter } from 'expo-router';
import { useState } from 'react';
import { useVehicles } from '@/store/vehicleDataStore';
import { Button, Card, Copy, Page, State } from '@/components/vehicle-health/ui';
import { VehicleCard } from '@/components/vehicle-health/cards';
import { useOnboarding } from '@/store/onboardingStore';
export default function Vehicles() {
  const { vehicles, selectVehicle, activeId, listState, retry } = useVehicles();
  const router = useRouter();
  const saved = useOnboarding();
  const [error, setError] = useState('');
  async function activate(id: string) {
    setError('');
    try { await saved.selectActive(id); } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not select the vehicle. Try again.'); }
  }
  return (
    <Page title="My vehicles">
      <Copy style={{ fontSize: 18, fontWeight: '600' }}>Saved vehicles</Copy>
      {saved.resource.status === 'ready' ? saved.resource.data.vehicles.map(vehicle => <Card key={vehicle.id}>
        <Copy style={{ fontSize: 20, fontWeight: '600' }}>{vehicle.nickname || `${vehicle.manufacturer} ${vehicle.model}`}</Copy>
        <Copy>{vehicle.manufacturer} · {vehicle.model} · {vehicle.year}</Copy>
        <Copy muted>{vehicle.powertrain.toUpperCase()} · {vehicle.fuel_type?.replaceAll('-', ' + ') ?? 'Electric'}</Copy>
        <Copy muted>Saved to your account · No connected telemetry</Copy>
        <Button title={saved.resource.status === 'ready' && saved.resource.data.active_vehicle_id === vehicle.id ? 'Active vehicle' : 'Make active'}
          disabled={saved.saving || (saved.resource.status === 'ready' && saved.resource.data.active_vehicle_id === vehicle.id)}
          onPress={() => { void activate(vehicle.id); }} />
      </Card>) : <State title="Saved vehicles unavailable" retry={() => { void saved.reload(); }} />}
      {!!error && <State title="Vehicle selection failed" message={error} />}
      <Copy style={{ fontSize: 18, fontWeight: '600' }}>Demo garage</Copy>
      <Copy muted>Demo garage · changes reset when this session ends.</Copy>
      <Button title="Add demo vehicle" onPress={() => router.push('/(main)/vehicle/add')} />
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
