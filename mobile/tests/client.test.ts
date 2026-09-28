// Verify bearer-token requests, bounded retries, identity matching, and safe errors.
import { authService } from '../src/api/auth';

jest.mock('../src/api/auth', () => ({ authService: { getToken: jest.fn() } }));
const previousUrl = process.env.EXPO_PUBLIC_API_URL;
process.env.EXPO_PUBLIC_API_URL = 'https://api.example.test/';
const { syncProfile } = require('../src/api/client') as typeof import('../src/api/client');
const originalFetch = global.fetch;
const profile = { firebase_uid: 'alice', email: 'alice@example.com', username: 'Driver', created_at: '2026-09-27T00:00:00Z', updated_at: '2026-09-27T00:00:00Z' };
const response = (status: number, body = profile) => ({ status, ok: status < 400, json: async () => body });

beforeEach(() => {
  jest.resetAllMocks();
  global.fetch = jest.fn();
  (authService.getToken as jest.Mock).mockResolvedValue('id-token');
});
afterEach(() => { global.fetch = originalFetch; jest.useRealTimers(); });
afterAll(() => {
  if (previousUrl === undefined) delete process.env.EXPO_PUBLIC_API_URL;
  else process.env.EXPO_PUBLIC_API_URL = previousUrl;
});

it('sends only a bearer token and lets the backend identify the current user', async () => {
  (fetch as jest.Mock).mockResolvedValue(response(200));
  await expect(syncProfile('alice')).resolves.toEqual(profile);
  expect(authService.getToken).toHaveBeenCalledWith(true);
  expect(fetch).toHaveBeenCalledWith('https://api.example.test/api/v1/users/me', {
    method: 'PUT', headers: { Authorization: 'Bearer id-token' }, signal: expect.anything(),
  });
});

it('refreshes the token and retries once on 401', async () => {
  (authService.getToken as jest.Mock).mockResolvedValueOnce('old').mockResolvedValueOnce('new');
  (fetch as jest.Mock).mockResolvedValueOnce(response(401)).mockResolvedValueOnce(response(200));
  await expect(syncProfile('alice')).resolves.toEqual(profile);
  expect(fetch).toHaveBeenCalledTimes(2);
  expect((fetch as jest.Mock).mock.calls[1][1].headers.Authorization).toBe('Bearer new');
});

it.each([401, 403, 503])('stops retrying failed authentication/storage responses (%s)', async (status) => {
  (fetch as jest.Mock).mockResolvedValue(response(status));
  await expect(syncProfile('alice')).rejects.toMatchObject({ status });
  expect(fetch).toHaveBeenCalledTimes(status === 401 ? 2 : 1);
});

it('does not accept a profile for a different account', async () => {
  (fetch as jest.Mock).mockResolvedValue(response(200));
  await expect(syncProfile('bob')).rejects.toThrow('unexpected response');
});

it('does not call the backend when Firebase cannot produce a token', async () => {
  (authService.getToken as jest.Mock).mockRejectedValue({ code: 'auth/network-request-failed' });
  await expect(syncProfile('alice')).rejects.toThrow('Could not connect');
  expect(fetch).not.toHaveBeenCalled();
});

it('aborts a hanging request and exposes a recoverable network message', async () => {
  jest.useFakeTimers();
  (fetch as jest.Mock).mockImplementation((_url, options) => new Promise((_resolve, reject) => {
    options.signal.addEventListener('abort', () => reject(new Error('aborted')));
  }));
  const assertion = expect(syncProfile('alice')).rejects.toThrow('Could not reach the account service');
  await jest.advanceTimersByTimeAsync(15000);
  await assertion;
});
