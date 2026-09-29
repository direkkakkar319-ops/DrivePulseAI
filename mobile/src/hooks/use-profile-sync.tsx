// Preserve automatic authenticated profile synchronization across signed-in tabs.
import { createContext, useContext, useEffect, useState, type PropsWithChildren } from 'react';
import { syncProfile } from '@/api/client';
import { useAuthStore } from '@/store/authStore';
function useSync() {
  const { user } = useAuthStore();
  const { uid, emailVerified, email, displayName } = user ?? {};
  const [message, setMessage] = useState('Syncing your account…');
  const [failed, setFailed] = useState(false);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    if (!uid || !emailVerified) return;
    let active = true;
    void Promise.resolve().then(async () => {
      if (!active) return;
      setFailed(false);
      setMessage('Syncing your account…');
      try {
        await syncProfile(uid);
        if (active) setMessage('Your account is synced.');
      } catch (error) {
        if (active) {
          setFailed(true);
          setMessage(error instanceof Error ? error.message : 'Could not sync your account.');
        }
      }
    });
    return () => {
      active = false;
    };
  }, [uid, emailVerified, email, displayName, revision]);
  return { message, failed, retry: () => setRevision((v) => v + 1) };
}
const Context = createContext<ReturnType<typeof useSync> | null>(null);
export function ProfileSyncProvider({ children }: PropsWithChildren) {
  const value = useSync();
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export function useProfileSync() {
  const value = useContext(Context);
  if (!value) throw new Error('ProfileSyncProvider required');
  return value;
}
