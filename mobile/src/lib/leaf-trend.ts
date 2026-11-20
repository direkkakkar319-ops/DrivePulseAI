// Independent trend contract. Never recalculate severity from rounded Z-scores.
import { trendSignals, type TrendAnalysis } from '@/types/leaf-analysis';
function check(value: unknown): asserts value { if (!value) throw new Error('Invalid trend response'); }
function object(value: unknown): Record<string, unknown> { check(value && typeof value === 'object' && !Array.isArray(value)); return value as Record<string, unknown>; }
function number(value: unknown): asserts value is number { check(typeof value === 'number' && Number.isFinite(value)); }
function count(value: unknown): asserts value is number { number(value); check(Number.isSafeInteger(value) && value >= 0); }
function strings(value: unknown) { check(Array.isArray(value) && value.every(v => typeof v === 'string')); }
function signal(key: string) { check(trendSignals.includes(key as typeof trendSignals[number])); }
export function parseLeafTrend(value: unknown): TrendAnalysis {
  const v = object(value); check(['completed','unavailable','insufficient_history','failed'].includes(v.status as string));
  check(v.reason === null || typeof v.reason === 'string');
  ['prepared_readings','analyzed_readings','skipped_readings','observed_days'].forEach(k => count(v[k]));
  check((v.analyzed_readings as number) <= (v.prepared_readings as number));
  for (const key of ['start_timestamp_us','end_timestamp_us']) if (v[key] !== null) { count(v[key]); check((v[key] as number) >= 946684800000000 && (v[key] as number) < 4102444800000000); }
  if (v.prepared_readings === 0) check(v.start_timestamp_us === null && v.end_timestamp_us === null && v.observed_days === 0);
  else { number(v.start_timestamp_us); number(v.end_timestamp_us); check(v.end_timestamp_us >= v.start_timestamp_us && (v.observed_days as number) >= 1); }
  strings(v.source_fields); strings(v.warnings); strings(v.limitations);
  const availability = object(v.signal_availability);
  Object.entries(availability).forEach(([name, item]) => { signal(name); const state = object(item); check(state.status === 'available' || state.status === 'unavailable'); check(state.reason === null || typeof state.reason === 'string'); });
  if (v.result === null) { check(v.status === 'unavailable' || v.status === 'failed'); check(v.analyzed_readings === 0); return value as TrendAnalysis; }
  check(v.status !== 'failed'); const r = object(v.result);
  check(r.schema_version === 1 && r.model_version === 'nissan-leaf-rolling-zscore-v1' && r.assessment_type === 'rolling_zscore_drift_detection');
  check(['ok','insufficient_history','empty_input'].includes(r.status as string)); check(typeof r.is_drift_detected === 'boolean'); count(r.drift_alerts_count);
  check(Array.isArray(r.alerts) && r.alerts.length <= 4 && r.alerts.length === r.drift_alerts_count && r.is_drift_detected === Boolean(r.alerts.length));
  check(v.analyzed_readings === v.prepared_readings);
  const details = object(r.signal_details); const flagged = new Set<string>();
  Object.entries(details).forEach(([name,item]) => {
    signal(name); const d = object(item); check(typeof d.label === 'string');
    check(['normal','warning','critical','non_finite_current_reading','insufficient_baseline_points'].includes(d.status as string));
    if (['normal','warning','critical'].includes(d.status as string)) {
      for (const key of ['current_value','baseline_mean','baseline_std','z_score']) number(d[key]); check((d.baseline_std as number) > 0 && typeof d.unit === 'string');
      count(d.consecutive_abnormal_days); count(d.baseline_window_days);
      if (d.status !== 'normal') flagged.add(name);
    }
    if (d.status === 'insufficient_baseline_points') { count(d.baseline_points_available); count(d.baseline_points_required); check((d.baseline_points_required as number) > 0); }
  });
  if (r.status === 'ok') {
    count(r.days_evaluated); check(r.days_evaluated === v.observed_days); count(r.window_size_days); check(r.window_size_days >= 3 && r.window_size_days <= 90);
    number(r.warning_z_threshold); number(r.critical_z_threshold); check(r.warning_z_threshold > 0 && r.critical_z_threshold > r.warning_z_threshold);
  } else {
    check(r.alerts.length === 0 && Object.keys(details).length === 0);
    if (r.status === 'insufficient_history') { count(r.days_available); count(r.min_days_required); check(r.days_available === v.observed_days && r.min_days_required > 0 && r.days_available < r.min_days_required && v.status === 'insufficient_history'); }
  }
  if (v.status === 'completed') check(r.status === 'ok' && Object.values(details).some(item => ['normal','warning','critical'].includes(object(item).status as string)));
  const seen = new Set();
  r.alerts.forEach(item => {
    const alert = object(item); check(typeof alert.signal === 'string'); signal(alert.signal); check(!seen.has(alert.signal)); seen.add(alert.signal);
    check(alert.severity === 'warning' || alert.severity === 'critical'); check(typeof alert.label === 'string' && typeof alert.unit === 'string' && typeof alert.explanation === 'string');
    const d = object(details[alert.signal]); check(d.status === alert.severity && d.label === alert.label && d.unit === alert.unit);
    for (const key of ['current_value','baseline_mean','baseline_std','z_score']) { number(alert[key]); check(alert[key] === d[key]); }
    count(alert.consecutive_days); check(alert.consecutive_days >= 1 && alert.consecutive_days === d.consecutive_abnormal_days);
  });
  check(seen.size === flagged.size && [...flagged].every(name => seen.has(name)));
  return value as TrendAnalysis;
}
