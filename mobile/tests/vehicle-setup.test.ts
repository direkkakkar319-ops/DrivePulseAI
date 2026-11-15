// Validate user-entered metadata independently of UI, existing Garage fixtures, and telemetry.
import { emptyVehicleSetup, validateVehicleSetup } from '../src/lib/vehicle-setup';
import type { VehicleSetupDraft } from '../src/types/vehicle-setup';

const valid: VehicleSetupDraft = {
  powertrain: 'ice', manufacturer: 'Independent Motors', model: 'Roadster', year: '2025', fuelType: 'petrol', nickname: '',
};

it('reports each required field without requiring a nickname', () => {
  expect(validateVehicleSetup(emptyVehicleSetup(), 2026)).toEqual({ valid: false, errors: {
    powertrain: 'Choose an engine / vehicle type.', manufacturer: 'Enter a manufacturer.', model: 'Enter a model.', year: 'Enter a model year.',
  } });
});

it.each(['manufacturer', 'model'] as const)('rejects whitespace-only %s', field => {
  const result = validateVehicleSetup({ ...valid, [field]: '   ' }, 2026);
  expect(result.valid).toBe(false);
  expect(result.errors[field]).toBeTruthy();
});

it.each(['', '202', '20255', '20ab', '2e03', '20.5', '-202', '+202', '２０２５'])('rejects invalid year %s', year => {
  const result = validateVehicleSetup({ ...valid, year }, 2026);
  expect(result.valid).toBe(false);
  expect(result.errors.year).toBeTruthy();
});

it.each(['1885', '2028', '0000'])('rejects year %s outside the model-year bounds', year => {
  expect(validateVehicleSetup({ ...valid, year }, 2026)).toMatchObject({ valid: false, errors: { year: 'Enter a year from 1886 to 2027.' } });
});

it.each(['1886', '2026', '2027'])('accepts supported year %s including boundaries', year => {
  const result = validateVehicleSetup({ ...valid, year }, 2026);
  expect(result).toMatchObject({ valid: true, value: { year: Number(year) } });
});

it('moves the maximum allowed model year with the current year', () => {
  expect(validateVehicleSetup({ ...valid, year: '2028' }, 2027).valid).toBe(true);
  expect(validateVehicleSetup({ ...valid, year: '2029' }, 2027).valid).toBe(false);
});

it.each(['petrol', 'diesel', 'cng'] as const)('accepts ICE fuel %s', fuelType => {
  expect(validateVehicleSetup({ ...valid, fuelType }, 2026)).toMatchObject({ valid: true, value: { powertrain: 'ice', fuelType } });
});

it.each(['petrol-electric', 'diesel-electric'] as const)('accepts hybrid fuel %s', fuelType => {
  expect(validateVehicleSetup({ ...valid, powertrain: 'hybrid', fuelType }, 2026)).toMatchObject({ valid: true, value: { powertrain: 'hybrid', fuelType } });
});

it.each([
  { powertrain: 'ice', fuelType: null }, { powertrain: 'ice', fuelType: 'petrol-electric' },
  { powertrain: 'hybrid', fuelType: null }, { powertrain: 'hybrid', fuelType: 'diesel' },
] as const)('rejects missing or incompatible fuel %o', combination => {
  expect(validateVehicleSetup({ ...valid, ...combination }, 2026)).toMatchObject({ valid: false, errors: { fuelType: 'Choose a fuel type for this powertrain.' } });
});

it('normalizes EV fuel to null even if an imported draft carries stale fuel', () => {
  expect(validateVehicleSetup({ ...valid, powertrain: 'ev' }, 2026)).toMatchObject({ valid: true, value: { powertrain: 'ev', fuelType: null } });
});

it('trims free text, preserves unrestricted manufacturer names, and omits blank nicknames', () => {
  const result = validateVehicleSetup({ ...valid, manufacturer: '  Véhicules 新品牌  ', model: '  Model / One  ', year: ' 2025 ', nickname: '  ' }, 2026);
  expect(result).toEqual({ valid: true, errors: {}, value: { manufacturer: 'Véhicules 新品牌', model: 'Model / One', year: 2025,
    powertrain: 'ice', fuelType: 'petrol', nickname: null } });
});

it('preserves an optional nickname when provided', () => {
  expect(validateVehicleSetup({ ...valid, nickname: ' My Car ' }, 2026)).toMatchObject({ valid: true, value: { nickname: 'My Car' } });
});

it.each([
  ['manufacturer', 61], ['model', 81], ['nickname', 61],
] as const)('validates the %s length even outside native input limits', (field, length) => {
  const result = validateVehicleSetup({ ...valid, [field]: 'x'.repeat(length) }, 2026);
  expect(result.valid).toBe(false);
  expect(result.errors[field]).toBeTruthy();
});
