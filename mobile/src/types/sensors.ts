// Display metadata for established telemetry fields; vibration has no assigned unit.
import type { SensorKey } from './vehicle-health';
export const sensors: { key: SensorKey; label: string; unit: string | null; symbol: string }[] = [
  { key: 'battery_voltage', label: 'Battery voltage', unit: 'V', symbol: 'battery' },
  { key: 'coolant_temp_c', label: 'Coolant temperature', unit: '°C', symbol: 'temperature' },
  { key: 'engine_rpm', label: 'Engine RPM', unit: 'rpm', symbol: 'pulse' },
  { key: 'engine_load_pct', label: 'Engine load', unit: '%', symbol: 'gauge' },
  { key: 'speed_kmph', label: 'Vehicle speed', unit: 'km/h', symbol: 'gauge' },
  { key: 'vibration', label: 'Vibration', unit: null, symbol: 'pulse' },
];
