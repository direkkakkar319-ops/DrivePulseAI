import { AppCard } from '@/components/ui/app-card';
import { AppText } from '@/components/ui/app-text';
import { AppStatus } from '@/components/ui/app-status';
import type { TrendAnalysis } from '@/types/leaf-analysis';
const names = { pack_temp_spread: 'Pack temperature spread', pack_temp_rise: 'Temperature rise over ambient', soh_decline_rate_per_kkm: 'SOH degradation rate', pack_avg_temp: 'Average battery temperature' };
export function LeafTrendResults({ trend }: { trend?: TrendAnalysis }) {
  const result = trend?.result;
  return <AppCard testID="leaf-trend-analysis">
    <AppText variant="subtitle">Battery Trend Analysis</AppText>
    {!trend ? <AppText>Trend analysis is unavailable from this backend response.</AppText> : <>
      <AppText>Status: {trend.status.replaceAll('_',' ')}</AppText>
      {trend.reason && <AppText>{trend.reason}</AppText>}
      <AppText>{trend.observed_days} observed UTC days · {trend.analyzed_readings} analyzed readings · {trend.skipped_readings} readings without trend inputs</AppText>
      {trend.start_timestamp_us !== null && trend.end_timestamp_us !== null && <AppText variant="caption">Source coverage: {new Date(trend.start_timestamp_us / 1000).toISOString()}–{new Date(trend.end_timestamp_us / 1000).toISOString()}</AppText>}
      {result && <>
        <AppText variant="caption">{result.model_version} · {result.status.replaceAll('_',' ')}</AppText>
        {trend.status === 'completed' && <AppText>{result.is_drift_detected ? `Unusual drift detected · ${result.drift_alerts_count} alerts` : 'No unusual drift detected in the evaluated latest daily signals.'}</AppText>}
        {result.warning_z_threshold != null && result.critical_z_threshold != null && <AppText variant="caption">Warning Z threshold: {result.warning_z_threshold} · Critical: {result.critical_z_threshold} · Up to {result.window_size_days} prior valid daily points</AppText>}
        {result.alerts.map(alert => <AppCard key={alert.signal}>
          <AppStatus label={`${alert.severity === 'critical' ? 'Critical' : 'Warning'} trend alert · ${alert.label}`} tone={alert.severity === 'critical' ? 'error' : 'warning'} />
          <AppText>{alert.explanation}</AppText>
          <AppText>Measured daily value: {alert.current_value} {alert.unit} · Baseline mean: {alert.baseline_mean} {alert.unit}</AppText>
          <AppText variant="caption">Z-score: {alert.z_score} · Baseline std: {alert.baseline_std} · Persistence: {alert.consecutive_days} observed points</AppText>
        </AppCard>)}
      </>}
      <AppText variant="label">Monitored signals and availability</AppText>
      {Object.entries(trend.signal_availability).map(([name,state]) => {
        const detail = result?.signal_details[name as keyof typeof names];
        return <AppCard key={name}><AppText variant="label">{names[name as keyof typeof names]}</AppText>
          <AppText>{state.status === 'available' ? 'Input fields available' : 'Unavailable'}{detail ? ` · ${detail.status.replaceAll('_',' ')}` : ''}</AppText>
          {state.reason && <AppText variant="caption">{state.reason}</AppText>}
          {detail?.current_value != null && <AppText>Daily value: {detail.current_value} {detail.unit} · Baseline: {detail.baseline_mean} {detail.unit} · Z-score: {detail.z_score}</AppText>}
          {detail?.baseline_points_available != null && <AppText variant="caption">Baseline points: {detail.baseline_points_available}/{detail.baseline_points_required}</AppText>}
        </AppCard>;
      })}
      {[...trend.warnings,...trend.limitations].map((warning,i) => <AppText key={i} variant="caption">{warning}</AppText>)}
    </>}
    <AppText variant="caption">Statistical drift is separate from point anomalies and SHAP. A trend alert is not a confirmed mechanical fault, battery failure or failure probability.</AppText>
  </AppCard>;
}
