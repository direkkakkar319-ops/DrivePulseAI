// Keep unconfigured platforms from attempting to initialize Android Firebase.
import type { AuthService } from './auth.types';

const unavailable = (): never => {
  throw new Error('Authentication is configured for the Android development build. Web and iOS setup will follow.');
};

export const authService: AuthService = {
  subscribe: unavailable,
  signIn: unavailable,
  signUp: unavailable,
  saveUsername: unavailable,
  sendVerification: unavailable,
  refreshUser: unavailable,
  resetPassword: unavailable,
  signOut: unavailable,
  getToken: unavailable,
};
