// Minimal account dashboard backed by saved vehicles; research recordings never supply vehicle metrics or history.
import { useRef, useState } from 'react';
import { useRouter } from 'expo-router';
import { useOnboarding } from '@/store/onboardingStore';
import { AppButton } from '@/components/ui/app-button';
import { AppCard } from '@/components/ui/app-card';
import { AppDataState } from '@/components/ui/app-data-state';
import { AppHeader } from '@/components/ui/app-header';
import { AppScreen } from '@/components/ui/app-screen';
import { AppStatus } from '@/components/ui/app-status';
import { AppText } from '@/components/ui/app-text';
import { ActiveVehicleCard } from './active-vehicle-card';

export function HomeScreen() {
  const router = useRouter();
  const { resource, saving, reload, selectActive } = useOnboarding();
  const [expanded, setExpanded] = useState(false);
  const [selectionError, setSelectionError] = useState<{ id: string; message: string } | null>(null);
  const selecting = useRef(false);

  async function activate(id: string) {
    if (saving || selecting.current || resource.status !== 'ready') return;
    if (id === resource.data.active_vehicle_id) { setSelectionError(null); setExpanded(false); return; }
    selecting.current = true;
    setSelectionError(null);
    try {
      await selectActive(id);
      setExpanded(false);
    } catch (failure) {
      setSelectionError({ id, message: failure instanceof Error ? failure.message : 'Please try again.' });
    } finally { selecting.current = false; }
  }

  return <AppScreen edges={['top', 'left', 'right']}>
    <AppText variant="caption" tone="secondary">DrivePulse AI</AppText>
    <AppHeader title="Home" />

    <AppText variant="subtitle" accessibilityRole="header">Active vehicle</AppText>
    {resource.status === 'loading' ? <AppDataState status="loading" title="Loading your vehicles" />
      : resource.status === 'error' ? <AppDataState status="error" title="Could not load your vehicles"
        message={resource.message} onRetry={() => { setSelectionError(null); void reload(); }} />
        : resource.data.vehicles.length === 0 ? <AppCard>
          <AppDataState status="empty" title="No saved vehicles yet" message="Your saved vehicles will appear here." />
          <AppButton title="Open Garage" variant="secondary" onPress={() => router.navigate('/(main)/(tabs)/vehicles')} />
        </AppCard> : <ActiveVehicleCard vehicles={resource.data.vehicles} activeId={resource.data.active_vehicle_id}
          expanded={expanded} saving={saving} onToggle={() => setExpanded(value => !value)} onSelect={id => { void activate(id); }} />}
    {selectionError && <AppCard>
      <AppStatus label="Could not switch vehicle" description={selectionError.message} tone="error" variant="notice" />
      <AppButton title="Retry vehicle selection" variant="secondary" disabled={saving}
        onPress={() => { void activate(selectionError.id); }} />
    </AppCard>}

    <AppCard>
      <AppText variant="subtitle" accessibilityRole="header">Vehicle connection</AppText>
      <AppText tone="secondary">OBD connectivity coming soon</AppText>
    </AppCard>

    <AppCard>
      <AppText variant="subtitle" accessibilityRole="header">Recent analyses</AppText>
      <AppText tone="secondary">No saved analyses yet</AppText>
      <AppButton title="View History" variant="text" icon="history" onPress={() => router.navigate('/(main)/(tabs)/history')} />
    </AppCard>

    <AppCard variant="filled">
      <AppText variant="subtitle" accessibilityRole="header">Recorded Nissan Leaf data</AppText>
      <AppText tone="secondary">Research recordings, separate from your saved vehicles. These recordings are not live data or analyses of your active vehicle.</AppText>
      <AppButton title="View recorded telemetry" variant="secondary" onPress={() => router.navigate('/(main)/(tabs)/telemetry')} />
      <AppButton title="Open recorded replay" variant="text" onPress={() => router.push('/(main)/replay')} />
    </AppCard>
  </AppScreen>;
}
