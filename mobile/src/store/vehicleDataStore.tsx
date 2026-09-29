// Signed-in data context keeps demo controls separate from the provider contract.
import { createContext, useContext, useEffect, useState, type PropsWithChildren } from 'react';
import { createDemoProvider } from '@/demo/provider';
import type {
  Resource,
  Scenario,
  Vehicle,
  VehicleDraft,
  VehicleSnapshot,
} from '@/types/vehicle-health';
function useVehicleData() {
  const [provider] = useState(createDemoProvider);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [resource, setResource] = useState<Resource<VehicleSnapshot>>({ status: 'loading' });
  const [listState, setListState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [revision, setRevision] = useState(0);
  const [scenario, setScenarioState] = useState<Scenario>('voltage');
  useEffect(() => {
    let current = true;
    void provider
      .listVehicles()
      .then((list) => {
        if (current) {
          setVehicles(list);
          setListState('ready');
          setActiveId((id) => (list.some((v) => v.id === id) ? id : (list[0]?.id ?? null)));
        }
      })
      .catch(() => {
        if (current) setListState('error');
      });
    return () => {
      current = false;
    };
  }, [provider, revision]);
  useEffect(() => {
    let current = true;
    void Promise.resolve().then(async () => {
      if (!current) return;
      setResource({ status: 'loading' });
      if (!activeId) return;
      const selected = provider.getScenario(activeId);
      setScenarioState(selected);
      if (selected === 'loading') return;
      try {
        const data = await provider.getSnapshot(activeId);
        if (current) setResource({ status: 'ready', data });
      } catch (error) {
        if (current)
          setResource({
            status: 'error',
            message: error instanceof Error ? error.message : 'Could not load vehicle data.',
          });
      }
    });
    return () => {
      current = false;
    };
  }, [activeId, provider, revision]);
  function chooseScenario(next: Scenario) {
    if (!activeId) return;
    provider.setScenario(activeId, next);
    setScenarioState(next);
    setRevision((v) => v + 1);
  }
  async function saveVehicle(draft: VehicleDraft, id?: string) {
    const vehicle = await provider.saveVehicle(draft, id);
    setVehicles(await provider.listVehicles());
    setActiveId(vehicle.id);
    setRevision((v) => v + 1);
    return vehicle;
  }
  return {
    vehicles,
    activeId,
    activeVehicle: vehicles.find((v) => v.id === activeId) ?? null,
    listState,
    resource:
      resource.status === 'ready' && resource.data.vehicleId !== activeId
        ? { status: 'loading' as const }
        : resource,
    selectVehicle: setActiveId,
    saveVehicle,
    scenario,
    chooseScenario,
    retry: () => setRevision((v) => v + 1),
    clear: () => {
      provider.clear();
      setActiveId(null);
      setRevision((v) => v + 1);
    },
    reset: () => {
      provider.reset();
      setRevision((v) => v + 1);
    },
  };
}
const Context = createContext<ReturnType<typeof useVehicleData> | null>(null);
export function VehicleDataProvider({ children }: PropsWithChildren) {
  const value = useVehicleData();
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export function useVehicles() {
  const value = useContext(Context);
  if (!value) throw new Error('VehicleDataProvider required');
  return value;
}
