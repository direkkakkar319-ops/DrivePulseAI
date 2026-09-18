// Auth contracts mirrored by backend/app/schemas/auth.py.
export interface AuthUser { id: string; email: string }
export interface Credentials { email: string; password: string }
export interface SessionResponse {
  access_token: string;
  token_type: 'bearer';
  expires_at: number;
  user: AuthUser;
}
