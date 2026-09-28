// Send Firebase ID tokens to FastAPI; never send passwords or persist bearer tokens.
import { authService } from './auth';
import { authErrorMessage } from './auth-errors';
import type { UserProfile } from './profile.types';

export const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL?.replace(/\/+$/, '') ?? '';

export class ApiError extends Error {
  constructor(message: string, readonly status?: number) { super(message); }
}

export async function syncProfile(expectedUid: string): Promise<UserProfile> {
  if (!API_BASE_URL) throw new ApiError('The account service is not configured yet.');
  // Fresh claims include a recently saved username or verified email.
  for (let attempt = 0; attempt < 2; attempt++) {
    let token: string;
    try { token = await authService.getToken(true); }
    catch (error) { throw new ApiError(authErrorMessage(error)); }
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/users/me`, {
        method: 'PUT', headers: { Authorization: `Bearer ${token}` }, signal: controller.signal,
      });
      if (response.status === 401 && attempt === 0) continue;
      if (!response.ok) {
        const message = response.status === 401 ? 'Your session could not be verified. Please log out and log in again.'
          : response.status === 403 ? 'Verify your email before syncing your account.'
          : 'Your account could not be synced right now. Please try again.';
        throw new ApiError(message, response.status);
      }
      const profile: UserProfile = await response.json();
      if (profile.firebase_uid !== expectedUid || typeof profile.email !== 'string'
        || !(profile.username === null || typeof profile.username === 'string')
        || typeof profile.created_at !== 'string' || typeof profile.updated_at !== 'string') {
        throw new ApiError('The account service returned an unexpected response.');
      }
      return profile;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw new ApiError('Could not reach the account service. Check your connection and try again.');
    } finally { clearTimeout(timeout); }
  }
  throw new ApiError('Please log in again.');
}
