// Saved-vehicle presentation and accessible inline selection; persistence belongs to the caller.
import { StyleSheet, View } from 'react-native';
import type { SavedVehicle } from '@/api/onboarding';
import { fuelOptionsFor, powertrainOptions } from '@/lib/vehicle-setup';
import { colors, radii, spacing } from '@/theme/tokens';
import { AppButton } from '@/components/ui/app-button';
import { AppCard } from '@/components/ui/app-card';
import { AppIcon } from '@/components/ui/app-icon';
import { AppText } from '@/components/ui/app-text';

export interface ActiveVehicleCardProps {
  vehicles: readonly SavedVehicle[];
  activeId: string | null;
  expanded: boolean;
  saving: boolean;
  onToggle: () => void;
  onSelect: (id: string) => void;
}

export function savedVehicleName(vehicle: SavedVehicle) {
  return vehicle.nickname?.trim() || `${vehicle.manufacturer} ${vehicle.model}`;
}

export function ActiveVehicleCard({ vehicles, activeId, expanded, saving, onToggle, onSelect }: ActiveVehicleCardProps) {
  const active = vehicles.find(vehicle => vehicle.id === activeId);
  const fuel = active && fuelOptionsFor(active.powertrain).find(option => option.value === active.fuel_type)?.label;
  return <AppCard>
    <View style={styles.summary}>
      <View style={styles.placeholder}><AppIcon name="car" size={32} color={colors.textSecondary} /></View>
      <View style={styles.copy}>
        <AppText variant="subtitle">{active ? savedVehicleName(active) : 'Choose an active vehicle'}</AppText>
        {active && <>
          <AppText tone="secondary">{active.manufacturer} · {active.model} · {active.year}</AppText>
          <AppText tone="secondary">{powertrainOptions.find(option => option.value === active.powertrain)?.label}</AppText>
          {!!fuel && <AppText tone="secondary">Fuel: {fuel}</AppText>}
        </>}
      </View>
    </View>
    <AppText variant="caption" tone="secondary">Saved to your account. No connected vehicle data.</AppText>
    {(vehicles.length > 1 || !active) && <AppButton title={saving ? 'Saving active vehicle…' : expanded ? 'Close vehicle selection' : 'Choose vehicle'}
      variant="secondary" icon="car" loading={saving} onPress={onToggle} accessibilityState={{ expanded }} />}
    {expanded && <View style={styles.options}>
      <AppText variant="label">Choose a saved vehicle</AppText>
      {vehicles.map(vehicle => <AppButton key={vehicle.id} title={savedVehicleName(vehicle)}
        accessibilityLabel={`Select ${savedVehicleName(vehicle)}, ${vehicle.year}`}
        accessibilityState={{ selected: vehicle.id === activeId }}
        icon={vehicle.id === activeId ? 'check' : 'car'} variant={vehicle.id === activeId ? 'primary' : 'secondary'}
        disabled={saving} onPress={() => onSelect(vehicle.id)} />)}
    </View>}
  </AppCard>;
}

const styles = StyleSheet.create({
  summary: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: spacing.md },
  placeholder: { width: 64, height: 64, borderRadius: radii.md, backgroundColor: colors.backgroundSecondary,
    alignItems: 'center', justifyContent: 'center' },
  copy: { flex: 1, minWidth: 160, gap: spacing.xxs },
  options: { gap: spacing.xs },
});
