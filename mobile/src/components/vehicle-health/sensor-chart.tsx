// Time-positioned SVG history chart; gaps remain gaps and summaries use these samples.
import { useId } from 'react';
import { View } from 'react-native';
import Svg, { Line, Path, Text as SvgText } from 'react-native-svg';
import { historyStats } from '@/lib/history';
import type { Reading, SensorKey } from '@/types/vehicle-health';
import { colors as c } from '@/theme/colors';
import { Copy, State, styles } from './ui';
export function formatValue(value: number | null, unit: string | null = '') {
  return value === null || !Number.isFinite(value)
    ? 'Unavailable'
    : `${Number(value.toFixed(2))}${unit ? ` ${unit}` : ''}`;
}
export function SensorChart({
  history,
  sensor,
  unit,
  compact = false,
}: {
  history: Reading[];
  sensor: SensorKey;
  unit: string | null;
  compact?: boolean;
}) {
  const labelId = useId();
  const stats = historyStats(history, sensor);
  if (stats.min === null || stats.max === null)
    return compact ? (
      <Copy muted>No history</Copy>
    ) : (
      <State
        title="History unavailable"
        message="No numeric readings are available for this period."
      />
    );
  const span = stats.max - stats.min || 1;
  const low = stats.min - span * 0.15,
    high = stats.max + span * 0.15;
  const start = Date.parse(history[0].timestamp),
    end = Date.parse(history[history.length - 1].timestamp);
  const x = (timestamp: string) =>
    38 + ((Date.parse(timestamp) - start) / (end - start || 1)) * 272;
  const y = (value: number) => 15 + ((high - value) / (high - low)) * 120;
  const path = history
    .map((point, index) => {
      const value = point.values[sensor];
      if (value === null || !Number.isFinite(value)) return '';
      const previous = history[index - 1]?.values[sensor];
      const connected = previous != null && Number.isFinite(previous);
      return `${connected ? 'L' : 'M'}${x(point.timestamp)},${y(value)}`;
    })
    .join(' ');
  const time = (stamp: string) => new Date(stamp).toISOString().slice(11, 16);
  return (
    <View
      accessible
      accessibilityLabel={`${sensor} history. ${history.length} samples. Minimum ${formatValue(stats.min, unit)}, maximum ${formatValue(stats.max, unit)}.`}
      nativeID={labelId}
    >
      <Svg width="100%" height={compact ? 80 : 190} viewBox="0 0 325 165">
        {[0, 1, 2, 3].map((i) => (
          <Line key={i} x1={38} x2={310} y1={15 + i * 40} y2={15 + i * 40} stroke={c.border} />
        ))}
        {!compact &&
          [high, (high + low) / 2, low].map((v, i) => (
            <SvgText key={i} x={0} y={20 + i * 60} fill={c.textMuted} fontSize={10}>
              {v.toFixed(1)}
            </SvgText>
          ))}
        <Path d={path} stroke={c.primary} strokeWidth={2} fill="none" strokeLinecap="round" />
        {!compact && (
          <>
            <SvgText x={38} y={160} fill={c.textMuted} fontSize={10}>
              {time(history[0].timestamp)}
            </SvgText>
            <SvgText x={310} y={160} textAnchor="end" fill={c.textMuted} fontSize={10}>
              {time(history[history.length - 1].timestamp)} UTC
            </SvgText>
          </>
        )}
      </Svg>
      {!compact && (
        <View style={[styles.wrap, { justifyContent: 'space-between' }]}>
          {Object.entries(stats).map(([key, value]) => (
            <View key={key}>
              <Copy muted style={{ fontSize: 12, textTransform: 'capitalize' }}>
                {key}
              </Copy>
              <Copy>{formatValue(value, unit)}</Copy>
            </View>
          ))}
        </View>
      )}
    </View>
  );
}
