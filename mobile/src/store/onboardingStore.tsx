// Server-authoritative account onboarding and saved vehicles; no durable in-memory substitute.
import { createContext, useCallback, useContext, useEffect, useRef, useState, type PropsWithChildren } from 'react';
import { onboardingApi, type OnboardingApi, type OnboardingState, type ProfileSetupInput } from '@/api/onboarding';
import type { VehicleSetupValue } from '@/types/vehicle-setup';

type Resource = { status: 'loading' } | { status: 'error'; message: string } | { status: 'ready'; data: OnboardingState };
function useAccount(uid: string, api: OnboardingApi) {
  const [resource, setResource] = useState<Resource>({ status: 'loading' });
  const [saving, setSaving] = useState(false);
  const alive = useRef(true), request = useRef(0), busy = useRef(false);
  const invalidate = useCallback(() => { alive.current = false; request.current++; }, []);
  const reload = useCallback(async () => {
    if (busy.current) return;
    const ticket = ++request.current;
    setResource({ status: 'loading' });
    try { const data = await api.load(uid); if (alive.current && ticket === request.current) setResource({ status: 'ready', data }); }
    catch (error) { if (alive.current && ticket === request.current) setResource({ status: 'error', message: error instanceof Error ? error.message : 'Could not load your account.' }); }
  }, [api, uid]);
  useEffect(() => {
    alive.current = true;
    void Promise.resolve().then(() => { if (alive.current) void reload(); });
    return invalidate;
  }, [reload, invalidate]);
  async function mutate(operation: () => Promise<OnboardingState>) {
    if (!alive.current || busy.current) throw new Error('An account request is already in progress.');
    busy.current = true; setSaving(true);
    const ticket = ++request.current;
    try {
      const data = await operation();
      if (!alive.current || ticket !== request.current) throw new Error('The account has changed.');
      setResource({ status: 'ready', data });
    } finally { busy.current = false; if (alive.current) setSaving(false); }
  }
  return { resource, saving, reload,
    saveProfile: (input: ProfileSetupInput) => mutate(() => api.saveProfile(uid, input)),
    saveFirstVehicle: (input: VehicleSetupValue) => mutate(() => api.saveFirstVehicle(uid, input)),
    selectActive: (id: string) => mutate(() => api.selectActive(uid, id)),
  };
}
const Context = createContext<ReturnType<typeof useAccount> | null>(null);
export function OnboardingProvider({ uid, api = onboardingApi, children }: PropsWithChildren<{ uid: string; api?: OnboardingApi }>) {
  return <AccountProvider key={uid} uid={uid} api={api}>{children}</AccountProvider>;
}
function AccountProvider({ uid, api, children }: PropsWithChildren<{ uid: string; api: OnboardingApi }>) {
  const value = useAccount(uid, api);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export function useOnboarding() {
  const value = useContext(Context);
  if (!value) throw new Error('useOnboarding requires OnboardingProvider');
  return value;
}
