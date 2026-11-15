// Pure catalog bounds and validation; existing records are exempt from new demo coverage restrictions.
import { demoVehicleCatalog, demoModel, validateDemoVehicle } from '../src/config/demo-vehicle-catalog';
import type { VehicleSetupDraft } from '../src/types/vehicle-setup';

it('records source-backed fixed historical ranges, without guessing current or future production', () => {
  expect(demoVehicleCatalog.map(make => make.name)).toEqual(['Mahindra', 'Hyundai', 'Ferrari']);
  for (const make of demoVehicleCatalog) for (const model of make.models) {
    expect(model.sources.length).toBeGreaterThan(0);
    expect(model.years).toEqual([...model.years].sort((a, b) => b - a));
    expect(Math.max(...model.years)).toBe(2024);
  }
  expect(demoModel('Mahindra', 'XUV700')?.years).toEqual([2024, 2023, 2022, 2021]);
  expect(demoModel('Ferrari', '296 GTB')?.years).toEqual([2024, 2023, 2022]);
});

const draft: VehicleSetupDraft = { manufacturer: 'Mahindra', model: 'Thar', year: '2019', powertrain: 'hybrid', fuelType: 'diesel-electric', nickname: '' };
it('validates dependent years and verified configurations even outside dropdown interactions', () => {
  expect(validateDemoVehicle(draft)).toMatchObject({ year: expect.any(String), powertrain: expect.any(String) });
  expect(validateDemoVehicle({ ...draft, powertrain: 'ice', fuelType: 'cng', year: '2024' })).toMatchObject({ fuelType: expect.any(String) });
});
it('preserves original saved metadata and does not treat manual metadata as catalog verified', () => {
  expect(validateDemoVehicle(draft, draft)).toEqual({});
  expect(validateDemoVehicle(draft, undefined, true)).toEqual({});
  expect(validateDemoVehicle({ ...draft, manufacturer: 'Unlisted' })).toEqual({});
});
