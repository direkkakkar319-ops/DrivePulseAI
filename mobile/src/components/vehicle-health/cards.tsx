// Vehicle, provenance, assessment, insight and sensor presentation components.
import { Image, Pressable, View, useWindowDimensions } from 'react-native';
import Svg, { Circle } from 'react-native-svg';
import type {
  Assessment,
  DataSource,
  Insight,
  Vehicle,
  VehicleSnapshot,
} from '@/types/vehicle-health';
import { sensors } from '@/types/sensors';
import { colors as c } from '@/theme/colors';
import { Badge, Card, Copy, Icon, styles } from './ui';
import { formatValue, SensorChart } from './sensor-chart';
export const carArtwork = require('@/assets/images/vehicles/demo-sedan.png');
export function SourceBadge({ source }: { source: DataSource }) {
  return (
    <Badge
      label={source === 'simulated' ? 'DEMO DATA' : source === 'real' ? 'REAL DATA' : 'NO DATA'}
      warning={source === 'simulated'}
    />
  );
}
export function VehicleCard({
  vehicle,
  onPress,
  compact = false,
}: {
  vehicle: Vehicle;
  onPress?: () => void;
  compact?: boolean;
}) {
  const content = (
    <Card>
      <View style={styles.row}>
        <View style={{ flex: 1 }}>
          <Copy style={{ fontSize: 20, fontWeight: '600' }}>{vehicle.name}</Copy>
          <Copy muted>{vehicle.id}</Copy>
        </View>
        <SourceBadge source={vehicle.source} />
        {onPress && <Icon name="arrow" size={18} />}
      </View>
      <Image
        source={carArtwork}
        style={{ width: '100%', height: compact ? 85 : 155, borderRadius: 10 }}
        resizeMode="cover"
        accessible={false}
      />
      <Copy muted style={{ fontSize: 10 }}>
        Illustrative vehicle artwork
      </Copy>
    </Card>
  );
  return onPress ? (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`View ${vehicle.name}`}
    >
      {content}
    </Pressable>
  ) : (
    content
  );
}
export function Freshness({ data }: { data: VehicleSnapshot }) {
  const label =
    data.connection === 'playback'
      ? 'Demo playback · fixed snapshot'
      : data.connection === 'connected'
        ? 'Receiving data'
        : data.connection === 'waiting'
          ? 'Waiting for readings'
          : data.connection === 'disconnected'
            ? 'Disconnected'
            : 'No readings';
  return (
    <View style={{ gap: 4 }}>
      <Copy style={{ color: data.freshness === 'stale' ? c.warning : c.primary }}>
        {label}
        {data.freshness === 'stale' ? ' · Stale data' : ''}
      </Copy>
      <Copy muted style={{ fontSize: 12 }}>
        {data.latest
          ? `Recorded ${new Date(data.latest.timestamp).toLocaleString()}`
          : 'Last updated unavailable'}
      </Copy>
    </View>
  );
}
export function HealthCard({ assessment }: { assessment: Assessment }) {
  return (
    <Card>
      <View style={[styles.row, { flexWrap: 'wrap' }]}>
        <Copy style={{ fontWeight: '600' }}>Vehicle health</Copy>
        <Badge label={assessment.label} />
      </View>
      <View style={styles.row}>
        <View style={{ width: 140, height: 140, alignItems: 'center', justifyContent: 'center' }}>
          <Svg width={140} height={140} style={{ position: 'absolute' }}>
            <Circle cx={70} cy={70} r={57} fill="none" stroke={c.border} strokeWidth={8} />
            <Circle
              cx={70}
              cy={70}
              r={57}
              fill="none"
              stroke={c.primary}
              strokeWidth={8}
              strokeDasharray={`${(assessment.score / 100) * 358} 358`}
              rotation={-90}
              origin="70,70"
              strokeLinecap="round"
            />
          </Svg>
          <Copy style={{ fontSize: 38, lineHeight: 44, fontWeight: '600' }}>
            {assessment.score}
          </Copy>
          <Copy muted>/100</Copy>
        </View>
        <View style={{ flex: 1, gap: 8 }}>
          <Icon size={34} />
          <Copy>{assessment.source === 'simulated' ? 'Demo score' : 'Health assessment'}</Copy>
          <Copy muted>Review the evidence below.</Copy>
        </View>
      </View>
      <Copy muted style={{ fontSize: 12 }}>
        {assessment.explanation}
      </Copy>
    </Card>
  );
}
export function InsightCard({ insight, onPress }: { insight: Insight; onPress: () => void }) {
  const sensor = sensors.find((s) => s.key === insight.sensor)!;
  return (
    <Pressable accessibilityRole="button" onPress={onPress}>
      <Card>
        <View style={styles.row}>
          <Icon name="warning" color={c.warning} size={28} />
          <View style={{ flex: 1 }}>
            <Copy style={{ fontWeight: '600' }}>{insight.title}</Copy>
            <Copy muted>
              {formatValue(insight.observed, sensor.unit)} ·{' '}
              {insight.source === 'simulated' ? 'Demo observation' : 'Observation'}
            </Copy>
          </View>
          <Icon name="arrow" />
        </View>
      </Card>
    </Pressable>
  );
}
export function SensorCards({
  data,
  onSelect,
  preview = false,
}: {
  data: VehicleSnapshot;
  onSelect: (sensor: string) => void;
  preview?: boolean;
}) {
  const { width, fontScale } = useWindowDimensions();
  const grid = preview && width >= 360 && fontScale <= 1.3;
  return (
    <View style={{ gap: 10, flexDirection: grid ? 'row' : 'column', flexWrap: 'wrap' }}>
      {sensors.slice(0, preview ? 4 : sensors.length).map((sensor) => (
        <Pressable
          key={sensor.key}
          onPress={() => onSelect(sensor.key)}
          accessibilityRole="button"
          accessibilityLabel={`${sensor.label} history`}
          style={{ width: grid ? '48%' : '100%', flexGrow: grid ? 1 : 0 }}
        >
          <Card>
            <View style={styles.row}>
              <Icon name={sensor.symbol} />
              <View style={{ flex: 1 }}>
                <Copy muted style={{ fontSize: 12 }}>
                  {sensor.label}
                </Copy>
                <Copy style={{ fontWeight: '600' }}>
                  {formatValue(data.latest?.values[sensor.key] ?? null, sensor.unit)}
                </Copy>
                {sensor.unit === null && (
                  <Copy muted style={{ fontSize: 10 }}>
                    Unit not established
                  </Copy>
                )}
              </View>
              {!preview && width >= 380 && fontScale <= 1.3 && (
                <View style={{ width: 90 }}>
                  <SensorChart
                    compact
                    history={data.history}
                    sensor={sensor.key}
                    unit={sensor.unit}
                  />
                </View>
              )}
              {!preview && <Icon name="arrow" size={16} />}
            </View>
          </Card>
        </Pressable>
      ))}
    </View>
  );
}
