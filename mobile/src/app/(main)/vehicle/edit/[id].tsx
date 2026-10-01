// Edit only a vehicle already present in this demo session.
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useRouteVehicle } from '@/hooks/use-route-vehicle';
import { VehicleForm } from '@/components/vehicle-health/vehicle-form';
import { Page, State } from '@/components/vehicle-health/ui';
export default function EditVehicle() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { vehicle, pending } = useRouteVehicle(id);
  const router = useRouter();
  return pending ? (
    <Page>
      <State title="Loading vehicle" loading />
    </Page>
  ) : vehicle ? (
    <VehicleForm key={vehicle.id} vehicle={vehicle} />
  ) : (
    <Page title="Manage vehicle" back={() => router.back()}>
      <State title="Vehicle not found" />
    </Page>
  );
}
