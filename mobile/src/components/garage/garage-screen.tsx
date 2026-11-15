// Account-owned Garage management; the shared provider keeps Home and Garage synchronized.
import { useRef, useState } from 'react';
import { Alert, StyleSheet, View } from 'react-native';
import { uuid } from 'expo-modules-core';
import { useRouter } from 'expo-router';
import { useOnboarding } from '@/store/onboardingStore';
import type { SavedVehicle } from '@/api/onboarding';
import type { VehicleSetupValue } from '@/types/vehicle-setup';
import { fuelOptionsFor, powertrainOptions } from '@/lib/vehicle-setup';
import { savedVehicleName } from '@/components/home/active-vehicle-card';
import { VehicleSetupForm } from '@/components/vehicle-setup-form';
import { AppButton } from '@/components/ui/app-button';
import { AppCard } from '@/components/ui/app-card';
import { AppDataState } from '@/components/ui/app-data-state';
import { AppHeader } from '@/components/ui/app-header';
import { AppIcon } from '@/components/ui/app-icon';
import { AppScreen } from '@/components/ui/app-screen';
import { AppStatus } from '@/components/ui/app-status';
import { AppText } from '@/components/ui/app-text';
import { colors, radii, spacing } from '@/theme/tokens';

type Editor = { id: string; vehicle?: SavedVehicle };
export function GarageScreen() {
  const saved = useOnboarding();
  const router = useRouter();
  const [editor, setEditor] = useState<Editor | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const busy = useRef(false);

  async function run(operation: () => Promise<void>) {
    if (busy.current || saved.saving) return;
    busy.current = true; setError(''); setNotice('');
    try { await operation(); }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not save changes. Please try again.'); }
    finally { busy.current = false; }
  }
  function confirmRemove(vehicle: SavedVehicle) {
    Alert.alert('Remove vehicle?', `Remove ${savedVehicleName(vehicle)} from your account? If it is active, your oldest remaining saved vehicle will become active. If none remain, your Garage will be empty. Your onboarding stays complete.`, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Remove', style: 'destructive', onPress: () => { void run(async () => {
        await saved.removeVehicle(vehicle.id);
        setNotice('Vehicle removed. Review your active vehicle below.');
      }); } },
    ]);
  }
  async function save(value: VehicleSetupValue) {
    if (!editor) return;
    if (editor.vehicle) await saved.updateVehicle(editor.id, value);
    else await saved.createVehicle(value, editor.id);
    setEditor(null); setNotice('Vehicle saved.');
  }

  if (editor) return <AppScreen edges={['top', 'left', 'right']} keyboardAvoiding>
    <AppHeader title={editor.vehicle ? 'Edit vehicle' : 'Add vehicle'} />
    <AppButton title="Cancel" variant="text" disabled={saved.saving} onPress={() => setEditor(null)} />
    <VehicleSetupForm key={editor.id} submitLabel="Save vehicle" onSubmit={save} initialValues={editor.vehicle ? {
      powertrain: editor.vehicle.powertrain, manufacturer: editor.vehicle.manufacturer, model: editor.vehicle.model,
      year: String(editor.vehicle.year), fuelType: editor.vehicle.fuel_type, nickname: editor.vehicle.nickname ?? '',
    } : undefined} />
  </AppScreen>;

  return <AppScreen edges={['top', 'left', 'right']}>
    <AppHeader title="My Garage" subtitle="Your saved vehicles" />
    {!!notice && <AppStatus label={notice} tone="success" variant="notice" />}
    {!!error && <AppStatus label={error} tone="error" variant="notice" />}
    {saved.resource.status === 'loading' ? <AppDataState status="loading" title="Loading your vehicles" />
      : saved.resource.status === 'error' ? <AppDataState status="error" title="Could not load Garage"
        message={saved.resource.message} onRetry={() => { void saved.reload(); }} /> : <>
        {saved.resource.data.vehicles.length === 0 && <AppDataState status="empty" title="No saved vehicles yet"
          message="Add a vehicle to your Garage. Your onboarding is already complete." />}
        {saved.resource.data.vehicles.map(vehicle => {
          const active = saved.resource.status === 'ready' && saved.resource.data.active_vehicle_id === vehicle.id;
          const name = savedVehicleName(vehicle);
          const fuel = fuelOptionsFor(vehicle.powertrain).find(option => option.value === vehicle.fuel_type)?.label;
          return <AppCard key={vehicle.id}>
            <View style={styles.row}>
              <View style={styles.placeholder}><AppIcon name="car" size={28} color={colors.textSecondary} /></View>
              <View style={styles.copy}>
                <AppText variant="subtitle">{name}</AppText>
                <AppText tone="secondary">{vehicle.manufacturer} · {vehicle.model} · {vehicle.year}</AppText>
                <AppText tone="secondary">{powertrainOptions.find(option => option.value === vehicle.powertrain)?.label}{fuel ? ` · ${fuel}` : ''}</AppText>
              </View>
            </View>
            {active && <AppStatus label="Active vehicle" tone="info" icon="check" />}
            <AppText variant="caption" tone="secondary">Saved to your account · No connected telemetry</AppText>
            <View style={styles.actions}>
              {!active && <AppButton title="Set active" accessibilityLabel={`Set ${name} active`} variant="secondary" disabled={saved.saving}
                onPress={() => { void run(async () => { await saved.selectActive(vehicle.id); }); }} />}
              <AppButton title="Edit" accessibilityLabel={`Edit ${name}`} variant="text" disabled={saved.saving}
                onPress={() => { setError(''); setNotice(''); setEditor({ id: vehicle.id, vehicle }); }} />
              <AppButton title="Remove" accessibilityLabel={`Remove ${name}`} variant="text" disabled={saved.saving} onPress={() => confirmRemove(vehicle)} />
            </View>
          </AppCard>;
        })}
        <AppButton title="Add Vehicle" icon="plus" style={styles.add} disabled={saved.saving}
          onPress={() => { setError(''); setNotice(''); setEditor({ id: uuid.v4() }); }} />
      </>}
    <AppButton title="Explore simulated Garage" variant="text" onPress={() => router.push('/(main)/demo-garage')} />
    <AppText variant="caption" tone="secondary">Simulated vehicles and recorded Nissan Leaf telemetry are separate from your saved vehicles.</AppText>
  </AppScreen>;
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: spacing.sm },
  copy: { flex: 1, minWidth: 160, gap: spacing.xxs },
  placeholder: { width: 56, height: 56, borderRadius: radii.md, backgroundColor: colors.backgroundSecondary, alignItems: 'center', justifyContent: 'center' },
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs },
  add: { alignSelf: 'flex-start' },
});
