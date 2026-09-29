// Insights are scoped to the selected vehicle and reuse fixture evidence.
import { useRouter } from 'expo-router';
import { Page, Copy, State } from '@/components/vehicle-health/ui';
import { DataGate, VehicleSelector } from '@/components/vehicle-health/data-state';
import { Freshness, InsightCard, SourceBadge } from '@/components/vehicle-health/cards';
export default function Insights() {
  const router = useRouter();
  return (
    <Page title="Insights">
      <VehicleSelector />
      <Copy muted>Observations for the selected vehicle</Copy>
      <DataGate>
        {(data) => (
          <>
            <SourceBadge source={data.source} />
            <Freshness data={data} />
            {data.insights.length ? (
              data.insights.map((insight) => (
                <InsightCard
                  key={insight.id}
                  insight={insight}
                  onPress={() =>
                    router.push({
                      pathname: '/(main)/insight/[id]',
                      params: { id: insight.id, vehicleId: data.vehicleId },
                    })
                  }
                />
              ))
            ) : (
              <State
                title={data.latest ? 'No flagged demo observations' : 'Insights unavailable'}
                message="No mechanical diagnosis has been generated."
              />
            )}
          </>
        )}
      </DataGate>
    </Page>
  );
}
