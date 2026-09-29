// Shared history selectors preserve missing values and calculate chart summaries.
import type { Reading, SensorKey } from '@/types/vehicle-health';
export function historyStats(history: Reading[], sensor: SensorKey) {
  const values = history
    .map((p) => p.values[sensor])
    .filter((v): v is number => v !== null && Number.isFinite(v));
  return {
    current: history.at(-1)?.values[sensor] ?? null,
    min: values.length ? Math.min(...values) : null,
    max: values.length ? Math.max(...values) : null,
    average: values.length ? values.reduce((a, b) => a + b, 0) / values.length : null,
  };
}
export function historyWindow(history: Reading[], hours: number) {
  const end = history.at(-1)?.timestamp;
  return end
    ? history.filter((p) => Date.parse(p.timestamp) >= Date.parse(end) - hours * 3600000)
    : [];
}
