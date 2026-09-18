// Shared session state, secure persistence, validation, and logout.
import { createContext, useCallback, useContext, useEffect, useRef, useState,
  type PropsWithChildren } from 'react';
import { AppState } from 'react-native';
import { ApiError, authApi } from '@/api/client';
import { sessionStorage } from '@/auth/storage';
import type { SessionResponse } from '@/types/auth';
interface AuthState {
  session: SessionResponse | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  login: (session: SessionResponse) => Promise<void>;
  logout: () => Promise<void>;
  restore: () => Promise<void>;
}
const AuthContext = createContext<AuthState | null>(null);
export function AuthProvider({ children }: PropsWithChildren) {
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [isLoading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const revision = useRef(0);
  const restore = useCallback(async () => {
    const version = ++revision.current;
    setLoading(true);
    setError(null);
    try {
      const saved = await sessionStorage.get();
      if (!saved) { if (version === revision.current) setSession(null); return; }
      let parsed: SessionResponse;
      try { parsed = JSON.parse(saved); } catch {
        await sessionStorage.remove(); setSession(null); return;
      }
      if (!parsed || typeof parsed.access_token !== 'string' ||
          typeof parsed.expires_at !== 'number' || parsed.expires_at * 1000 <= Date.now()) {
        await sessionStorage.remove(); setSession(null); return;
      }
      const user = await authApi.me(parsed.access_token);
      if (version === revision.current) setSession({ ...parsed, user });
    } catch (error) {
      if (version !== revision.current) return;
      setSession(null);
      if (error instanceof ApiError && error.status === 401) {
        await sessionStorage.remove().catch(() => setError('Could not clear the saved session.'));
      } else setError('Could not restore your session. Check your connection and retry.');
    } finally { if (version === revision.current) setLoading(false); }
  }, []);
  useEffect(() => {
    // Hydration synchronizes React state with asynchronous device storage.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void restore();
  }, [restore]);
  useEffect(() => {
    const subscription = AppState.addEventListener('change', (state) => {
      if (state === 'active' && session) void restore();
    });
    return () => subscription.remove();
  }, [restore, session]);
  useEffect(() => {
    if (!session) return;
    const timer = setTimeout(() => {
      setSession(null);
      void sessionStorage.remove().catch(() => setError('Could not clear the expired session.'));
    }, Math.max(0, session.expires_at * 1000 - Date.now()));
    return () => clearTimeout(timer);
  }, [session]);
  const login = async (next: SessionResponse) => {
    ++revision.current;
    await sessionStorage.set(JSON.stringify(next));
    setSession(next); setError(null); setLoading(false);
  };
  const logout = async () => {
    ++revision.current;
    if (session) {
      try { await authApi.logout(session.access_token); }
      catch (error) {
        if (!(error instanceof ApiError && error.status === 401)) throw error;
      }
    }
    await sessionStorage.remove();
    setSession(null); setError(null);
  };
  return <AuthContext.Provider value={{ session, isAuthenticated: !!session,
    isLoading, error, login, logout, restore }}>{children}</AuthContext.Provider>;
}
export function useAuthStore() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuthStore must be used inside AuthProvider');
  return context;
}
