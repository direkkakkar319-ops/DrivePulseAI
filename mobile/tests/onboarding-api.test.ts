// Exercise authenticated wire contracts and ensure photos and cross-account state never pass through.
import { onboardingApi, vehicleManagementApi, validateOnboarding } from '../src/api/onboarding';
import { authService } from '../src/api/auth';
import { accountState } from './onboarding-fixtures';

jest.mock('../src/api/auth', () => ({ authService: { getToken: jest.fn() } }));
jest.mock('../src/api/client', () => {
  const actual = jest.requireActual('../src/api/client');
  return { ...actual, API_BASE_URL: 'https://api.example.test' };
});
const originalFetch = global.fetch;
beforeEach(() => { jest.clearAllMocks(); global.fetch = jest.fn(); (authService.getToken as jest.Mock).mockResolvedValue('token'); });
afterEach(() => { global.fetch = originalFetch; jest.useRealTimers(); });
function response(status: number, data = accountState()) {
  return { status, ok: status >= 200 && status < 300, json: async () => data };
}

it('loads durable state with a fresh token and explicit expected-account precondition', async () => {
  (fetch as jest.Mock).mockResolvedValue(response(200));
  await expect(onboardingApi.load('alice')).resolves.toEqual(accountState());
  expect(fetch).toHaveBeenCalledWith('https://api.example.test/api/v1/onboarding', expect.objectContaining({
    method: 'GET', headers: { Authorization: 'Bearer token', 'X-Account-UID': 'alice' },
  }));
});

it('persists active vehicle selection through the existing authenticated vehicle endpoint', async () => {
  const state = accountState('home');
  (fetch as jest.Mock).mockResolvedValue(response(200, state));
  await expect(onboardingApi.selectActive('alice', state.active_vehicle_id!)).resolves.toEqual(state);
  expect(fetch).toHaveBeenCalledWith(`https://api.example.test/api/v1/vehicles/${state.active_vehicle_id}/active`, expect.objectContaining({
    method: 'PUT', body: '{}', headers: {
      Authorization: 'Bearer token', 'X-Account-UID': 'alice', 'Content-Type': 'application/json',
    },
  }));
});

it('sends only explicit app profile data and never local photo references or a user-supplied owner', async () => {
  (fetch as jest.Mock).mockResolvedValue(response(200, accountState('vehicle')));
  const input = { full_name: 'Chosen name', driving_licence: 'no' as const, photo: 'file:///private-preview.jpg' };
  await onboardingApi.saveProfile('alice', input);
  const body = JSON.parse((fetch as jest.Mock).mock.calls[0][1].body);
  expect(body).toEqual({ full_name: 'Chosen name', driving_licence: 'no' });
  expect(authService.getToken).toHaveBeenCalledWith(true);
});

it('maps the typed vehicle input to the backend fuel_type contract', async () => {
  (fetch as jest.Mock).mockResolvedValue(response(200, accountState('home')));
  await onboardingApi.saveFirstVehicle('alice', { powertrain: 'ev', manufacturer: 'Any Brand', model: 'Example EV', year: 2024, fuelType: null, nickname: null });
  expect(JSON.parse((fetch as jest.Mock).mock.calls[0][1].body)).toEqual({ powertrain: 'ev', manufacturer: 'Any Brand', model: 'Example EV', year: 2024, fuel_type: null, nickname: null });
});

it('accepts a completed empty Garage and a removed original first vehicle', () => {
  const complete = accountState('home');
  expect(validateOnboarding({ ...complete, vehicles: [], first_vehicle_id: null, active_vehicle_id: null }, 'alice').completed_at).toBe(complete.completed_at);
  expect(validateOnboarding({ ...complete, first_vehicle_id: null }, 'alice').vehicles).toHaveLength(1);
  expect(() => validateOnboarding({ ...complete, active_vehicle_id: null }, 'alice')).toThrow('unexpected');
});

it('creates with a stable request ID and reloads authoritative account state', async () => {
  const state = accountState('home');
  (fetch as jest.Mock).mockResolvedValueOnce(response(201, state)).mockResolvedValueOnce(response(200, state));
  await expect(vehicleManagementApi.create('alice', { powertrain: 'ev', manufacturer: 'Any Brand', model: 'Example EV', year: 2024, fuelType: null, nickname: null }, state.active_vehicle_id!)).resolves.toEqual(state);
  expect(fetch).toHaveBeenNthCalledWith(1, 'https://api.example.test/api/v1/vehicles', expect.objectContaining({
    method: 'POST', headers: expect.objectContaining({ 'X-Vehicle-ID': state.active_vehicle_id, 'X-Account-UID': 'alice' }),
  }));
  expect(fetch).toHaveBeenNthCalledWith(2, 'https://api.example.test/api/v1/onboarding', expect.objectContaining({ method: 'GET' }));
});

it('edits through the owner-authenticated PUT endpoint', async () => {
  const state = accountState('home'); (fetch as jest.Mock).mockResolvedValue(response(200, state));
  await vehicleManagementApi.update('alice', state.active_vehicle_id!, { powertrain: 'ev', manufacturer: 'Any Brand', model: 'Example EV', year: 2024, fuelType: null, nickname: 'Edited' });
  expect(fetch).toHaveBeenCalledWith(`https://api.example.test/api/v1/vehicles/${state.active_vehicle_id}`, expect.objectContaining({ method: 'PUT' }));
  expect(JSON.parse((fetch as jest.Mock).mock.calls[0][1].body).nickname).toBe('Edited');
});

it('deletes without a body and recovers a lost successful response through reload', async () => {
  const state = { ...accountState('home'), vehicles: [], first_vehicle_id: null, active_vehicle_id: null };
  (fetch as jest.Mock).mockResolvedValueOnce(response(404)).mockResolvedValueOnce(response(200, state));
  await expect(vehicleManagementApi.remove('alice', accountState('home').active_vehicle_id!)).resolves.toEqual(state);
  expect((fetch as jest.Mock).mock.calls[0][1]).toMatchObject({ method: 'DELETE', headers: expect.objectContaining({ Authorization: 'Bearer token' }) });
  expect((fetch as jest.Mock).mock.calls[0][1].body).toBeUndefined();
});

it('retries one 401 with refreshed credentials', async () => {
  (fetch as jest.Mock).mockResolvedValueOnce(response(401)).mockResolvedValueOnce(response(200));
  await onboardingApi.load('alice');
  expect(fetch).toHaveBeenCalledTimes(2);
  expect(authService.getToken).toHaveBeenCalledTimes(2);
});

it.each([403, 409, 422, 503])('does not retry or accept failed account response %s', async status => {
  (fetch as jest.Mock).mockResolvedValue(response(status));
  await expect(onboardingApi.load('alice')).rejects.toMatchObject({ status });
  expect(fetch).toHaveBeenCalledTimes(1);
});

it('rejects another account and inconsistent completion or active selection', () => {
  expect(() => validateOnboarding(accountState('home', 'bob'), 'alice')).toThrow('unexpected');
  expect(() => validateOnboarding({ ...accountState(), completed_at: '2026-01-01T00:00:00Z' }, 'alice')).toThrow('unexpected');
  expect(() => validateOnboarding({ ...accountState('home'), active_vehicle_id: '00000000-0000-4000-8000-000000000099' }, 'alice')).toThrow('unexpected');
  const state = accountState('home');
  state.vehicles[0].owner_uid = 'bob';
  expect(() => validateOnboarding(state, 'alice')).toThrow('unexpected');
});

it('does not fetch when Firebase cannot provide a verified token', async () => {
  (authService.getToken as jest.Mock).mockRejectedValue({ code: 'auth/network-request-failed' });
  await expect(onboardingApi.load('alice')).rejects.toThrow('Could not connect');
  expect(fetch).not.toHaveBeenCalled();
});

it('aborts an unavailable backend rather than inventing completed onboarding', async () => {
  jest.useFakeTimers();
  (fetch as jest.Mock).mockImplementation((_url, options) => new Promise((_resolve, reject) => {
    options.signal.addEventListener('abort', () => reject(new Error('aborted')));
  }));
  const assertion = expect(onboardingApi.load('alice')).rejects.toThrow('Could not reach');
  await jest.advanceTimersByTimeAsync(15000);
  await assertion;
});
