// Light reusable vehicle metadata form; callers own routing and future persistence.
import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { useVehicleSetup } from '@/hooks/use-vehicle-setup';
import { fuelOptionsFor, powertrainOptions, vehicleTextLimits, vehicleYearBounds } from '@/lib/vehicle-setup';
import type { VehicleSetupDraft, VehicleSetupValue } from '@/types/vehicle-setup';
import { colors, layout, radii, spacing } from '@/theme/tokens';
import { AppButton } from './ui/app-button';
import { AppCard } from './ui/app-card';
import { AppStatus } from './ui/app-status';
import { AppText } from './ui/app-text';
import { AppTextField } from './ui/app-text-field';

export interface VehicleSetupFormProps {
  onSubmit: (value: VehicleSetupValue) => void | Promise<void>;
  /** Initial draft is applied on mount; remount when editing another vehicle. */
  initialValues?: VehicleSetupDraft;
  submitLabel?: string;
}

export function VehicleSetupForm({ onSubmit, initialValues, submitLabel = 'Continue' }: VehicleSetupFormProps) {
  const { draft, errors, submitting, submitError, setField, selectPowertrain, selectFuel, submit } = useVehicleSetup(onSubmit, initialValues);
  const bounds = vehicleYearBounds();
  return <View style={styles.form}>
    <ChoiceGroup title="Powertrain" options={powertrainOptions} selected={draft.powertrain}
      onSelect={selectPowertrain} disabled={submitting} error={errors.powertrain} />
    <AppTextField label="Manufacturer" hint="Enter any manufacturer." value={draft.manufacturer}
      onChangeText={value => setField('manufacturer', value)} error={errors.manufacturer} editable={!submitting}
      maxLength={vehicleTextLimits.manufacturer} autoCapitalize="words" autoCorrect={false} />
    <AppTextField label="Model" value={draft.model} onChangeText={value => setField('model', value)}
      error={errors.model} editable={!submitting} maxLength={vehicleTextLimits.model} autoCorrect={false} />
    <AppTextField label="Model year" hint={`Manufacturing or model year · ${bounds.min}–${bounds.max}`} value={draft.year}
      onChangeText={value => setField('year', value)} error={errors.year} editable={!submitting}
      keyboardType="number-pad" maxLength={4} />
    {draft.powertrain === 'ev'
      ? <AppCard variant="filled"><AppText variant="label">Fully electric</AppText><AppText tone="secondary">No combustion fuel selection needed.</AppText></AppCard>
      : draft.powertrain && <ChoiceGroup title="Fuel type" options={fuelOptionsFor(draft.powertrain)} selected={draft.fuelType}
          onSelect={selectFuel} disabled={submitting} error={errors.fuelType} />}
    <AppTextField label="Vehicle nickname" hint="Optional" placeholder="My Car" value={draft.nickname}
      onChangeText={value => setField('nickname', value)} error={errors.nickname} editable={!submitting}
      maxLength={vehicleTextLimits.nickname} autoCapitalize="words" />
    {!!submitError && <AppStatus label={submitError} tone="error" variant="notice" />}
    <AppButton title={submitLabel} onPress={submit} loading={submitting} />
  </View>;
}

interface Choice<T extends string> { value: T; label: string; description?: string }
function ChoiceGroup<T extends string>({ title, options, selected, onSelect, disabled, error }: {
  title: string; options: readonly Choice<T>[]; selected: T | null; onSelect: (value: T) => void; disabled: boolean; error?: string;
}) {
  return <View style={styles.group}>
    <AppText variant="subtitle">{title}</AppText>
    <View accessibilityRole="radiogroup" accessibilityLabel={title} style={styles.group}>
      {options.map(option => <ChoiceCard key={option.value} option={option} checked={selected === option.value}
        onPress={() => onSelect(option.value)} disabled={disabled} />)}
    </View>
    {!!error && <AppText tone="error" variant="caption" accessibilityRole="alert" accessibilityLiveRegion="polite">{error}</AppText>}
  </View>;
}

function ChoiceCard<T extends string>({ option, checked, onPress, disabled }: {
  option: Choice<T>; checked: boolean; onPress: () => void; disabled: boolean;
}) {
  const [focused, setFocused] = useState(false);
  return <Pressable accessibilityRole="radio" accessibilityLabel={option.label} accessibilityHint={option.description}
    accessibilityState={{ checked, disabled }} disabled={disabled} onPress={onPress}
    onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}
    style={({ pressed }) => [styles.choice, {
      backgroundColor: disabled ? colors.disabledBackground : checked || pressed ? colors.accentSoft : colors.background,
      borderColor: checked ? colors.accent : colors.borderStrong,
    }, focused && !disabled && { outlineColor: colors.focus, outlineWidth: 2, outlineOffset: 2 }]}>
    <View style={[styles.radio, { borderColor: checked ? colors.accent : colors.borderStrong }]}>
      {checked && <View style={styles.dot} />}
    </View>
    <View style={styles.choiceCopy}>
      <AppText variant="label" tone={disabled ? 'secondary' : 'primary'}>{option.label}</AppText>
      {!!option.description && <AppText variant="caption" tone="secondary">{option.description}</AppText>}
    </View>
  </Pressable>;
}

const styles = StyleSheet.create({
  form: { gap: spacing.xl },
  group: { gap: spacing.sm },
  choice: { minHeight: layout.minimumTouchTarget, borderWidth: 1, borderRadius: radii.md, padding: spacing.md,
    flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  choiceCopy: { flex: 1, gap: spacing.xxs },
  radio: { width: 22, height: 22, borderWidth: 2, borderRadius: radii.pill, alignItems: 'center', justifyContent: 'center' },
  dot: { width: 10, height: 10, borderRadius: radii.pill, backgroundColor: colors.accent },
});
