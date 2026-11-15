// Authenticated PostgreSQL onboarding adapter; local photo URIs never enter requests.
import { authService } from './auth';
import { authErrorMessage } from './auth-errors';
import { API_BASE_URL, ApiError } from './client';
import { validateVehicleSetup } from '@/lib/vehicle-setup';
import type { DrivingLicenceAnswer } from '@/types/profile-onboarding';
import type { VehicleSetupValue } from '@/types/vehicle-setup';

export interface SavedVehicle {
  id: string; owner_uid: string; powertrain: 'ice' | 'hybrid' | 'ev'; manufacturer: string;
  model: string; year: number; fuel_type: VehicleSetupValue['fuelType']; nickname: string | null; created_at: string;
}
export interface OnboardingState {
  firebase_uid: string; full_name: string | null; driving_licence: DrivingLicenceAnswer | null;
  profile_completed_at: string | null; completed_at: string | null;
  first_vehicle_id: string | null; active_vehicle_id: string | null; vehicles: SavedVehicle[];
}
export interface ProfileSetupInput { full_name: string | null; driving_licence: DrivingLicenceAnswer | null }
export interface OnboardingApi {
  load: (uid: string) => Promise<OnboardingState>;
  saveProfile: (uid: string, input: ProfileSetupInput) => Promise<OnboardingState>;
  saveFirstVehicle: (uid: string, input: VehicleSetupValue) => Promise<OnboardingState>;
  selectActive: (uid: string, id: string) => Promise<OnboardingState>;
}
export interface VehicleManagementApi {
  create: (uid: string, input: VehicleSetupValue, requestId: string) => Promise<OnboardingState>;
  update: (uid: string, id: string, input: VehicleSetupValue) => Promise<OnboardingState>;
  remove: (uid: string, id: string) => Promise<OnboardingState>;
}

const nullableText = (v: unknown) => v === null || typeof v === 'string';
const timestamp = (v: unknown) => v === null || (typeof v === 'string' && Number.isFinite(Date.parse(v)));
const uuid = (v: unknown): v is string => typeof v === 'string' && /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(v);

export function validateOnboarding(value: unknown, uid: string): OnboardingState {
  const bad = () => new ApiError('The account service returned an unexpected onboarding response.');
  if (!value || typeof value !== 'object') throw bad();
  const state = value as OnboardingState;
  if (state.firebase_uid !== uid || !nullableText(state.full_name)
    || ![null, 'yes', 'no', 'prefer-not-to-say'].includes(state.driving_licence)
    || !timestamp(state.profile_completed_at) || !timestamp(state.completed_at)
    || !(state.first_vehicle_id === null || uuid(state.first_vehicle_id))
    || !(state.active_vehicle_id === null || uuid(state.active_vehicle_id)) || !Array.isArray(state.vehicles)) throw bad();
  const ids = new Set<string>();
  for (const vehicle of state.vehicles) {
    if (!vehicle || !uuid(vehicle.id) || ids.has(vehicle.id) || vehicle.owner_uid !== uid
      || typeof vehicle.manufacturer !== 'string' || typeof vehicle.model !== 'string'
      || !Number.isInteger(vehicle.year) || !nullableText(vehicle.nickname)
      || typeof vehicle.created_at !== 'string' || !timestamp(vehicle.created_at)
      || !validateVehicleSetup({ powertrain: vehicle.powertrain, manufacturer: vehicle.manufacturer, model: vehicle.model,
        year: String(vehicle.year), nickname: vehicle.nickname ?? '', fuelType: vehicle.fuel_type }).valid
      || (vehicle.powertrain === 'ev' && vehicle.fuel_type !== null)) throw bad();
    ids.add(vehicle.id);
  }
  if ((state.profile_completed_at && !state.full_name?.trim())
    || (state.first_vehicle_id && !ids.has(state.first_vehicle_id))
    || (state.active_vehicle_id && !ids.has(state.active_vehicle_id))
    || (state.completed_at && (!state.profile_completed_at || (state.vehicles.length > 0 && !state.active_vehicle_id)))) throw bad();
  return state;
}

async function requestRaw(uid: string, path: string, body?: unknown, method = body === undefined ? 'GET' : 'PUT', extraHeaders: Record<string, string> = {}): Promise<unknown> {
  if (!API_BASE_URL) throw new ApiError('The account service is not configured yet.');
  for (let attempt = 0; attempt < 2; attempt++) {
    let token: string;
    try { token = await authService.getToken(true); }
    catch (error) { throw new ApiError(authErrorMessage(error)); }
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1${path}`, {
        method,
        headers: { Authorization: `Bearer ${token}`, 'X-Account-UID': uid, ...extraHeaders, ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }), signal: controller.signal,
      });
      if (response.status === 401 && attempt === 0) continue;
      if (!response.ok) throw new ApiError(response.status === 409
        ? 'Your account state changed. Reload your account and try again.'
        : response.status === 403 ? 'Verify your email before continuing.'
          : response.status === 422 ? 'Check your profile or vehicle details and try again.'
            : 'Could not load or save your account. Please try again.', response.status);
      return await response.json();
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw new ApiError('Could not reach the account service. Check your connection and try again.');
    } finally { clearTimeout(timer); }
  }
  throw new ApiError('Please log in again.');
}

async function request(uid: string, path: string, body?: unknown, method?: string): Promise<OnboardingState> {
  return validateOnboarding(await requestRaw(uid, path, body, method), uid);
}

function vehicleInput(input: VehicleSetupValue) {
  return { powertrain: input.powertrain, manufacturer: input.manufacturer, model: input.model, year: input.year,
    fuel_type: input.fuelType, nickname: input.nickname };
}

export const vehicleManagementApi: VehicleManagementApi = {
  create: async (uid, input, requestId) => {
    await requestRaw(uid, '/vehicles', vehicleInput(input), 'POST', { 'X-Vehicle-ID': requestId });
    return request(uid, '/onboarding');
  },
  update: (uid, id, input) => request(uid, `/vehicles/${encodeURIComponent(id)}`, vehicleInput(input)),
  remove: async (uid, id) => {
    try { return await request(uid, `/vehicles/${encodeURIComponent(id)}`, undefined, 'DELETE'); }
    catch (error) {
      // A previous DELETE may have committed before its response was lost.
      if (error instanceof ApiError && error.status === 404) return request(uid, '/onboarding');
      throw error;
    }
  },
};

export const onboardingApi: OnboardingApi = {
  load: uid => request(uid, '/onboarding'),
  saveProfile: (uid, input) => request(uid, '/onboarding/profile', {
    full_name: input.full_name, driving_licence: input.driving_licence,
  }),
  saveFirstVehicle: (uid, input) => request(uid, '/onboarding/first-vehicle', {
    powertrain: input.powertrain, manufacturer: input.manufacturer, model: input.model, year: input.year,
    fuel_type: input.fuelType, nickname: input.nickname,
  }),
  selectActive: (uid, id) => request(uid, `/vehicles/${encodeURIComponent(id)}/active`, {}),
};
