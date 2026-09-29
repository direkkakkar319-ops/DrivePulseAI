// Verify provider isolation, deterministic evidence, missing values, and history consistency.
import { createDemoProvider } from '../src/demo/provider';
import { makeSnapshot, scenarios } from '../src/demo/fixtures';
import { historyStats, historyWindow } from '../src/lib/history';
const draft = { name: 'Test car', make: 'Toyota', model: 'Corolla', year: '2022', notes: '' };
it('isolates demo sessions and starts new vehicles without inferred telemetry', async () => {
  const a = createDemoProvider(),
    b = createDemoProvider();
  const vehicle = await a.saveVehicle(draft);
  expect(await a.listVehicles()).toHaveLength(4);
  expect(await b.listVehicles()).toHaveLength(3);
  expect((await a.getSnapshot(vehicle.id)).latest).toBeNull();
  await a.saveVehicle({ ...draft, make: 'Different', name: 'Renamed' }, vehicle.id);
  expect((await a.getSnapshot(vehicle.id)).latest).toBeNull();
});
it('does not mutate provider records through returned list values', async () => {
  const provider = createDemoProvider();
  const list = await provider.listVehicles();
  list[0].name = 'Mutated';
  expect((await provider.listVehicles())[0].name).toBe('My Sedan');
});
it('validates prototype metadata and rejects unknown vehicles', async () => {
  const p = createDemoProvider();
  await expect(p.saveVehicle({ ...draft, name: ' ' })).rejects.toThrow('vehicle name');
  await expect(p.saveVehicle({ ...draft, year: 'abcd' })).rejects.toThrow('four-digit');
  await expect(p.saveVehicle(draft, 'unknown')).rejects.toThrow('not found');
  await expect(p.getSnapshot('unknown')).rejects.toThrow('not found');
});
it.each(scenarios.filter((s) => !['failed', 'loading'].includes(s.id)))(
  'keeps $id fixtures deterministic and report evidence consistent',
  ({ id }) => {
    const data = makeSnapshot('SIM-001', id);
    expect(data).toEqual(makeSnapshot('SIM-001', id));
    expect(data.source).toBe('simulated');
    expect(data.latest).toEqual(data.history.at(-1) ?? null);
    for (const insight of data.insights) {
      expect(insight.observed).toBe(data.latest?.values[insight.sensor]);
      expect(insight.source).toBe('simulated');
    }
    if (data.report) {
      expect(data.report.observations).toEqual(data.insights);
      expect(data.report.assessment).toEqual(data.assessment);
      expect(data.report.start).toBe(data.history[0].timestamp);
      expect(data.report.end).toBe(data.latest?.timestamp);
    }
  },
);
it('computes statistics from the exact selected samples and preserves missing current values', () => {
  const data = makeSnapshot('SIM-001', 'voltage');
  const window = historyWindow(data.history, 6);
  const values = window.map((p) => p.values.battery_voltage!);
  const stats = historyStats(window, 'battery_voltage');
  expect(window).toHaveLength(7);
  expect(stats.average).toBe(values.reduce((a, b) => a + b) / values.length);
  expect(stats.min).toBe(Math.min(...values));
  expect(stats.max).toBe(Math.max(...values));
  expect(stats.current).toBe(values.at(-1));
  const missing = window.map((p, i) => ({
    ...p,
    values: {
      ...p.values,
      battery_voltage: i === window.length - 1 ? null : p.values.battery_voltage,
    },
  }));
  expect(historyStats(missing, 'battery_voltage').current).toBeNull();
  expect(historyStats([], 'battery_voltage')).toEqual({
    current: null,
    min: null,
    max: null,
    average: null,
  });
});
it('keeps absent readings and assessments null while retaining a real zero speed', () => {
  expect(makeSnapshot('SIM-001', 'no-data').latest).toBeNull();
  expect(makeSnapshot('SIM-001', 'no-data').assessment).toBeNull();
  expect(makeSnapshot('SIM-001', 'missing').latest?.values.battery_voltage).toBeNull();
  expect(makeSnapshot('SIM-001', 'voltage').latest?.values.speed_kmph).toBe(0);
});
it('represents stale and disconnected separately from demo provenance', () => {
  expect(makeSnapshot('SIM-001', 'stale')).toMatchObject({
    source: 'simulated',
    freshness: 'stale',
    connection: 'playback',
  });
  expect(makeSnapshot('SIM-001', 'disconnected')).toMatchObject({
    source: 'simulated',
    freshness: 'stale',
    connection: 'disconnected',
  });
});
it('supports deterministic failure recovery and an empty garage', async () => {
  const p = createDemoProvider();
  p.setScenario('SIM-001', 'failed');
  await expect(p.getSnapshot('SIM-001')).rejects.toThrow('Demo request failed');
  p.setScenario('SIM-001', 'voltage');
  expect((await p.getSnapshot('SIM-001')).assessment).not.toBeNull();
  p.clear();
  expect(await p.listVehicles()).toEqual([]);
  p.reset();
  expect(await p.listVehicles()).toHaveLength(3);
});
