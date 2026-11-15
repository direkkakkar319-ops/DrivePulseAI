// Small shared demo form; catalog filtering never changes account persistence or silently rewrites saved data.
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { useVehicleSetup } from '@/hooks/use-vehicle-setup';
import { fuelOptionsFor, powertrainOptions, vehicleTextLimits, vehicleYearBounds } from '@/lib/vehicle-setup';
import { demoVehicleCatalog, demoManufacturer, demoModel, originalModel, validateDemoVehicle } from '@/config/demo-vehicle-catalog';
import type { VehicleSetupDraft, VehicleSetupValue } from '@/types/vehicle-setup';
import { spacing } from '@/theme/tokens';
import { AppButton } from './ui/app-button';
import { AppCard } from './ui/app-card';
import { AppStatus } from './ui/app-status';
import { AppText } from './ui/app-text';
import { AppTextField } from './ui/app-text-field';
import { AppSelect } from './ui/app-select';

export interface VehicleSetupFormProps {
  onSubmit: (value: VehicleSetupValue) => void | Promise<void>;
  /** Initial values remain intact even if not covered by the demo catalog. */
  initialValues?: VehicleSetupDraft;
  submitLabel?: string;
  onRetry?: () => void | Promise<void>;
}

export function VehicleSetupForm({ onSubmit, initialValues, submitLabel = 'Continue', onRetry }: VehicleSetupFormProps) {
  const [manualManufacturer, setManualManufacturer] = useState(false), [manualModel, setManualModel] = useState(false);
  const manual = manualManufacturer || manualModel;
  const { draft, errors, submitting, submitError, setField, selectPowertrain, selectFuel, submit } = useVehicleSetup(onSubmit, initialValues,
    value => validateDemoVehicle(value, initialValues, manual));
  const bounds = vehicleYearBounds();
  const model = manual ? undefined : demoModel(draft.manufacturer, draft.model);
  const retained = originalModel(draft, initialValues);
  const years = model?.years ?? Array.from({ length: bounds.max - bounds.min + 1 }, (_, index) => bounds.max - index);
  const types = powertrainOptions.filter(option => !model?.configurations
    || model.configurations.some(item => item.powertrain === option.value) || (retained && initialValues?.powertrain === option.value))
    .map(option => ({ value: option.value, label: option.value === 'ice' ? 'Combustion engine (ICE)' : option.label }));
  const fuels = fuelOptionsFor(draft.powertrain).filter(option => !model?.configurations
    || model.configurations.some(item => item.powertrain === draft.powertrain && item.fuels.includes(option.value))
    || (retained && initialValues?.powertrain === draft.powertrain && initialValues?.fuelType === option.value));

  function manufacturerChanged(value: string) {
    if (value !== draft.manufacturer) setManualModel(false);
    setField('manufacturer', value);
  }
  function modelChanged(value: string) {
    setField('model', value);
    const next = manual ? undefined : demoModel(draft.manufacturer, value);
    if (value !== draft.model && next?.configurations && draft.powertrain) {
      const configurations = next.configurations.filter(item => item.powertrain === draft.powertrain);
      if (!configurations.length) selectPowertrain(null);
      else if (!configurations.some(item => item.fuels.includes(draft.fuelType))) selectFuel(null);
    }
  }

  return <View style={styles.form}>
    {manualManufacturer ? <View style={styles.group}>
      <AppTextField label="Manufacturer" value={draft.manufacturer} onChangeText={manufacturerChanged} error={errors.manufacturer}
        editable={!submitting} maxLength={vehicleTextLimits.manufacturer} autoCapitalize="words" autoCorrect={false} />
      <AppButton title="Choose manufacturer from catalog" variant="text" disabled={submitting} onPress={() => setManualManufacturer(false)} />
    </View> : <AppSelect label="Manufacturer" value={draft.manufacturer}
      options={demoVehicleCatalog.map(make => ({ value: make.name, label: make.name }))} onSelect={manufacturerChanged}
      onManual={() => setManualManufacturer(true)} error={errors.manufacturer} disabled={submitting}
      hint="Small demo catalog. Other / Not Listed supports your own vehicle." />}
    {manualModel ? <View style={styles.group}>
      <AppTextField label="Model" value={draft.model} onChangeText={value => setField('model', value)} error={errors.model}
        editable={!submitting} maxLength={vehicleTextLimits.model} autoCorrect={false} />
      <AppButton title="Choose model from catalog" variant="text" disabled={submitting} onPress={() => setManualModel(false)} />
    </View> : <AppSelect label="Model" value={draft.model}
      options={(demoManufacturer(draft.manufacturer)?.models ?? []).map(item => ({ value: item.name, label: item.name }))}
      onSelect={modelChanged} onManual={() => setManualModel(true)} error={errors.model}
      disabled={submitting || !draft.manufacturer.trim()} />}
    <AppSelect label="Model year" value={draft.year} options={years.map(year => ({ value: String(year), label: String(year) }))}
      hint={model ? `${model.coverage}. Other years: use manual model entry. Saved values are preserved.` : 'Choose your vehicle’s actual year. Manual-entry years are not catalog-verified.'}
      onSelect={value => setField('year', value)} error={errors.year} disabled={submitting || !draft.manufacturer.trim() || !draft.model.trim()} />
    <AppSelect label="Engine / Vehicle Type" value={draft.powertrain} options={types} disabled={submitting}
      hint={model?.configurations ? 'Select your vehicle’s configuration. Nothing is selected automatically.' : 'General choices; confirm the actual type of your vehicle.'}
      onSelect={value => { const type = powertrainOptions.find(option => option.value === value); if (type) selectPowertrain(type.value); }} error={errors.powertrain} />
    {draft.powertrain === 'ev' ? <AppCard variant="filled"><AppText variant="label">Fully electric</AppText>
      <AppText tone="secondary">No combustion fuel selection needed.</AppText></AppCard>
      : draft.powertrain && <AppSelect key={draft.powertrain} label="Fuel type" options={fuels} value={draft.fuelType}
        onSelect={value => { const fuel = fuels.find(option => option.value === value); if (fuel) selectFuel(fuel.value); }}
        disabled={submitting} error={errors.fuelType} searchable={false} />}
    <AppTextField label="Vehicle nickname" hint="Optional" placeholder="My Car" value={draft.nickname}
      onChangeText={value => setField('nickname', value)} error={errors.nickname} editable={!submitting}
      maxLength={vehicleTextLimits.nickname} autoCapitalize="words" />
    {!!submitError && <>
      <AppStatus label={submitError} tone="error" variant="notice" />
      <AppButton title="Retry" variant="secondary" disabled={submitting} onPress={onRetry ?? submit} />
    </>}
    <AppButton title={submitLabel} onPress={submit} loading={submitting} />
  </View>;
}

const styles = StyleSheet.create({ form: { gap: spacing.lg }, group: { gap: spacing.sm } });
