// Home consumes the provider view model and never manufactures readings or assessments.
import { useRouter } from 'expo-router';
import { View } from 'react-native';
import { useAuthStore } from '@/store/authStore';
import { useVehicles } from '@/store/vehicleDataStore';
import { Brand, Copy, Page, Section, State, Button } from '@/components/vehicle-health/ui';
import {
  VehicleCard,
  Freshness,
  HealthCard,
  InsightCard,
  SensorCards,
} from '@/components/vehicle-health/cards';
import {
  AssessmentUnavailable,
  DataGate,
  VehicleSelector,
} from '@/components/vehicle-health/data-state';
import { SensorChart } from '@/components/vehicle-health/sensor-chart';
export default function Home() {
  const router = useRouter();
  const { user } = useAuthStore();
  const { activeVehicle } = useVehicles();
  return (
    <Page>
      <Brand />
      <View>
        <Copy muted>YOUR VEHICLE, AT A GLANCE</Copy>
        <Copy style={{ fontSize: 27, lineHeight: 34, fontWeight: '600' }}>
          Hello, {user?.displayName || 'Driver'}
        </Copy>
      </View>
      <VehicleSelector />
      <DataGate>
        {(data) => (
          <>
            {activeVehicle && (
              <VehicleCard
                vehicle={activeVehicle}
                onPress={() =>
                  router.push({
                    pathname: '/(main)/vehicle/[id]',
                    params: { id: activeVehicle.id },
                  })
                }
              />
            )}
            <Freshness data={data} />
            {data.assessment ? (
              <HealthCard assessment={data.assessment} />
            ) : (
              <AssessmentUnavailable data={data} />
            )}
            {data.insights[0] ? (
              <InsightCard
                insight={data.insights[0]}
                onPress={() =>
                  router.push({
                    pathname: '/(main)/insight/[id]',
                    params: { id: data.insights[0].id, vehicleId: data.vehicleId },
                  })
                }
              />
            ) : (
              <State
                title={data.latest ? 'No flagged demo observations' : 'No readings yet'}
                message={
                  data.latest
                    ? 'This is not confirmation of vehicle health.'
                    : 'Choose a demo scenario from Account → Prototype controls.'
                }
              />
            )}
            <Section
              title="Sensor readings"
              action="See all"
              onPress={() =>
                router.push({
                  pathname: '/(main)/vehicle/[id]',
                  params: { id: data.vehicleId, tab: 'sensors' },
                })
              }
            />
            <SensorCards
              preview
              data={data}
              onSelect={(sensor) =>
                router.push({
                  pathname: '/(main)/sensor/[key]',
                  params: { key: sensor, vehicleId: data.vehicleId },
                })
              }
            />
            <Section title="Battery history" />
            <SensorChart history={data.history} sensor="battery_voltage" unit="V" />
            <Section title="Latest report" />
            {data.report ? (
              <Button
                secondary
                title="View report preview"
                onPress={() =>
                  router.push({ pathname: '/(main)/report/[id]', params: { id: data.vehicleId } })
                }
              />
            ) : (
              <State title="Report preview unavailable" />
            )}
          </>
        )}
      </DataGate>
    </Page>
  );
}
