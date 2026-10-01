// Vehicle overview, sensor list and history use the route's explicit vehicle context.
import { useState } from 'react';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useRouteVehicle } from '@/hooks/use-route-vehicle';
import { Page, State, Chips, Button, Copy } from '@/components/vehicle-health/ui';
import { VehicleCard, Freshness, HealthCard, SensorCards } from '@/components/vehicle-health/cards';
import { DataGate, AssessmentUnavailable } from '@/components/vehicle-health/data-state';
import { SensorChart } from '@/components/vehicle-health/sensor-chart';
export default function VehicleDetail() {
  const { id, tab: initialTab } = useLocalSearchParams<{ id: string; tab?: string }>();
  const router = useRouter();
  const { vehicle, pending } = useRouteVehicle(id);
  const [tab, setTab] = useState(initialTab === 'sensors' ? 'sensors' : 'overview');
  return (
    <Page title="Vehicle details" back={() => router.back()}>
      {pending ? (
        <State title="Loading vehicle" loading />
      ) : !vehicle ? (
        <State
          title="Vehicle not found"
          message="Session-only vehicles disappear when the demo session ends."
        />
      ) : (
        <>
          <VehicleCard vehicle={vehicle} />
          <Button
            secondary
            title="Manage vehicle"
            onPress={() =>
              router.push({ pathname: '/(main)/vehicle/edit/[id]', params: { id: vehicle.id } })
            }
          />
          <Chips
            values={[
              { id: 'overview', label: 'Overview' },
              { id: 'sensors', label: 'Sensors' },
              { id: 'history', label: 'History' },
            ]}
            selected={tab}
            onSelect={setTab}
          />
          <DataGate>
            {(data) => (
              <>
                <Freshness data={data} />
                {tab === 'overview' ? (
                  <>
                    {data.assessment ? (
                      <HealthCard assessment={data.assessment} />
                    ) : (
                      <AssessmentUnavailable data={data} />
                    )}
                    <Copy muted>{data.insights.length} flagged demo observations</Copy>
                    <Button
                      secondary
                      title="View insights"
                      onPress={() => router.push('/(main)/(tabs)/insights')}
                    />
                    <Button
                      title="View report preview"
                      onPress={() =>
                        router.push({ pathname: '/(main)/report/[id]', params: { id: vehicle.id } })
                      }
                    />
                  </>
                ) : tab === 'sensors' ? (
                  <SensorCards
                    data={data}
                    onSelect={(key) =>
                      router.push({
                        pathname: '/(main)/sensor/[key]',
                        params: { key, vehicleId: vehicle.id },
                      })
                    }
                  />
                ) : (
                  <>
                    <Copy>Battery voltage · available demo history</Copy>
                    <SensorChart history={data.history} sensor="battery_voltage" unit="V" />
                    <Button
                      secondary
                      title="Explore battery history"
                      onPress={() =>
                        router.push({
                          pathname: '/(main)/sensor/[key]',
                          params: { key: 'battery_voltage', vehicleId: vehicle.id },
                        })
                      }
                    />
                  </>
                )}
              </>
            )}
          </DataGate>
        </>
      )}
    </Page>
  );
}
