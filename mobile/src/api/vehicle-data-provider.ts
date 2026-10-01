// Replace this boundary with an authenticated API adapter when contracts exist.
import type { Vehicle, VehicleDraft, VehicleSnapshot } from '@/types/vehicle-health';
export interface VehicleDataProvider {
  listVehicles(): Promise<Vehicle[]>;
  saveVehicle(draft: VehicleDraft, id?: string): Promise<Vehicle>;
  getSnapshot(vehicleId: string): Promise<VehicleSnapshot>;
}
