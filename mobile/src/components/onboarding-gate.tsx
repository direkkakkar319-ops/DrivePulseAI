// Single routing decision after verified authentication, based only on persisted server milestones.
import type { PropsWithChildren } from 'react';
import { Redirect, useSegments } from 'expo-router';
import { useState } from 'react';
import { useOnboarding } from '@/store/onboardingStore';
import { authService } from '@/api/auth';
import { authErrorMessage } from '@/api/auth-errors';
import { AppButton } from './ui/app-button';
import { AppDataState } from './ui/app-data-state';
import { AppScreen } from './ui/app-screen';
import { AppStatus } from './ui/app-status';

export function onboardingStep(state: { profile_completed_at: string | null; completed_at: string | null }) {
  return !state.profile_completed_at ? 'profile-setup' : !state.completed_at ? 'vehicle-setup' : 'home';
}

export function OnboardingGate({ children }: PropsWithChildren) {
  const { resource, reload } = useOnboarding();
  const route = useSegments().at(-1);
  const [error, setError] = useState(''), [loggingOut, setLoggingOut] = useState(false);
  async function logout() {
    setLoggingOut(true); setError('');
    try { await authService.signOut(); } catch (failure) { setError(authErrorMessage(failure)); }
    finally { setLoggingOut(false); }
  }
  if (resource.status !== 'ready') return <AppScreen>
    <AppDataState status={resource.status === 'error' ? 'error' : 'loading'} title={resource.status === 'error' ? 'Account unavailable' : 'Loading your account'}
      message={resource.status === 'error' ? resource.message : undefined} onRetry={() => { void reload(); }} />
    {!!error && <AppStatus label={error} tone="error" variant="notice" />}
    <AppButton title="Log out" variant="text" loading={loggingOut} onPress={logout} />
  </AppScreen>;
  const step = onboardingStep(resource.data);
  if (step === 'profile-setup' && route !== 'profile-setup') return <Redirect href="/(main)/profile-setup" />;
  if (step === 'vehicle-setup' && route !== 'vehicle-setup') return <Redirect href="/(main)/vehicle-setup" />;
  if (step === 'home' && (route === 'profile-setup' || route === 'vehicle-setup')) return <Redirect href="/(main)/dashboard" />;
  return children;
}
