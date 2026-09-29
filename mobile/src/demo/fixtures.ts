// Deterministic design fixtures only; no trained model or live telemetry is used.
import type {
  Insight,
  Reading,
  Scenario,
  SensorKey,
  Vehicle,
  VehicleSnapshot,
} from '@/types/vehicle-health';
export const scenarios: { id: Scenario; label: string }[] = [
  { id: 'voltage', label: 'Voltage deviation' },
  { id: 'normal', label: 'No flagged observations' },
  { id: 'temperature', label: 'Temperature trend' },
  { id: 'vibration', label: 'Vibration trend' },
  { id: 'no-data', label: 'No readings' },
  { id: 'waiting', label: 'Waiting for readings' },
  { id: 'collecting', label: 'Collecting data' },
  { id: 'assessment-unavailable', label: 'Assessment unavailable' },
  { id: 'missing', label: 'Missing sensor values' },
  { id: 'stale', label: 'Stale readings' },
  { id: 'disconnected', label: 'Disconnected' },
  { id: 'failed', label: 'Failed load' },
  { id: 'loading', label: 'Loading' },
];
export const initialVehicles: Vehicle[] = [
  {
    id: 'SIM-001',
    name: 'My Sedan',
    make: '',
    model: '',
    year: '',
    notes: '',
    source: 'simulated',
  },
  {
    id: 'SIM-002',
    name: 'Family SUV',
    make: '',
    model: '',
    year: '',
    notes: '',
    source: 'simulated',
  },
  {
    id: 'SIM-003',
    name: 'City Hatchback',
    make: '',
    model: '',
    year: '',
    notes: '',
    source: 'simulated',
  },
];
export const demoEnd = '2026-09-28T18:00:00.000Z';
const voltages = [
  12.4, 12.5, 12.4, 12.6, 12.5, 12.4, 12.3, 12.2, 12.1, 12.2, 12.1, 12.0, 12.1, 12.0, 12.0, 11.9,
  11.8, 11.7, 11.6, 11.7, 11.9, 12.0, 11.9, 11.8, 11.8,
];
export function makeSnapshot(vehicleId: string, scenario: Scenario): VehicleSnapshot {
  const empty = scenario === 'no-data' || scenario === 'waiting';
  const history: Reading[] = empty
    ? []
    : voltages.map((voltage, index) => ({
        timestamp: new Date(Date.parse(demoEnd) - (24 - index) * 3600000).toISOString(),
        values: {
          battery_voltage: scenario === 'missing' ? null : scenario === 'normal' ? 12.4 : voltage,
          coolant_temp_c: scenario === 'temperature' ? 80 + index / 2 : 92,
          engine_rpm: 820,
          engine_load_pct: 34,
          speed_kmph: 0,
          vibration:
            scenario === 'missing' ? null : scenario === 'vibration' ? 0.2 + index / 100 : 0.2,
        },
      }));
  const latest = history.at(-1) ?? null;
  const sensor: SensorKey =
    scenario === 'temperature'
      ? 'coolant_temp_c'
      : scenario === 'vibration'
        ? 'vibration'
        : 'battery_voltage';
  const flagged = ['voltage', 'temperature', 'vibration', 'stale', 'disconnected'].includes(
    scenario,
  );
  const observed = latest?.values[sensor];
  const insights: Insight[] =
    flagged && observed != null
      ? [
          {
            id: `${vehicleId}-${scenario}`,
            vehicleId,
            sensor,
            observed,
            timestamp: demoEnd,
            source: 'simulated',
            title:
              scenario === 'temperature'
                ? 'Temperature trend'
                : scenario === 'vibration'
                  ? 'Vibration trend increase'
                  : 'Battery voltage deviation',
            explanation:
              sensor === 'battery_voltage'
                ? 'This demo history moves from 12.4 V to 11.8 V. The fixture illustrates a voltage deviation; no validated reference range or diagnosis is available.'
                : 'The demo series rises across the displayed period. This observation describes the fixture, not a diagnosed fault.',
            nextStep:
              sensor === 'battery_voltage'
                ? 'Review charging-system readings with a technician.'
                : 'Review this sensor history with a technician before drawing conclusions.',
          },
        ]
      : [];
  const assessment =
    insights.length && sensor === 'battery_voltage'
      ? {
          score: 86,
          label: 'Illustrative assessment',
          source: 'simulated' as const,
          timestamp: demoEnd,
          explanation:
            '86/100 is an authored UI example associated with the voltage-deviation fixture. It is not calculated by a model and does not establish vehicle condition.',
        }
      : null;
  return {
    vehicleId,
    source: 'simulated',
    connection:
      scenario === 'disconnected'
        ? 'disconnected'
        : scenario === 'waiting'
          ? 'waiting'
          : empty
            ? 'none'
            : 'playback',
    freshness: empty
      ? 'unavailable'
      : scenario === 'stale' || scenario === 'disconnected'
        ? 'stale'
        : 'current',
    assessmentState:
      scenario === 'collecting' ? 'collecting' : assessment ? 'available' : 'unavailable',
    history,
    latest,
    assessment,
    insights,
    report: latest
      ? {
          id: vehicleId,
          vehicleId,
          createdAt: demoEnd,
          start: history[0].timestamp,
          end: latest.timestamp,
          source: 'simulated',
          assessment,
          observations: insights,
        }
      : null,
  };
}
