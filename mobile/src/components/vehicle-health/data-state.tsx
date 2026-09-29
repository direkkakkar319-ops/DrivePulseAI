// Shared selectors and availability gates keep source and missing-state behavior consistent.
import type { PropsWithChildren } from 'react';
import { useRouter } from 'expo-router';
import { useVehicles } from '@/store/vehicleDataStore';
import type { VehicleSnapshot } from '@/types/vehicle-health';
import { scenarios } from '@/demo/fixtures';
import { Button, Card, Chips, Copy, State } from './ui';
export function VehicleSelector() {
  const { vehicles, activeId, selectVehicle } = useVehicles();
  return vehicles.length > 1 ? (
    <Chips
      values={vehicles.map((v) => ({ id: v.id, label: v.name }))}
      selected={activeId ?? ''}
      onSelect={selectVehicle}
    />
  ) : null;
}
export function DataGate({ children }: { children: (data: VehicleSnapshot) => React.ReactNode }) {
  const { resource, activeVehicle, listState, retry } = useVehicles();
  const router = useRouter();
  if (listState === 'loading') return <State title="Loading vehicles" loading />;
  if (listState === 'error') return <State title="Could not load vehicles" retry={retry} />;
  if (!activeVehicle)
    return (
      <Card>
        <Copy style={{ fontWeight: '700' }}>Add your first vehicle</Copy>
        <Copy muted>Start with a vehicle name. You can choose a demo scenario afterwards.</Copy>
        <Button title="Add vehicle" onPress={() => router.push('/(main)/vehicle/add')} />
      </Card>
    );
  if (resource.status === 'loading')
    return (
      <State
        title="Loading readings"
        message="In the Loading demo scenario, this state stays visible until you choose another scenario."
        loading
      />
    );
  if (resource.status === 'error')
    return <State title="Could not load readings" message={resource.message} retry={retry} />;
  return children(resource.data);
}
export function DemoControls() {
  const { activeVehicle, scenario, chooseScenario, clear, reset } = useVehicles();
  return (
    <Card>
      <Copy style={{ fontWeight: '600' }}>Prototype controls</Copy>
      <Copy muted>
        Choose a deterministic demo state. Vehicle edits last only for this session.
      </Copy>
      {activeVehicle && <Chips values={scenarios} selected={scenario} onSelect={chooseScenario} />}
      <Button title="Show empty garage" secondary onPress={clear} />
      <Button title="Reset demo vehicles" secondary onPress={reset} />
    </Card>
  );
}
export function AssessmentUnavailable({ data }: { data: VehicleSnapshot }) {
  return (
    <State
      title={data.assessmentState === 'collecting' ? 'Collecting data' : 'Assessment unavailable'}
      message={
        data.assessmentState === 'collecting'
          ? 'This demo represents an incomplete assessment window.'
          : 'No model assessment is available. Missing assessments are not health scores.'
      }
    />
  );
}
export function Notice({ children }: PropsWithChildren) {
  return (
    <Copy muted style={{ fontSize: 12 }}>
      {children}
    </Copy>
  );
}
