// Server-shaped fixtures used only by onboarding API and routing tests.
import type { OnboardingState, SavedVehicle } from '../src/api/onboarding';

export const vehicleId = '00000000-0000-4000-8000-000000000001';
export const secondVehicleId = '00000000-0000-4000-8000-000000000002';
export const savedVehicle = (uid = 'alice'): SavedVehicle => ({
  id: vehicleId, owner_uid: uid, manufacturer: 'Any Brand', model: 'Example EV', year: 2024,
  powertrain: 'ev', fuel_type: null, nickname: 'Personal car', created_at: '2026-01-01T00:00:00Z',
});
export function accountState(step: 'profile' | 'vehicle' | 'home' = 'profile', uid = 'alice'): OnboardingState {
  return { firebase_uid: uid, full_name: step === 'profile' ? null : 'Saved app name',
    driving_licence: step === 'profile' ? null : 'prefer-not-to-say',
    profile_completed_at: step === 'profile' ? null : '2026-01-01T00:00:00Z',
    completed_at: step === 'home' ? '2026-01-01T00:01:00Z' : null,
    first_vehicle_id: step === 'home' ? vehicleId : null,
    active_vehicle_id: step === 'home' ? vehicleId : null, vehicles: step === 'home' ? [savedVehicle(uid)] : [] };
}
