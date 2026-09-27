// Share Firebase session state without storing passwords or tokens in React state.
import { createContext, createElement, useContext, useEffect, useState, type PropsWithChildren } from 'react';
import { authService } from '@/api/auth';
import type { AuthUser } from '@/api/auth.types';

interface AuthState {
  user: AuthUser | null;
  initializing: boolean;
  startupError: string | null;
  refreshUser: () => Promise<boolean>;
  createAccount: (email: string, password: string, username: string) => Promise<void>;
  usernameSavePending: boolean;
  retryUsername: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: PropsWithChildren) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [initializing, setInitializing] = useState(true);
  const [startupError, setStartupError] = useState<string | null>(null);
  const [pendingUsername, setPendingUsername] = useState<{ uid: string; username: string } | null>(null);

  useEffect(() => {
    try {
      return authService.subscribe((nextUser) => {
        setUser(nextUser);
        setPendingUsername((pending) => pending?.uid === nextUser?.uid ? pending : null);
        setInitializing(false);
      });
    } catch {
      // A one-time native SDK initialization failure must replace the loading screen.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setStartupError('Open the Android development build to use authentication. If you are already using it, rebuild the app with its Firebase configuration.');
      setInitializing(false);
    }
  }, []);

  async function refreshUser() {
    const updated = await authService.refreshUser();
    setUser(updated);
    return updated?.emailVerified === true;
  }

  async function createAccount(email: string, password: string, username: string) {
    const result = await authService.signUp(email, password, username);
    if (!result.profileSaved) setPendingUsername({ uid: result.uid, username });
  }

  async function retryUsername() {
    if (!pendingUsername || pendingUsername.uid !== user?.uid) return;
    await authService.saveUsername(pendingUsername.uid, pendingUsername.username);
    setPendingUsername(null);
  }

  return createElement(AuthContext.Provider, {
    value: { user, initializing, startupError, refreshUser, createAccount,
      usernameSavePending: !!pendingUsername && pendingUsername.uid === user?.uid, retryUsername },
  }, children);
}

export function useAuthStore(): AuthState {
  const value = useContext(AuthContext);
  if (!value) throw new Error('useAuthStore must be used within AuthProvider.');
  return value;
}
