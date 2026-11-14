// API profile contract; mirrored by backend/app/schemas/user.py and mobile/src/api/profile.types.ts.
export interface UserProfile {
  firebase_uid: string;
  email: string;
  username: string | null;
  created_at: string;
  updated_at: string;
}

// Durable onboarding contracts mirrored by backend/app/schemas/onboarding.py.
export interface VehicleInput {
  powertrain: 'ice' | 'hybrid' | 'ev';
  manufacturer: string;
  model: string;
  year: number;
  fuel_type: 'petrol' | 'diesel' | 'cng' | 'petrol-electric' | 'diesel-electric' | null;
  nickname: string | null;
}
export interface SavedVehicleResponse extends VehicleInput {
  id: string;
  owner_uid: string;
  created_at: string;
}
export interface ProfileSetupInput {
  full_name: string | null;
  driving_licence: 'yes' | 'no' | 'prefer-not-to-say' | null;
}
export interface OnboardingResponse extends ProfileSetupInput {
  firebase_uid: string;
  profile_completed_at: string | null;
  completed_at: string | null;
  first_vehicle_id: string | null;
  active_vehicle_id: string | null;
  vehicles: SavedVehicleResponse[];
}
