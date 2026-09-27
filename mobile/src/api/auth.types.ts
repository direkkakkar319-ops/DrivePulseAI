// Platform-independent account state and Firebase authentication operations.
export interface AuthUser {
  uid: string;
  email: string | null;
  emailVerified: boolean;
  displayName: string | null;
}

export interface AuthService {
  subscribe: (listener: (user: AuthUser | null) => void) => () => void;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, username: string) => Promise<{ uid: string; profileSaved: boolean }>;
  saveUsername: (uid: string, username: string) => Promise<void>;
  sendVerification: () => Promise<void>;
  refreshUser: () => Promise<AuthUser | null>;
  resetPassword: (email: string) => Promise<void>;
  signOut: () => Promise<void>;
  getToken: (forceRefresh?: boolean) => Promise<string>;
}
