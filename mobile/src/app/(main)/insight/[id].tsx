// Evidence-first demo insight detail, without component diagnoses or risk claims.
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useRouteVehicle } from '@/hooks/use-route-vehicle';
import { sensors } from '@/types/sensors';
import { Page, State, Card, Copy, Section, Button, Badge } from '@/components/vehicle-health/ui';
import { DataGate } from '@/components/vehicle-health/data-state';
import { Freshness, SourceBadge } from '@/components/vehicle-health/cards';
import { SensorChart, formatValue } from '@/components/vehicle-health/sensor-chart';
export default function InsightDetail() {
  const { id, vehicleId } = useLocalSearchParams<{ id: string; vehicleId: string }>();
  const { vehicle, pending } = useRouteVehicle(vehicleId);
  const router = useRouter();
  return (
    <Page title="Observation detail" back={() => router.back()}>
      {pending ? (
        <State title="Loading vehicle" loading />
      ) : !vehicle ? (
        <State title="Vehicle not found" />
      ) : (
        <>
          <Copy>
            {vehicle.name} · {vehicle.id}
          </Copy>
          <DataGate>
            {(data) => {
              const insight = data.insights.find((i) => i.id === id);
              if (!insight)
                return (
                  <State
                    title="Observation unavailable"
                    message="The selected demo scenario may have changed."
                  />
                );
              const sensor = sensors.find((s) => s.key === insight.sensor)!;
              return (
                <>
                  <SourceBadge source={insight.source} />
                  <Freshness data={data} />
                  <Badge label="DEMO OBSERVATION" warning />
                  <Copy style={{ fontSize: 25, lineHeight: 32, fontWeight: '600' }}>
                    {insight.title}
                  </Copy>
                  <Section title="What was observed" />
                  <Copy muted>{insight.explanation}</Copy>
                  <Card>
                    <Copy muted>
                      Observed value · {new Date(insight.timestamp).toLocaleString()}
                    </Copy>
                    <Copy style={{ fontSize: 26, lineHeight: 34 }}>
                      {formatValue(insight.observed, sensor.unit)}
                    </Copy>
                  </Card>
                  <Section title="Supporting evidence" />
                  <SensorChart history={data.history} sensor={insight.sensor} unit={sensor.unit} />
                  <Section title="Suggested next step" />
                  <Copy>{insight.nextStep}</Copy>
                  <State
                    title="Model explanation unavailable"
                    message="No inference or confirmed mechanical root cause is available for this prototype."
                  />
                  <Button
                    secondary
                    title="Explore sensor history"
                    onPress={() =>
                      router.push({
                        pathname: '/(main)/sensor/[key]',
                        params: { key: insight.sensor, vehicleId },
                      })
                    }
                  />
                  <Button
                    title="View report preview"
                    onPress={() =>
                      router.push({ pathname: '/(main)/report/[id]', params: { id: vehicleId } })
                    }
                  />
                </>
              );
            }}
          </DataGate>
        </>
      )}
    </Page>
  );
}
