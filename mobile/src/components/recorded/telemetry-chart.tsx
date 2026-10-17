// SVG chart using original sample offsets, with gaps and saved persistent intervals visible.
import { View } from 'react-native';
import Svg, { Circle, Line, Path, Rect, Text as SvgText } from 'react-native-svg';
import type { PersistentInterval, TelemetrySample } from '@/types/recorded-telemetry';
import { measurement } from '@/lib/recorded-replay';
import { Copy, palette } from './ui';
import { colors, spacing, type } from './theme';
export const channels = [
  { key: 'voltage_v', label: 'High-voltage battery', unit: 'V' },
  { key: 'temperature_c', label: 'Pack 1 temperature', unit: '°C' },
  { key: 'soc_percent', label: 'Battery SOC', unit: '%' },
] as const;
export function TelemetryChart({ samples, channel, intervals = [] }: { samples: TelemetrySample[]; channel: typeof channels[number]; intervals?: PersistentInterval[] }) {
  const numeric = samples.map(s => s[channel.key]).filter((v): v is number => v !== null && Number.isFinite(v));
  if (!numeric.length) return <Copy muted>No measured history available.</Copy>;
  const min = Math.min(...numeric), max = Math.max(...numeric), pad = (max - min || 1) * 0.15;
  const start = samples[0].playback_offset_ms, end = samples.at(-1)!.playback_offset_ms;
  const plot = { left: 52, right: 318, top: 14, bottom: 120 };
  const x = (offset: number) => plot.left + (offset - start) / (end - start || 1) * (plot.right - plot.left);
  const y = (v: number) => plot.top + (max + pad - v) / (max - min + 2 * pad) * (plot.bottom - plot.top);
  const path = samples.map((s, i) => {
    const value = s[channel.key], prior = samples[i - 1];
    if (value === null || !Number.isFinite(value)) return '';
    const connected = prior && prior[channel.key] !== null && Number.isFinite(prior[channel.key]) && s.playback_offset_ms - prior.playback_offset_ms <= 1000;
    return `${connected ? 'L' : 'M'}${x(s.playback_offset_ms)},${y(value)}`;
  }).join(' ');
  const time = (s: TelemetrySample) => s.original_timestamp_utc.slice(11, 23);
  const current = samples.at(-1)!;
  const currentValue = current[channel.key];
  const flagged = samples.filter(sample => sample.unusual && sample[channel.key] !== null);
  const precision = channel.key === 'soc_percent' ? 1 : channel.key === 'temperature_c' ? 1 : 0;
  return <View accessible accessibilityRole="image" accessibilityLabel={`${channel.label} recorded history. Current ${measurement(currentValue, channel.unit)}. ${numeric.length} available samples. Minimum ${measurement(min, channel.unit)}, maximum ${measurement(max, channel.unit)}. ${flagged.length} statistically unusual samples shown.`} style={{ gap: spacing.xs }}>
    <Svg width="100%" height={186} viewBox="0 0 334 168" preserveAspectRatio="xMidYMid meet">
      {intervals.map(interval => {
        const inside = samples.filter(s => s.source_row >= interval.start_source_row && s.source_row <= interval.end_source_row);
        return inside.length ? <Rect key={interval.interval_id} x={x(inside[0].playback_offset_ms)} y={plot.top} width={Math.max(2, x(inside.at(-1)!.playback_offset_ms) - x(inside[0].playback_offset_ms))} height={plot.bottom - plot.top} fill={colors.unusualSoft} /> : null;
      })}
      {[max + pad, (max + min) / 2, min - pad].map((value, i) => <ChartGridLine key={i} value={value} position={i} precision={precision} />)}
      {flagged.map(sample => <Circle key={sample.source_row} cx={x(sample.playback_offset_ms)} cy={y(sample[channel.key]!)} r={2.2} fill={colors.unusual} opacity={0.78} />)}
      <Path d={path} stroke={colors.accent} strokeWidth={2.25} fill="none" strokeLinejoin="round" strokeLinecap="round" />
      <Line x1={x(current.playback_offset_ms)} x2={x(current.playback_offset_ms)} y1={plot.top} y2={plot.bottom} stroke={colors.borderStrong} strokeDasharray="3 3" />
      {currentValue !== null && Number.isFinite(currentValue) && <Circle cx={x(current.playback_offset_ms)} cy={y(currentValue)} r={4} fill={current.unusual ? colors.unusual : colors.accent} stroke={colors.white} strokeWidth={2} />}
      <SvgText x={plot.left} y={143} fill={palette.muted} fontSize={10}>{time(samples[0])}</SvgText>
      <SvgText x={plot.right} y={143} textAnchor="end" fill={palette.muted} fontSize={10}>{time(current)}</SvgText>
      <SvgText x={plot.right} y={158} textAnchor="end" fill={palette.muted} fontSize={10}>UTC</SvgText>
    </Svg>
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: spacing.md }}>
      <Copy muted style={type.caption}>{channel.unit} · Original recording time</Copy>
      <Copy muted style={type.caption}>● Current sample</Copy>
      {!!flagged.length && <Copy style={{ color: colors.unusual, ...type.caption }}>● Unusual sample</Copy>}
      {!!intervals.length && <Copy muted style={type.caption}>Shading: persistent interval</Copy>}
    </View>
  </View>;
}
function ChartGridLine({ value, position, precision }: { value: number; position: number; precision: number }) {
  const y = 14 + position * 53;
  return <><Line x1={52} x2={318} y1={y} y2={y} stroke={palette.line} /><SvgText x={46} y={y + 4} textAnchor="end" fill={palette.muted} fontSize={10}>{value.toFixed(precision)}</SvgText></>;
}
