// Reusable vehicle form state and submission boundary; no Garage or backend writes.
import { useEffect, useRef, useState } from 'react';
import { emptyVehicleSetup, fuelOptionsFor, validateVehicleSetup } from '@/lib/vehicle-setup';
import type { Powertrain, VehicleFuelType, VehicleSetupDraft, VehicleSetupValue } from '@/types/vehicle-setup';

export function useVehicleSetup(onSubmit: (value: VehicleSetupValue) => void | Promise<void>, initialValues?: VehicleSetupDraft) {
  const [draft, setDraft] = useState<VehicleSetupDraft>(() => ({ ...(initialValues ?? emptyVehicleSetup()) }));
  const [attempted, setAttempted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const busy = useRef(false), mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const validation = validateVehicleSetup(draft);

  function setField(field: 'manufacturer' | 'model' | 'year' | 'nickname', value: string) {
    if (busy.current) return;
    setDraft(current => ({ ...current, [field]: value }));
    setSubmitError('');
  }
  function selectPowertrain(powertrain: Powertrain) {
    if (busy.current) return;
    setDraft(current => ({ ...current, powertrain, fuelType: current.powertrain === powertrain ? current.fuelType : null }));
    setSubmitError('');
  }
  function selectFuel(fuelType: VehicleFuelType) {
    if (busy.current || !fuelOptionsFor(draft.powertrain).some(option => option.value === fuelType)) return;
    setDraft(current => ({ ...current, fuelType }));
    setSubmitError('');
  }
  async function submit() {
    if (busy.current) return;
    setAttempted(true);
    if (!validation.valid) return;
    busy.current = true;
    setSubmitting(true);
    setSubmitError('');
    try { await onSubmit(validation.value); }
    catch { if (mounted.current) setSubmitError('Could not continue. Please try again.'); }
    finally { busy.current = false; if (mounted.current) setSubmitting(false); }
  }
  return { draft, errors: attempted ? validation.errors : {}, submitting, submitError, setField, selectPowertrain, selectFuel, submit };
}
