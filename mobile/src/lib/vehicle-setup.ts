// Pure powertrain rules and metadata validation; no registry lookup, storage, or inference.
import type { HybridFuelType, IceFuelType, Powertrain, VehicleFuelType, VehicleSetupDraft, VehicleSetupErrors, VehicleSetupValidation, VehicleSetupValue } from '@/types/vehicle-setup';

export const powertrainOptions = [
  { value: 'ice', label: 'ICE', description: 'Internal combustion engine' },
  { value: 'hybrid', label: 'Hybrid', description: 'Combustion engine and electric motor' },
  { value: 'ev', label: 'Fully Electric (EV)', description: 'Electric motor only' },
] as const;

const iceFuels = [
  { value: 'petrol', label: 'Petrol' },
  { value: 'diesel', label: 'Diesel' },
  { value: 'cng', label: 'CNG' },
] as const;
const hybridFuels = [
  { value: 'petrol-electric', label: 'Petrol + electric' },
  { value: 'diesel-electric', label: 'Diesel + electric' },
] as const;

export function fuelOptionsFor(powertrain: Powertrain | null): readonly { value: VehicleFuelType; label: string }[] {
  return powertrain === 'ice' ? iceFuels : powertrain === 'hybrid' ? hybridFuels : [];
}

export function emptyVehicleSetup(): VehicleSetupDraft {
  return { powertrain: null, manufacturer: '', model: '', year: '', fuelType: null, nickname: '' };
}

export const vehicleTextLimits = { manufacturer: 60, model: 80, nickname: 60 } as const;
// Accept older vehicles and next year's model-year releases; this is a UI policy,
// not a claim that a manufacturer/model/year combination exists in a vehicle registry.
export const minimumVehicleYear = 1886;
export function vehicleYearBounds(currentYear = new Date().getFullYear()) {
  return { min: minimumVehicleYear, max: currentYear + 1 };
}

export function validateVehicleSetup(draft: VehicleSetupDraft, currentYear = new Date().getFullYear()): VehicleSetupValidation {
  const errors: VehicleSetupErrors = {};
  const manufacturer = draft.manufacturer.trim(), model = draft.model.trim(), nickname = draft.nickname.trim();
  if (!draft.powertrain || !powertrainOptions.some(option => option.value === draft.powertrain)) errors.powertrain = 'Choose an engine / vehicle type.';
  if (!manufacturer) errors.manufacturer = 'Enter a manufacturer.';
  else if (manufacturer.length > vehicleTextLimits.manufacturer) errors.manufacturer = `Use ${vehicleTextLimits.manufacturer} characters or fewer.`;
  if (!model) errors.model = 'Enter a model.';
  else if (model.length > vehicleTextLimits.model) errors.model = `Use ${vehicleTextLimits.model} characters or fewer.`;
  if (nickname.length > vehicleTextLimits.nickname) errors.nickname = `Use ${vehicleTextLimits.nickname} characters or fewer.`;
  const yearText = draft.year.trim(), year = Number(yearText), bounds = vehicleYearBounds(currentYear);
  if (!yearText) errors.year = 'Enter a model year.';
  else if (!/^\d{4}$/.test(yearText)) errors.year = 'Enter a four-digit year using numbers only.';
  else if (year < bounds.min || year > bounds.max) errors.year = `Enter a year from ${bounds.min} to ${bounds.max}.`;
  if ((draft.powertrain === 'ice' || draft.powertrain === 'hybrid')
    && !fuelOptionsFor(draft.powertrain).some(option => option.value === draft.fuelType)) {
    errors.fuelType = 'Choose a fuel type for this powertrain.';
  }
  if (Object.keys(errors).length) return { valid: false, errors };

  const base = { manufacturer, model, year, nickname: nickname || null };
  let value: VehicleSetupValue;
  // Fuel membership was checked above; preserve the powertrain/fuel relationship
  // in the submission type instead of accepting arbitrary combinations in storage.
  switch (draft.powertrain) {
    case 'ice': value = { ...base, powertrain: 'ice', fuelType: draft.fuelType as IceFuelType }; break;
    case 'hybrid': value = { ...base, powertrain: 'hybrid', fuelType: draft.fuelType as HybridFuelType }; break;
    case 'ev': value = { ...base, powertrain: 'ev', fuelType: null }; break;
    default: return { valid: false, errors: { powertrain: 'Choose a powertrain.' } };
  }
  return { valid: true, value, errors: {} };
}
