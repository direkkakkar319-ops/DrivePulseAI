// Configurable API transport and authentication endpoints.
import { Platform } from 'react-native';
import type { AuthUser, Credentials, SessionResponse } from '@/types/auth';

export const API_BASE_URL = (process.env.EXPO_PUBLIC_API_URL ||
  (Platform.OS === 'android' ? 'http://10.0.2.2:8000' : 'http://localhost:8000')).replace(/\/$/, '');
export const WS_BASE_URL = `${API_BASE_URL.replace(/^http/, 'ws')}/ws`;
export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}
export async function request<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: { 'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers },
      signal: controller.signal,
    });
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new ApiError(response.status, typeof body?.detail === 'string'
        ? body.detail : 'The request failed. Check your details and try again.');
    }
    return response.status === 204 ? undefined as T : await response.json();
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new Error('Unable to reach the server. Check your connection and try again.');
  } finally { clearTimeout(timeout); }
}
export const authApi = {
  login: (body: Credentials) => request<SessionResponse>('/auth/login', {
    method: 'POST', body: JSON.stringify(body),
  }),
  register: (body: Credentials) => request<SessionResponse>('/auth/register', {
    method: 'POST', body: JSON.stringify(body),
  }),
  google: (idToken: string) => request<SessionResponse>('/auth/google', {
    method: 'POST', body: JSON.stringify({ id_token: idToken }),
  }),
  me: (token: string) => request<AuthUser>('/auth/me', {}, token),
  logout: (token: string) => request<void>('/auth/logout', { method: 'POST' }, token),
};
export const fetchVehicles = async () => {
  // Vehicle API remains scaffolded.
  return [];
};
