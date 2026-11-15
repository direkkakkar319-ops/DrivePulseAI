// User-entered vehicle metadata contracts, separate from simulated Garage and telemetry types.
export type Powertrain = 'ice' | 'hybrid' | 'ev';
export type IceFuelType = 'petrol' | 'diesel' | 'cng';
export type HybridFuelType = 'petrol-electric' | 'diesel-electric';
export type VehicleFuelType = IceFuelType | HybridFuelType;

export interface VehicleSetupDraft {
  powertrain: Powertrain | null;
  manufacturer: string;
  model: string;
  year: string;
  fuelType: VehicleFuelType | null;
  nickname: string;
}

interface VehicleDetails {
  manufacturer: string;
  model: string;
  year: number;
  nickname: string | null;
}

/** Validated input for a future storage adapter; never implies connected telemetry. */
export type VehicleSetupValue = VehicleDetails & (
  | { powertrain: 'ice'; fuelType: IceFuelType }
  | { powertrain: 'hybrid'; fuelType: HybridFuelType }
  | { powertrain: 'ev'; fuelType: null }
);

export type VehicleSetupErrors = Partial<Record<keyof VehicleSetupDraft, string>>;
export type VehicleSetupValidation =
  | { valid: true; value: VehicleSetupValue; errors: VehicleSetupErrors }
  | { valid: false; errors: VehicleSetupErrors };
