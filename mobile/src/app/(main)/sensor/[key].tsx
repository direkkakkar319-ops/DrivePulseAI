// Sensor history uses selected sample windows; no invented reference ranges.
import { useState } from 'react';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { sensors } from '@/types/sensors';
import { historyWindow } from '@/lib/history';
import { useRouteVehicle } from '@/hooks/use-route-vehicle';
import { Page, State, Copy, Chips, Card } from '@/components/vehicle-health/ui';
import { DataGate } from '@/components/vehicle-health/data-state';
import { Freshness, SourceBadge } from '@/components/vehicle-health/cards';
import { SensorChart } from '@/components/vehicle-health/sensor-chart';
export default function SensorHistory() {
  const { key, vehicleId } = useLocalSearchParams<{ key: string; vehicleId: string }>();
  const router = useRouter();
  const { vehicle, pending } = useRouteVehicle(vehicleId);
  const [period, setPeriod] = useState('24');
  const sensor = sensors.find((s) => s.key === key);
  return (
    <Page title={sensor?.label ?? 'Sensor history'} back={() => router.back()}>
      {pending ? (
        <State title="Loading vehicle" loading />
      ) : !vehicle || !sensor ? (
        <State title="History not found" />
      ) : (
        <>
          <Copy>
            {vehicle.name} · {vehicle.id}
          </Copy>
          <DataGate>
            {(data) => (
              <>
                <SourceBadge source={data.source} />
                <Freshness data={data} />
                <Chips
                  values={[
                    { id: '6', label: '6 hours' },
                    { id: '12', label: '12 hours' },
                    { id: '24', label: '24 hours' },
                  ]}
                  selected={period}
                  onSelect={setPeriod}
                />
                <Card>
                  <SensorChart
                    history={historyWindow(data.history, Number(period))}
                    sensor={sensor.key}
                    unit={sensor.unit}
                  />
                </Card>
                <Copy muted>
                  Only the available demo samples are shown. Summary values are calculated from this
                  selected window. Missing samples remain unavailable.
                </Copy>
                <Copy muted>
                  {sensor.unit === null
                    ? 'Vibration unit and reference range are not established.'
                    : 'No validated reference range is available.'}
                </Copy>
              </>
            )}
          </DataGate>
        </>
      )}
    </Page>
  );
}
