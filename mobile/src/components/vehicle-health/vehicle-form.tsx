// Prototype vehicle metadata form; no external lookup or telemetry inference.
import { useState } from 'react';
import { useRouter } from 'expo-router';
import { useVehicles } from '@/store/vehicleDataStore';
import type { Vehicle, VehicleDraft } from '@/types/vehicle-health';
import { AuthInput, AuthMessage } from '@/components/auth-form';
import { Button, Copy, Page } from './ui';
export function VehicleForm({ vehicle }: { vehicle?: Vehicle }) {
  const [draft, setDraft] = useState<VehicleDraft>(
    vehicle ?? { name: '', make: '', model: '', year: '', notes: '' },
  );
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const { saveVehicle } = useVehicles();
  const router = useRouter();
  async function save() {
    setBusy(true);
    setError('');
    try {
      const saved = await saveVehicle(draft, vehicle?.id);
      router.replace({ pathname: '/(main)/vehicle/[id]', params: { id: saved.id } });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save vehicle.');
    } finally {
      setBusy(false);
    }
  }
  return (
    <Page title={vehicle ? 'Manage vehicle' : 'Add vehicle'} back={() => router.back()}>
      <Copy muted>
        Demo garage · saved for this session only. Make and model do not determine sensor readings.
      </Copy>
      {(
        [
          { key: 'name', label: 'Vehicle name', max: 60 },
          { key: 'make', label: 'Make (optional)', max: 60 },
          { key: 'model', label: 'Model (optional)', max: 60 },
          { key: 'year', label: 'Year (optional)', max: 4 },
          { key: 'notes', label: 'Notes (optional)', max: 300 },
        ] as const
      ).map((field) => (
        <AuthInput
          key={field.key}
          label={field.label}
          value={draft[field.key]}
          onChangeText={(value) => setDraft((d) => ({ ...d, [field.key]: value }))}
          keyboardType={field.key === 'year' ? 'number-pad' : 'default'}
          maxLength={field.max}
          editable={!busy}
        />
      ))}
      <AuthMessage message={error} error />
      <Button
        title={busy ? 'Saving…' : 'Save demo vehicle'}
        disabled={busy}
        onPress={() => void save()}
      />
      {!vehicle && (
        <Copy muted>
          New vehicles begin without readings. Select demo playback from Account → Prototype
          controls after saving.
        </Copy>
      )}
    </Page>
  );
}
