// Bounded observation chart using installed SVG; no invented time windows or predictions.
import { useState } from 'react';
import { View } from 'react-native';
import Svg, { Circle, Line, Polyline } from 'react-native-svg';
import { AppButton } from '@/components/ui/app-button';
import { AppText } from '@/components/ui/app-text';
import { colors } from '@/theme/tokens';
export interface ReadingPoint { row_id: number; timestamp_us: number; value: number | null; unusual?: boolean }
export function readingRuns(points: ReadingPoint[]) {
  const runs: ReadingPoint[][] = []; let previous: ReadingPoint | undefined;
  for (const p of points) {
    if (p.value === null) { previous = undefined; continue; }
    // A source gap over one second, skipped row, repeated/backward time breaks the line.
    if (!previous || p.timestamp_us <= previous.timestamp_us || p.timestamp_us - previous.timestamp_us > 1000000 || p.row_id !== previous.row_id + 1) runs.push([]);
    runs[runs.length - 1].push(p); previous = p;
  }
  return runs;
}
const stamp = (us: number) => new Date(us / 1000).toISOString();
export function LeafReadingChart({ title, unit, points, threshold }: { title: string; unit: string; points: ReadingPoint[]; threshold?: number }) {
  const [page, setPage] = useState(0), [selected, setSelected] = useState(0);
  const pages = Math.max(1, Math.ceil(points.length / 48)), current = Math.min(page, pages - 1), visible = points.slice(current * 48, current * 48 + 48);
  if (!visible.length) return <AppText>No {title} readings available.</AppText>;
  const values = visible.flatMap(p => p.value === null ? [] : [p.value]); if (threshold !== undefined) values.push(threshold);
  const low = Math.min(0, ...values), high = Math.max(0, ...values), scale = Math.max(Math.abs(low), Math.abs(high), Number.MIN_VALUE), span = high / scale - low / scale || 1;
  const y = (v: number) => 150 - (v / scale - low / scale) / span * 130;
  // Source row position intentionally preserves order when clocks repeat or jump backward.
  const x = (p: ReadingPoint) => 12 + visible.indexOf(p) / Math.max(1, visible.length - 1) * 336;
  const active = visible[Math.min(selected, visible.length - 1)];
  return <View testID={`${title} chart`}>
    <AppText variant="label">{title} · {unit}</AppText>
    <AppText variant="caption">{low.toPrecision(4)} to {high.toPrecision(4)} · source reading order · Page {current + 1}/{pages}</AppText>
    <Svg width="100%" height={170} viewBox="0 0 360 170" accessibilityLabel={`${title} observations; red marks unusual readings`}>
      {threshold !== undefined && <Line testID="leaf-threshold" x1={12} x2={348} y1={y(threshold)} y2={y(threshold)} stroke={colors.warning} strokeDasharray="5 4" />}
      {readingRuns(visible).map((run, i) => <Polyline key={i} points={run.map(p => `${x(p)},${y(p.value!)}`).join(' ')} fill="none" stroke={colors.accent} strokeWidth={2} />)}
      {visible.filter(p => p.value !== null).map(p => <Circle key={p.row_id} cx={x(p)} cy={y(p.value!)} r={p.row_id === active.row_id ? 5 : 3} fill={p.unusual ? colors.danger : colors.accent} onPress={() => setSelected(visible.indexOf(p))} />)}
    </Svg>
    <AppText>{stamp(active.timestamp_us)} · row {active.row_id} · {active.value === null ? 'Measurement unavailable' : `${active.value.toPrecision(5)} ${unit}`}{active.unusual ? ' · Unusual' : ''}</AppText>
    <AppText variant="caption">Blue: recorded value. Red: unusual reading. Dashed: model threshold where shown. Lines break at missing data, source gaps and clock discontinuities.</AppText>
    <AppButton title={`Previous ${title} reading`} variant="text" disabled={selected === 0} onPress={() => setSelected(Math.max(0, selected - 1))} />
    <AppButton title={`Next ${title} reading`} variant="text" disabled={selected >= visible.length - 1} onPress={() => setSelected(selected + 1)} />
    {pages > 1 && <><AppButton title={`Previous ${title} page`} variant="secondary" disabled={current === 0} onPress={() => { setPage(current - 1); setSelected(0); }} /><AppButton title={`Next ${title} page`} variant="secondary" disabled={current >= pages - 1} onPress={() => { setPage(current + 1); setSelected(0); }} /></>}
  </View>;
}
