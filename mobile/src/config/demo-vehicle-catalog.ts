// Curated historical demo coverage with primary sources; these are not complete worldwide model-year ranges.
import type { Powertrain, VehicleFuelType, VehicleSetupDraft, VehicleSetupErrors } from '@/types/vehicle-setup';

export interface DemoConfiguration { powertrain: Powertrain; fuels: readonly (VehicleFuelType | null)[] }
export interface DemoVehicleModel {
  name: string;
  years: readonly number[];
  coverage: string;
  sources: readonly string[];
  configurations?: readonly DemoConfiguration[];
}
export interface DemoManufacturer { name: string; models: readonly DemoVehicleModel[] }
const years = (first: number, last: number) => Array.from({ length: last - first + 1 }, (_, index) => last - index);
const hyundaiManuals = 'https://org2.hyundai.com/in/en/connect-to-service/hyundai-service/owners-manual';
const ferrari2024 = 'https://www.sec.gov/Archives/edgar/data/1648416/000164841625000027/race-20241231.htm';

// Fixed historical subsets stop at 2024 intentionally. Do not extend them with the
// current year: launch dates are not guarantees of future production/model years.
export const demoVehicleCatalog: readonly DemoManufacturer[] = [
  { name: 'Mahindra', models: [
    { name: 'Thar', years: years(2020, 2024), coverage: '2020-generation Thar · demo years 2020–2024', sources: [
      'https://www.mahindra.com/news-room/press-release/en/mahindra-commemorates-its-75-th-anniversary-launches-the-all-new-thar-at-attractive-prices',
      'https://www.mahindra.com/sites/default/files/2024-06/MM-Annual-Report-2023-24.pdf',
    ], configurations: [{ powertrain: 'ice', fuels: ['petrol', 'diesel'] }] },
    { name: 'XUV700', years: years(2021, 2024), coverage: 'Demo years 2021–2024', sources: [
      'https://www.mahindra.com/sites/default/files/resources/investor-reports/FY22/Announcements/XUV700-Launch-14-08-2021.pdf',
      'https://auto.mahindra.com/on/demandware.static/-/Sites-amc-Library/default/dw535a8403/X700/Press-release/pdfs/Press-Note-Fast-Forward-to-The-Big-League.pdf',
    ], configurations: [{ powertrain: 'ice', fuels: ['petrol', 'diesel'] }] },
  ] },
  { name: 'Hyundai', models: [
    { name: 'Creta', years: years(2020, 2024), coverage: '2020-generation onward · demo years 2020–2024', sources: [hyundaiManuals,
      'https://www.hyundai.com/in/en/hyundai-story/hyundai-motor-india/history-2016-2022'] },
    { name: 'i20', years: years(2020, 2024), coverage: '2020-generation i20 · demo years 2020–2024', sources: [hyundaiManuals] },
  ] },
  { name: 'Ferrari', models: [
    { name: '296 GTB', years: years(2022, 2024), coverage: 'Delivery-era demo years 2022–2024', sources: [
      'https://cdn.ferrari.com/cms/network/media/pdf/2023_02_02%20-%20Ferrari%20-%20FY%202022%20Results%20Presentation.pdf', ferrari2024,
      'https://lto.gov.ph/wp-content/uploads/2024/08/MC-VDM-2024-2774.pdf',
    ], configurations: [{ powertrain: 'hybrid', fuels: ['petrol-electric'] }] },
    { name: 'Roma', years: years(2020, 2024), coverage: 'Roma coupe · demo years 2020–2024 (not Roma Spider)', sources: [
      'https://www.sec.gov/Archives/edgar/data/1648416/000164841621000007/fnvfy2020resultspr.htm', ferrari2024,
      'https://cdn.ferrari.com/cms/network/media/pdf/cs_ferrari_roma_full_gbr.pdf',
    ], configurations: [{ powertrain: 'ice', fuels: ['petrol'] }] },
  ] },
];

const normalized = (value: string) => value.trim().toLowerCase();
export function demoManufacturer(name: string) {
  return demoVehicleCatalog.find(item => normalized(item.name) === normalized(name));
}
export function demoModel(manufacturer: string, model: string) {
  return demoManufacturer(manufacturer)?.models.find(item => normalized(item.name) === normalized(model));
}
export function originalModel(draft: VehicleSetupDraft, initial?: VehicleSetupDraft) {
  return Boolean(initial && draft.manufacturer === initial.manufacturer && draft.model === initial.model);
}
export function validateDemoVehicle(draft: VehicleSetupDraft, initial?: VehicleSetupDraft, manual = false): VehicleSetupErrors {
  const entry = manual ? undefined : demoModel(draft.manufacturer, draft.model);
  if (!entry) return {};
  const errors: VehicleSetupErrors = {};
  const original = originalModel(draft, initial);
  if (/^\d{4}$/.test(draft.year) && !entry.years.includes(Number(draft.year)) && !(original && draft.year === initial?.year)) {
    errors.year = 'Choose a year listed for this demo model, or use manual vehicle entry.';
  }
  const retainedConfiguration = original && draft.powertrain === initial?.powertrain && draft.fuelType === initial?.fuelType;
  if (!retainedConfiguration && draft.powertrain && entry.configurations) {
    const configurations = entry.configurations.filter(item => item.powertrain === draft.powertrain);
    if (!configurations.length) errors.powertrain = 'Choose an engine / vehicle type listed for this model.';
    else if (draft.fuelType && !configurations.some(item => item.fuels.includes(draft.fuelType))) errors.fuelType = 'Choose a fuel listed for this model.';
  }
  return errors;
}
