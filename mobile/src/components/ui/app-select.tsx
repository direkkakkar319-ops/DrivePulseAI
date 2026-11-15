// Searchable native modal selector with virtualized options, keyboard handling and optional manual fallback.
import { useState } from 'react';
import { FlatList, Keyboard, KeyboardAvoidingView, Modal, Platform, Pressable, StyleSheet, View } from 'react-native';
import { SafeAreaProvider, SafeAreaView, initialWindowMetrics } from 'react-native-safe-area-context';
import { colors, layout, radii, spacing } from '@/theme/tokens';
import { AppButton } from './app-button';
import { AppDataState } from './app-data-state';
import { AppHeader } from './app-header';
import { AppIcon } from './app-icon';
import { AppText } from './app-text';
import { AppTextField } from './app-text-field';

export interface SelectOption { value: string; label: string }
export interface AppSelectProps {
  label: string;
  value: string | null;
  options: readonly SelectOption[];
  onSelect: (value: string) => void;
  onOpen?: () => void;
  onManual?: () => void;
  loading?: boolean;
  loadError?: string;
  onRetry?: () => void;
  error?: string;
  hint?: string;
  disabled?: boolean;
  searchable?: boolean;
}

export function AppSelect({ label, value, options, onSelect, onOpen, onManual, loading = false, loadError, onRetry,
  error, hint, disabled = false, searchable = true }: AppSelectProps) {
  const [open, setOpen] = useState(false), [search, setSearch] = useState(''), [focused, setFocused] = useState(false);
  const selected = options.find(option => option.value === value)?.label ?? value;
  const filtered = options.filter(option => option.label.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase()));
  function close() { Keyboard.dismiss(); setOpen(false); }
  return <View style={styles.field}>
    <AppText variant="label">{label}</AppText>
    <Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityHint={hint}
      accessibilityValue={{ text: selected || 'Not selected' }} accessibilityState={{ disabled, expanded: open }} disabled={disabled}
      onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}
      onPress={() => { Keyboard.dismiss(); setSearch(''); setOpen(true); onOpen?.(); }}
      style={[styles.trigger, { borderColor: error ? colors.danger : focused ? colors.focus : colors.borderStrong,
        backgroundColor: disabled ? colors.disabledBackground : colors.background }]}>
      <AppText tone={selected ? 'primary' : 'secondary'} style={styles.value}>{selected || `Select ${label.toLowerCase()}`}</AppText>
      <View style={{ transform: [{ rotate: '90deg' }] }}><AppIcon name="chevronRight" size={18} color={colors.textSecondary} /></View>
    </Pressable>
    {!!hint && <AppText variant="caption" tone="secondary">{hint}</AppText>}
    {!!error && <AppText accessibilityRole="alert" accessibilityLiveRegion="polite" variant="caption" tone="error">{error}</AppText>}
    {open && <Modal visible testID={`${label} options`} onRequestClose={close} animationType="none">
      <SafeAreaProvider initialMetrics={initialWindowMetrics}><SafeAreaView style={styles.modal} accessibilityViewIsModal onAccessibilityEscape={close}>
        <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
          <View style={styles.top}>
            <AppHeader title={`Select ${label.toLowerCase()}`} onBack={close} backLabel={`Close ${label.toLowerCase()} selection`} />
            {searchable && <AppTextField label={`Search ${label.toLowerCase()}`} value={search} onChangeText={setSearch}
              autoCorrect={false} autoCapitalize="none" />}
          </View>
          {loading ? <AppDataState status="loading" title={`Loading ${label.toLowerCase()} options`} />
            : loadError ? <AppDataState status="error" title="Catalog unavailable" message={loadError} onRetry={onRetry} /> : null}
          <FlatList data={loading || loadError ? [] : filtered} keyExtractor={item => item.value}
            keyboardShouldPersistTaps="handled" initialNumToRender={20} contentContainerStyle={styles.list}
            ListEmptyComponent={!loading && !loadError ? <AppDataState status="empty" title="No matching options"
              message={onManual ? 'Try another search or choose Other / Not Listed.' : 'Try another search.'} /> : null}
            renderItem={({ item }) => <AppButton title={item.label} variant={value === item.value ? 'primary' : 'secondary'}
              accessibilityState={{ selected: value === item.value }} onPress={() => { close(); onSelect(item.value); }} />} />
          {onManual && <View style={styles.footer}><AppButton title="Other / Not Listed" variant="secondary"
            onPress={() => { close(); onManual(); }} /></View>}
        </KeyboardAvoidingView>
      </SafeAreaView></SafeAreaProvider>
    </Modal>}
  </View>;
}

const styles = StyleSheet.create({
  field: { gap: spacing.xs },
  trigger: { minHeight: layout.minimumTouchTarget, borderWidth: 1, borderRadius: radii.md, padding: spacing.sm,
    flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  value: { flex: 1 },
  modal: { flex: 1, backgroundColor: colors.background }, flex: { flex: 1 },
  top: { padding: spacing.lg, gap: spacing.md }, list: { paddingHorizontal: spacing.lg, gap: spacing.xs },
  footer: { padding: spacing.lg, borderTopWidth: 1, borderColor: colors.border },
});
