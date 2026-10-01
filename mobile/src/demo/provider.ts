// Session-only provider; scenario controls never infer telemetry from metadata.
import type { VehicleDataProvider } from '@/api/vehicle-data-provider';
import type { Scenario, Vehicle, VehicleDraft } from '@/types/vehicle-health';
import { initialVehicles, makeSnapshot } from './fixtures';
export function createDemoProvider(): VehicleDataProvider & {
  setScenario(id: string, scenario: Scenario): void;
  getScenario(id: string): Scenario;
  clear(): void;
  reset(): void;
} {
  let vehicles = initialVehicles.map((v) => ({ ...v }));
  let nextId = 4;
  const scenarios = new Map<string, Scenario>();
  const getScenario = (id: string): Scenario =>
    scenarios.get(id) ?? (id === 'SIM-001' ? 'voltage' : 'normal');
  return {
    async listVehicles() {
      return vehicles.map((v) => ({ ...v }));
    },
    async saveVehicle(draft: VehicleDraft, id?: string) {
      if (!draft.name.trim()) throw new Error('Enter a vehicle name.');
      if (draft.year && !/^\d{4}$/.test(draft.year))
        throw new Error('Enter a four-digit model year or leave it blank.');
      if (id && !vehicles.some((v) => v.id === id)) throw new Error('Vehicle not found.');
      const vehicle: Vehicle = {
        ...draft,
        name: draft.name.trim(),
        id: id ?? `SIM-${String(nextId++).padStart(3, '0')}`,
        source: 'simulated',
      };
      vehicles = id ? vehicles.map((v) => (v.id === id ? vehicle : v)) : [...vehicles, vehicle];
      if (!id) scenarios.set(vehicle.id, 'no-data');
      return { ...vehicle };
    },
    async getSnapshot(id) {
      if (!vehicles.some((v) => v.id === id)) throw new Error('Vehicle not found.');
      const scenario = getScenario(id);
      if (scenario === 'failed')
        throw new Error('Demo request failed. Choose another scenario to restore data.');
      return makeSnapshot(id, scenario);
    },
    getScenario,
    setScenario(id, scenario) {
      scenarios.set(id, scenario);
    },
    clear() {
      vehicles = [];
      scenarios.clear();
    },
    reset() {
      vehicles = initialVehicles.map((v) => ({ ...v }));
      scenarios.clear();
      nextId = 4;
    },
  };
}
