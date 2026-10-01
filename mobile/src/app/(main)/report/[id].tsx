// Report preview reuses the same assessment, observations and period as demo telemetry.
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useRouteVehicle } from '@/hooks/use-route-vehicle';
import { Page, Copy, State, Section, Card, Badge } from '@/components/vehicle-health/ui';
import { DataGate, AssessmentUnavailable } from '@/components/vehicle-health/data-state';
import { Freshness, VehicleCard, HealthCard, InsightCard } from '@/components/vehicle-health/cards';
export default function Report() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { vehicle, pending } = useRouteVehicle(id);
  const router = useRouter();
  return (
    <Page title="Maintenance report" back={() => router.back()}>
      {pending ? (
        <State title="Loading vehicle" loading />
      ) : !vehicle ? (
        <State title="Vehicle not found" />
      ) : (
        <>
          <VehicleCard vehicle={vehicle} compact />
          <Badge label="REPORT PREVIEW" />
          <Copy muted>Demo content · no production report has been generated.</Copy>
          <DataGate>
            {(data) =>
              !data.report ? (
                <State
                  title="Report preview unavailable"
                  message="This vehicle has no readings to summarize."
                />
              ) : (
                <>
                  <Freshness data={data} />
                  <Card>
                    <Copy>Preview date: {new Date(data.report.createdAt).toLocaleString()}</Copy>
                    <Copy muted>
                      Data source:{' '}
                      {data.report.source === 'simulated' ? 'Demo / simulated' : data.report.source}
                    </Copy>
                    <Copy muted>
                      Telemetry period: {new Date(data.report.start).toLocaleString()} –{' '}
                      {new Date(data.report.end).toLocaleString()}
                    </Copy>
                  </Card>
                  <Section title="Health summary" />
                  {data.report.assessment ? (
                    <HealthCard assessment={data.report.assessment} />
                  ) : (
                    <AssessmentUnavailable data={data} />
                  )}
                  <Section title="Flagged observations" />
                  {data.report.observations.length ? (
                    data.report.observations.map((insight) => (
                      <Card key={insight.id}>
                        <InsightCard
                          insight={insight}
                          onPress={() =>
                            router.push({
                              pathname: '/(main)/insight/[id]',
                              params: { id: insight.id, vehicleId: id },
                            })
                          }
                        />
                        <Copy muted>{insight.explanation}</Copy>
                        <Copy>{insight.nextStep}</Copy>
                      </Card>
                    ))
                  ) : (
                    <State
                      title="No flagged demo observations"
                      message="This does not establish that the vehicle is healthy."
                    />
                  )}
                  <State
                    title="Prediction details unavailable"
                    message="Failure probability, confidence, remaining useful life, and model contributions are not provided."
                  />
                </>
              )
            }
          </DataGate>
        </>
      )}
    </Page>
  );
}
