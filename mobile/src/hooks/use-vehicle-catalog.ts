// Lazy public catalog loading; old manufacturer responses can never replace the current model list.
import { useEffect, useRef, useState } from 'react';
import { vehicleCatalog, type CatalogMake, type VehicleCatalog } from '@/api/vehicle-catalog';

interface Options<T> { items: readonly T[]; loading: boolean; error?: string }
export function useVehicleCatalog(manufacturer: string, catalog: VehicleCatalog = vehicleCatalog) {
  const [makes, setMakes] = useState<Options<CatalogMake>>({ items: [], loading: false });
  const [models, setModels] = useState<Options<string> & { manufacturer: string }>({ items: [], loading: false, manufacturer: '' });
  const current = useRef(manufacturer);
  const mounted = useRef(true), makeTicket = useRef(0), modelTicket = useRef(0);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => { current.current = manufacturer; modelTicket.current++; }, [manufacturer]);
  async function loadMakes() {
    const ticket = ++makeTicket.current;
    setMakes(previous => ({ ...previous, loading: true, error: undefined }));
    try { const items = await catalog.makes(); if (mounted.current && ticket === makeTicket.current) setMakes({ items, loading: false }); }
    catch (error) { if (mounted.current && ticket === makeTicket.current) setMakes({ items: [], loading: false, error: error instanceof Error ? error.message : 'Catalog unavailable. Use manual entry.' }); }
  }
  async function loadModels() {
    const key = manufacturer, ticket = ++modelTicket.current;
    setModels({ manufacturer: key, items: [], loading: true });
    try {
      const allMakes = await catalog.makes();
      const make = allMakes.find(item => item.name.toLocaleLowerCase() === key.trim().toLocaleLowerCase());
      const items = make ? await catalog.models(make) : [];
      if (mounted.current && ticket === modelTicket.current && current.current === key) setModels({ manufacturer: key, items, loading: false });
    } catch (error) {
      if (mounted.current && ticket === modelTicket.current && current.current === key) setModels({ manufacturer: key, items: [], loading: false,
        error: error instanceof Error ? error.message : 'Catalog unavailable. Use manual entry.' });
    }
  }
  const visibleModels: Options<string> = models.manufacturer === manufacturer ? models : { items: [], loading: false };
  return { makes, models: visibleModels, loadMakes, loadModels };
}
