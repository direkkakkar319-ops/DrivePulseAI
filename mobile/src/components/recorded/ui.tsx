// Restrained, accessible presentation primitives scoped to recorded battery telemetry.
import type { PropsWithChildren } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
  useWindowDimensions,
  type TextStyle,
  type ViewStyle,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Icon } from '@/components/vehicle-health/ui';
import { useReplay } from '@/store/recordedReplayStore';
import { activeInterval, measurement, recordedTime } from '@/lib/recorded-replay';
import type { ReplayClip, TelemetrySample } from '@/types/recorded-telemetry';
import { colors, minimumTouchTarget, radius, spacing, type } from './theme';

export const palette = {
  background: colors.canvas,
  surface: colors.surface,
  ink: colors.text,
  muted: colors.textSecondary,
  line: colors.border,
  accent: colors.accent,
  tint: colors.accentSoft,
};
export const ui = StyleSheet.create({
  page: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    gap: spacing.lg,
    width: '100%',
    maxWidth: 720,
    alignSelf: 'center',
    flexGrow: 1,
    paddingBottom: spacing.xxl,
  },
  row: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: spacing.sm },
  text: { color: colors.text, ...type.body },
  title: { color: colors.text, ...type.title, flexShrink: 1 },
  panel: {
    backgroundColor: colors.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.md,
    gap: spacing.sm,
  },
  button: {
    minHeight: minimumTouchTarget,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.accent,
    justifyContent: 'center',
    alignItems: 'center',
  },
  divider: { height: StyleSheet.hairlineWidth, backgroundColor: colors.border },
});
export function Copy({ children, muted = false, style }: PropsWithChildren<{ muted?: boolean; style?: TextStyle }>) {
  return <Text style={[ui.text, muted && { color: palette.muted }, style]}>{children}</Text>;
}
export function Button({ title, onPress, secondary = false, disabled = false, selected, style }: { title: string; onPress: () => void; secondary?: boolean; disabled?: boolean; selected?: boolean; style?: ViewStyle }) {
  return <Pressable accessibilityRole="button" accessibilityState={{ disabled, selected }} disabled={disabled} onPress={onPress}
    style={({ pressed }) => [ui.button, style, {
      backgroundColor: secondary ? colors.surface : pressed ? colors.accentPressed : colors.accent,
      borderColor: disabled ? colors.borderStrong : colors.accent,
      opacity: disabled ? 0.45 : pressed ? 0.82 : 1,
    }]}>
    <Text style={{ color: secondary ? colors.accent : colors.white, ...type.label, textAlign: 'center' }}>{title}</Text>
  </Pressable>;
}
export function Page({ title, children, back = false, accountAction = true }: PropsWithChildren<{ title: string; back?: boolean; accountAction?: boolean }>) {
  const router = useRouter();
  return <SafeAreaView style={{ flex: 1, backgroundColor: colors.canvas }} edges={['top', 'left', 'right']}>
    <ScrollView contentContainerStyle={ui.page} keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>
      <View style={[ui.row, { minHeight: minimumTouchTarget, justifyContent: 'space-between' }]}>
        <View style={[ui.row, { gap: spacing.xs, flex: 1 }]}>
          {back && <Pressable accessibilityLabel="Go back" accessibilityRole="button" onPress={() => router.canGoBack() ? router.back() : router.replace('/(main)/(tabs)/home')} style={styles.iconButton}>
            <Icon name="back" color={colors.accent} />
          </Pressable>}
          <Copy muted style={{ ...type.label, letterSpacing: 0.3 }}>DRIVEPULSE AI</Copy>
        </View>
        {accountAction && <Pressable accessibilityLabel="Account" accessibilityHint="Open account settings" accessibilityRole="button" onPress={() => router.push('/(main)/account')} style={styles.iconButton}>
          <Icon name="account" color={colors.accent} />
        </Pressable>}
      </View>
      <Text accessibilityRole="header" style={ui.title}>{title}</Text>
      {children}
    </ScrollView>
  </SafeAreaView>;
}
export function Panel({ children, style, accessibilityLabel }: PropsWithChildren<{ style?: ViewStyle; accessibilityLabel?: string }>) {
  return <View style={[ui.panel, style]} accessible={!!accessibilityLabel} accessibilityLabel={accessibilityLabel}>{children}</View>;
}
export function SectionHeader({ eyebrow, title, detail }: { eyebrow?: string; title: string; detail?: string }) {
  return <View style={{ gap: spacing.xxs }}>
    {eyebrow && <Copy style={styles.eyebrow}>{eyebrow.toUpperCase()}</Copy>}
    <Copy style={type.section}>{title}</Copy>
    {detail && <Copy muted>{detail}</Copy>}
  </View>;
}
export function StatusPill({ label, unusual = false }: { label: string; unusual?: boolean }) {
  return <View style={[styles.statusPill, unusual && styles.unusualPill]} accessibilityLabel={label}>
    <View style={[styles.statusDot, unusual && { backgroundColor: colors.unusual }]} />
    <Text style={[styles.statusText, unusual && { color: colors.unusual }]}>{label}</Text>
  </View>;
}
export function DataGate({ children }: { children: (clip: ReplayClip, sample: TelemetrySample) => React.ReactNode }) {
  const { resource, catalog, sample, selectClip, selectedId, reload } = useReplay();
  if (catalog.status === 'error' || resource.status === 'error') return <Panel><Copy>Recording unavailable</Copy><Copy muted>{catalog.status === 'error' ? catalog.message : resource.status === 'error' ? resource.message : ''}</Copy><Button title="Try again" onPress={() => { void (catalog.status === 'error' ? reload() : selectClip(selectedId)); }} /></Panel>;
  if (catalog.status === 'loading' || resource.status === 'loading') return <Panel><ActivityIndicator color={palette.accent} accessibilityLabel="Loading recorded telemetry" /><Copy>Loading recorded telemetry…</Copy></Panel>;
  if (resource.status !== 'ready' || !sample) return <Panel><Copy>No recorded measurements available</Copy><Copy muted>The data provider has no samples to replay.</Copy></Panel>;
  return <>{children(resource.data, sample)}</>;
}
export function Recording({ clip, sample }: { clip: ReplayClip; sample?: TelemetrySample }) {
  return <View style={styles.recordingHeader}>
    <View style={[ui.row, { justifyContent: 'space-between' }]}>
      <StatusPill label="Recorded data" />
      <Copy muted style={type.caption}>TRIP {clip.trip_id}</Copy>
    </View>
    <Copy style={styles.vehicleName}>{clip.vehicle.description}</Copy>
    <Copy muted>{clip.title} · {recordedTime(sample?.original_timestamp_utc ?? clip.recorded_start_utc)}</Copy>
  </View>;
}
export function Measurements({ sample }: { sample: TelemetrySample }) {
  const { width, fontScale } = useWindowDimensions();
  const stacked = width < 360 || fontScale > 1.3;
  const items = [
    ['Battery SOC', sample.soc_percent, '%'],
    ['High-voltage battery', sample.voltage_v, 'V'],
    ['Pack 1 temperature', sample.temperature_c, '°C'],
  ] as const;
  return <View style={[styles.metricGrid, stacked && { flexDirection: 'column' }]}>
    {items.map(([label, value, unit]) => <View key={label} style={[styles.metric, stacked && { width: '100%' }]} accessible accessibilityLabel={`${label}: ${measurement(value, unit)}`}>
      <Copy muted style={type.caption}>{label}</Copy>
      <Copy style={styles.metricValue}>{measurement(value, unit)}</Copy>
    </View>)}
  </View>;
}
export function Score({ clip, sample }: { clip: ReplayClip; sample: TelemetrySample }) {
  const persistent = activeInterval(clip, sample);
  const unusual = sample.unusual === true;
  const label = sample.unusual === null ? 'Score unavailable' : unusual ? 'Statistically unusual pattern' : 'Statistically typical telemetry';
  return <Panel style={unusual ? styles.unusualPanel : undefined} accessibilityLabel={`${label}. Saved anomaly score ${measurement(sample.score_samples, '', 6)}`}>
    <View style={[ui.row, { justifyContent: 'space-between' }]}>
      <StatusPill label={label} unusual={unusual} />
      <Copy style={styles.score}>{measurement(sample.score_samples, '', 6)}</Copy>
    </View>
    <Copy muted style={type.caption}>Saved anomaly score · frozen threshold {clip.threshold}</Copy>
    <Copy muted>Lower scores mean a more unusual statistical combination. This is not a fault probability or mechanical diagnosis.</Copy>
    {persistent && <Copy style={{ color: colors.unusual, fontWeight: '600' }}>Persistent interval · {measurement(persistent.duration_seconds, 's', 3)}</Copy>}
  </Panel>;
}

const styles = StyleSheet.create({
  iconButton: { minWidth: minimumTouchTarget, minHeight: minimumTouchTarget, alignItems: 'center', justifyContent: 'center', borderRadius: radius.pill },
  eyebrow: { color: colors.accent, ...type.caption, fontWeight: '700', letterSpacing: 0.8 },
  statusPill: { minHeight: 28, paddingHorizontal: spacing.sm, borderRadius: radius.pill, backgroundColor: colors.accentSoft, flexDirection: 'row', alignItems: 'center', gap: spacing.xs, alignSelf: 'flex-start' },
  unusualPill: { backgroundColor: colors.unusualSoft },
  statusDot: { width: 7, height: 7, borderRadius: 4, backgroundColor: colors.typical },
  statusText: { color: colors.typical, ...type.caption, fontWeight: '700' },
  recordingHeader: { gap: spacing.xs, paddingBottom: spacing.xs },
  vehicleName: { fontSize: 21, lineHeight: 28, fontWeight: '600' },
  metricGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  metric: { width: '47%', minWidth: 144, flexGrow: 1, backgroundColor: colors.surface, borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border, borderRadius: radius.md, padding: spacing.md, gap: spacing.xs },
  metricValue: { ...type.metric, fontVariant: ['tabular-nums'] },
  unusualPanel: { borderColor: colors.unusual, backgroundColor: '#FFFCF8' },
  score: { fontSize: 19, lineHeight: 25, fontWeight: '600', fontVariant: ['tabular-nums'] },
});
