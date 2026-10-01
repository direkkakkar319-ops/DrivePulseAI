// Shared accessible presentation primitives for the vehicle-health experience.
import type { PropsWithChildren } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
  type TextStyle,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import Svg, { Path } from 'react-native-svg';
import { colors as c } from '@/theme/colors';
export function Icon({
  name = 'pulse',
  size = 22,
  color = c.primary,
}: {
  name?: string;
  size?: number;
  color?: string;
}) {
  const paths: Record<string, string> = {
    pulse: 'M2 12h5l3-8 4 16 3-8h5',
    home: 'M3 10l9-7 9 7M5 9v12h5v-7h4v7h5V9',
    car: 'M3 11l2-6h14l2 6M3 11h18v8H3zM6 19v2m12-2v2M6 14h2m8 0h2',
    account: 'M4 22v-3c0-6 16-6 16 0v3M8 6a4 4 0 1 0 8 0 4 4 0 1 0-8 0',
    back: 'M20 12H4m6-6-6 6 6 6',
    arrow: 'm9 5 7 7-7 7',
    plus: 'M12 4v16M4 12h16',
    temperature: 'M9 14V5a3 3 0 0 1 6 0v9a5 5 0 1 1-6 0M12 8v10',
    battery: 'M9 3h6M4 6h16v15H4zM7 11h4m-2-2v4m5-2h3',
    gauge: 'M4 19a10 10 0 1 1 16 0M12 14l5-7M7 19h10',
    warning: 'M12 3 2 21h20L12 3M12 9v5m0 3v1',
    settings: 'M5 6h14M5 12h14M5 18h14M8 3v6m8 0v6m-6 0v6',
  };
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" accessible={false}>
      <Path
        d={paths[name] ?? paths.pulse}
        stroke={color}
        strokeWidth={1.6}
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
    </Svg>
  );
}
export function Brand({ large = false }: { large?: boolean }) {
  return (
    <View style={{ alignItems: 'center', gap: 12, flexDirection: large ? 'column' : 'row' }}>
      <View style={styles.brand}>
        <Icon size={large ? 40 : 23} />
      </View>
      <Text style={[styles.title, large && { fontSize: 32 }]}>
        DrivePulse<Text style={{ color: c.primary }}> AI</Text>
      </Text>
    </View>
  );
}
export function Copy({
  children,
  muted = false,
  style,
}: PropsWithChildren<{ muted?: boolean; style?: TextStyle }>) {
  return <Text style={[styles.copy, muted && { color: c.textMuted }, style]}>{children}</Text>;
}
export function Page({
  children,
  title,
  back,
  action,
}: PropsWithChildren<{ title?: string; back?: () => void; action?: React.ReactNode }>) {
  return (
    <SafeAreaView style={styles.safe} edges={['top', 'left', 'right']}>
      <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={styles.page}>
        {title && (
          <View style={styles.row}>
            {back && (
              <Pressable
                onPress={back}
                accessibilityLabel="Back"
                accessibilityRole="button"
                style={styles.touch}
              >
                <Icon name="back" color={c.textMuted} />
              </Pressable>
            )}
            <Text style={[styles.title, { flex: 1 }]}>{title}</Text>
            {action}
          </View>
        )}
        {children}
      </ScrollView>
    </SafeAreaView>
  );
}
export function Card({ children }: PropsWithChildren) {
  return (
    <LinearGradient colors={[c.cardRaised, c.card]} style={styles.card}>
      {children}
    </LinearGradient>
  );
}
export function Section({
  title,
  action,
  onPress,
}: {
  title: string;
  action?: string;
  onPress?: () => void;
}) {
  return (
    <View style={styles.row}>
      <Text style={[styles.title, { flex: 1, fontSize: 17 }]}>{title}</Text>
      {action && (
        <Pressable onPress={onPress} accessibilityRole="button" style={styles.touch}>
          <Copy style={{ color: c.primary, fontSize: 13 }}>{action}</Copy>
        </Pressable>
      )}
    </View>
  );
}
export function Button({
  title,
  onPress,
  secondary = false,
  disabled = false,
}: {
  title: string;
  onPress: () => void;
  secondary?: boolean;
  disabled?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled }}
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => ({ opacity: disabled || pressed ? 0.55 : 1 })}
    >
      <LinearGradient
        colors={secondary ? [c.card, c.card] : [c.primaryDeep, c.primary]}
        style={[styles.button, secondary && { borderWidth: 1, borderColor: c.border }]}
      >
        <Text style={{ color: secondary ? c.text : c.background, fontWeight: '700', fontSize: 15 }}>
          {title}
        </Text>
      </LinearGradient>
    </Pressable>
  );
}
export function Badge({ label, warning = false }: { label: string; warning?: boolean }) {
  return (
    <View style={[styles.badge, warning && { backgroundColor: '#412c19' }]}>
      <Text style={{ color: warning ? c.warning : c.primary, fontSize: 11, fontWeight: '700' }}>
        {label}
      </Text>
    </View>
  );
}
export function State({
  title,
  message,
  loading = false,
  retry,
}: {
  title: string;
  message?: string;
  loading?: boolean;
  retry?: () => void;
}) {
  return (
    <Card>
      {loading && <ActivityIndicator color={c.primary} accessibilityLabel={title} />}
      <Copy style={{ fontWeight: '700' }}>{title}</Copy>
      {message && <Copy muted>{message}</Copy>}
      {retry && <Button title="Try again" secondary onPress={retry} />}
    </Card>
  );
}
export function Chips<T extends string>({
  values,
  selected,
  onSelect,
}: {
  values: { id: T; label: string }[];
  selected: T;
  onSelect: (id: T) => void;
}) {
  return (
    <View style={styles.wrap}>
      {values.map((v) => (
        <Pressable
          key={v.id}
          onPress={() => onSelect(v.id)}
          accessibilityRole="button"
          accessibilityState={{ selected: selected === v.id }}
          style={[styles.chip, selected === v.id && { backgroundColor: c.primary }]}
        >
          <Text style={{ color: selected === v.id ? c.background : c.textMuted, fontSize: 13 }}>
            {v.label}
          </Text>
        </Pressable>
      ))}
    </View>
  );
}
export function Avatar({ name }: { name: string }) {
  return (
    <View style={styles.avatar}>
      <Copy style={{ color: c.primary, fontWeight: '700', fontSize: 23 }}>
        {name.trim().slice(0, 1).toUpperCase() || 'D'}
      </Copy>
    </View>
  );
}
export const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: c.background },
  page: {
    padding: 20,
    gap: 16,
    paddingBottom: 40,
    width: '100%',
    maxWidth: 650,
    alignSelf: 'center',
    flexGrow: 1,
  },
  copy: { color: c.text, fontSize: 14, lineHeight: 21 },
  title: { color: c.text, fontSize: 20, fontWeight: '600' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  wrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  card: {
    borderRadius: 17,
    borderWidth: 1,
    borderColor: c.border,
    padding: 16,
    gap: 12,
    overflow: 'hidden',
  },
  button: {
    minHeight: 50,
    padding: 14,
    borderRadius: 26,
    justifyContent: 'center',
    alignItems: 'center',
  },
  badge: {
    backgroundColor: '#08343c',
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 5,
    alignSelf: 'flex-start',
  },
  touch: { minWidth: 44, minHeight: 44, alignItems: 'center', justifyContent: 'center' },
  chip: {
    minHeight: 44,
    paddingHorizontal: 16,
    justifyContent: 'center',
    borderRadius: 22,
    backgroundColor: c.cardRaised,
  },
  brand: {
    borderColor: c.primary,
    borderWidth: 1,
    backgroundColor: '#003139',
    padding: 8,
    borderRadius: 13,
  },
  avatar: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: c.cardRaised,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
