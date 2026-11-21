import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import Svg, { Circle, Line, Polyline, Rect } from 'react-native-svg';
import { AppButton } from '@/components/ui/app-button';
import { AppText } from '@/components/ui/app-text';
import { CHART_PAGE_SIZE, clock, lineRuns, plotNumber, type PlotPoint } from '@/lib/kit-visualization';
import { colors, spacing } from '@/theme/tokens';

// Two bounded SVG plots, no gesture engine, interpolation or derived predictions.
export function KitLineChart({ title, unit, points, threshold, onInspect }: {
  title: string; unit: string; points: PlotPoint[]; threshold?: number; onInspect?: (point: PlotPoint) => void;
}) {
  const [page, setPage] = useState(0), [selected, setSelected] = useState(0), [width, setWidth] = useState(1);
  const pages = Math.max(1, Math.ceil(points.length / CHART_PAGE_SIZE));
  const start = Math.min(page, pages - 1) * CHART_PAGE_SIZE;
  const visible = points.slice(start, start + CHART_PAGE_SIZE);
  if (!visible.length) return <AppText>No {title.toLowerCase()} points are available.</AppText>;
  const active = visible[Math.min(selected, visible.length - 1)];
  const values = visible.flatMap(p => p.value !== null && Number.isFinite(p.value) ? [p.value] : []);
  if (threshold !== undefined) values.push(threshold);
  const low = Math.min(0, ...values), high = Math.max(0, ...values);
  // Normalize before subtracting to avoid overflow for very large finite data.
  const scale = Math.max(Math.abs(low), Math.abs(high), Number.MIN_VALUE);
  const bottom = low / scale, span = (high / scale - bottom) || 1;
  const first = visible[0].window.start_seconds, last = visible[visible.length - 1].window.end_seconds;
  const x = (time: number) => 12 + (time - first) / Math.max(10, last - first) * 336;
  const y = (n: number) => 160 - ((n / scale - bottom) / span) * 144;
  function inspect(index: number) {
    const next = Math.max(0, Math.min(visible.length - 1, index));
    setSelected(next); onInspect?.(visible[next]);
  }
  function changePage(next: number) { setPage(next); setSelected(0); onInspect?.(points[next * CHART_PAGE_SIZE]); }
  return <View style={styles.stack} testID={`${title} chart`}>
    <AppText variant="label">{title} · {unit}</AppText>
    <View style={styles.row}><AppText variant="caption">{plotNumber(high)} {unit}</AppText>
      <AppText variant="caption" tone="secondary">Page {page + 1} of {pages} · local scale</AppText></View>
    <Pressable accessibilityRole="image" accessibilityLabel={`${title} line graph. Use previous and next reading buttons to inspect every value.`}
      onLayout={e => setWidth(e.nativeEvent.layout.width)}
      onPress={e => {
        const time = first + Math.max(0, Math.min(1, (e.nativeEvent.locationX / width * 360 - 12) / 336)) * (last - first);
        let closest = 0;
        visible.forEach((p, i) => { if (Math.abs(p.window.start_seconds - time) < Math.abs(visible[closest].window.start_seconds - time)) closest = i; });
        inspect(closest);
      }}>
      <Svg width="100%" height={180} viewBox="0 0 360 180" preserveAspectRatio="none" accessible={false}>
        {visible.filter(p => p.flagged).map(p => <Rect key={p.id} testID="flagged-window-band"
          x={x(p.window.start_seconds)} y={8} width={Math.max(1, x(p.window.end_seconds) - x(p.window.start_seconds))} height={160} fill={colors.dangerSoft} />)}
        {[16, 88, 160].map(v => <Line key={v} x1={12} x2={348} y1={v} y2={v} stroke={colors.border} />)}
        {threshold !== undefined && <Line testID="novelty-threshold-line" x1={12} x2={348} y1={y(threshold)} y2={y(threshold)} stroke={colors.warning} strokeWidth={2} strokeDasharray="6 4" />}
        {lineRuns(visible).map((run, i) => <Polyline key={i} testID="observed-line" fill="none" stroke={colors.accent} strokeWidth={2}
          points={run.map(p => `${x(p.window.start_seconds)},${y(p.value!)}`).join(' ')} />)}
        {visible.filter(p => p.value !== null).map(p => <Circle key={p.id} cx={x(p.window.start_seconds)} cy={y(p.value!)}
          r={p.id === active.id ? 5 : p.flagged ? 4 : 2} fill={p.flagged ? colors.danger : colors.accent} />)}
      </Svg>
    </Pressable>
    <View style={styles.row}><AppText variant="caption">{plotNumber(low)} {unit}</AppText>
      <AppText variant="caption">{clock(first)}–{clock(last)} · source clock</AppText></View>
    <AppText variant="caption" tone="secondary">Blue: {threshold === undefined ? 'observed median' : 'novelty score'}. Red/shaded: flagged target window.{threshold !== undefined ? ` Dashed: threshold ${plotNumber(threshold)}.` : ''} Gaps are not interpolated.</AppText>
    <View accessibilityLiveRegion="polite" testID={`${title} inspection`}>
      <AppText>{clock(active.window.start_seconds)}–{clock(active.window.end_seconds)} · {active.id}</AppText>
      <AppText>{active.value === null ? 'Measurement unavailable' : `${plotNumber(active.value)} ${unit}`}{active.flagged ? ' · Novelty flagged' : ''}</AppText>
      {!!active.missingFraction && <AppText tone="secondary">Missing readings: {plotNumber(active.missingFraction * 100)}% of this window.</AppText>}
    </View>
    <View style={styles.actions}>
      <AppButton title={`Previous ${title.toLowerCase()} reading`} variant="text" disabled={selected === 0} onPress={() => inspect(selected - 1)} />
      <AppButton title={`Next ${title.toLowerCase()} reading`} variant="text" disabled={selected >= visible.length - 1} onPress={() => inspect(selected + 1)} />
    </View>
    {pages > 1 && <View style={styles.actions}>
      <AppButton title={`Previous ${title.toLowerCase()} page`} variant="secondary" disabled={page === 0} onPress={() => changePage(page - 1)} />
      <AppButton title={`Next ${title.toLowerCase()} page`} variant="secondary" disabled={page >= pages - 1} onPress={() => changePage(page + 1)} />
    </View>}
    <AppText variant="caption" tone="secondary">Showing readings {start + 1}–{start + visible.length} of {points.length}. All pages retain original backend values.</AppText>
  </View>;
}
const styles = StyleSheet.create({ stack: { gap: spacing.xs }, row: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', gap: spacing.xs },
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs } });
