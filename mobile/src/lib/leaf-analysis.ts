// Validate network data before rendering, including identity mapping and score direction.
import { leafFeatures, type LeafAnalysis, type LeafCatalog } from '@/types/leaf-analysis';
function check(value: unknown): asserts value { if (!value) throw new Error('Incompatible Nissan analysis'); }
function object(value: unknown): Record<string, unknown> { check(value && typeof value === 'object' && !Array.isArray(value)); return value as Record<string, unknown>; }
function number(value: unknown): asserts value is number { check(typeof value === 'number' && Number.isFinite(value)); }
function count(value: unknown): asserts value is number { number(value); check(Number.isSafeInteger(value) && value >= 0); }
function strings(value: unknown) { check(Array.isArray(value) && value.every(s => typeof s === 'string')); }
function nullable(value: unknown) { if (value !== null) number(value); }
function rows(value: unknown): unknown[] { check(Array.isArray(value) && value.length <= 10000); return value; }
function time(value: unknown) { count(value); check(value >= 946684800000000 && value < 4102444800000000); }
function intervalTriple(v: Record<string, unknown>, keys: string[]) {
  const values = keys.map(key => v[key]);
  values.forEach(value => { if (value !== undefined && value !== null) { number(value); check(value >= 0); } });
  if (values.some(value => value !== undefined && value !== null)) {
    check(values.every(value => typeof value === 'number'));
    check((values[0] as number) <= (values[1] as number) && (values[1] as number) <= (values[2] as number));
  }
}
function confidenceInterval(result: Record<string, unknown>) {
  intervalTriple(result, ['rul_km_p10','rul_km_p50','rul_km_p90']);
  intervalTriple(result, ['estimated_days_to_threshold_p10','estimated_days_to_threshold_p50','estimated_days_to_threshold_p90']);
  if (result.confidence_interval === undefined || result.confidence_interval === null) return;
  const ci = object(result.confidence_interval); number(ci.level_pct); check(ci.level_pct > 0 && ci.level_pct < 100);
  for (const key of ['rul_km_p10','rul_km_p50','rul_km_p90']) { number(ci[key]); check((ci[key] as number) >= 0); }
  intervalTriple(ci, ['rul_km_p10','rul_km_p50','rul_km_p90']);
  intervalTriple(ci, ['estimated_days_p10','estimated_days_p50','estimated_days_p90']);
  count(ci.bootstrap_iterations_valid); check(ci.interpretation === undefined || ci.interpretation === null || typeof ci.interpretation === 'string');
  for (const [flat, nested] of [['rul_km_p10','rul_km_p10'],['rul_km_p50','rul_km_p50'],['rul_km_p90','rul_km_p90'],['estimated_days_to_threshold_p10','estimated_days_p10'],['estimated_days_to_threshold_p50','estimated_days_p50'],['estimated_days_to_threshold_p90','estimated_days_p90']]) {
    if (result[flat] !== undefined && result[flat] !== null) check(result[flat] === ci[nested]);
  }
}
export function parseLeafCatalog(value: unknown): LeafCatalog {
  const v = object(value); check(v.schema_version === 1);
  const samples = rows(v.samples); const ids = new Set();
  samples.forEach(item => { const s = object(item); check(typeof s.id === 'string' && /^[a-z0-9][a-z0-9-]{0,63}$/.test(s.id) && !ids.has(s.id)); ids.add(s.id);
    check(typeof s.display_name === 'string' && typeof s.provenance === 'string' && typeof s.synthetic === 'boolean' && s.format_version === 'leaf-csv-v1'); strings(s.limitations); });
  return value as LeafCatalog;
}
export function parseLeafAnalysis(value: unknown): LeafAnalysis {
  const v = object(value); check(v.schema_version === 1 && v.analysis_type === 'nissan_leaf_telemetry' && v.persisted === false);
  check(v.source_type === 'built_in_sample' || v.source_type === 'uploaded_csv');
  const source = object(v.source); check(source.format_version === 'leaf-csv-v1' && typeof source.synthetic === 'boolean' && typeof source.provenance === 'string');
  check(v.source_type === 'built_in_sample' ? typeof source.sample_id === 'string' : source.sample_id === null && source.synthetic === false);
  const recording = object(v.recording); count(recording.reading_count); count(recording.input_rows); count(recording.skipped_timestamp_rows); count(recording.valid_timestamp_rows); count(recording.missing_or_invalid_cells); count(recording.backward_or_duplicate_timestamps);
  check(recording.input_rows === (recording.valid_timestamp_rows as number) + (recording.skipped_timestamp_rows as number));
  check(recording.reading_count === recording.valid_timestamp_rows && recording.timestamp_unit === 'unix_microseconds'); strings(recording.columns); strings(recording.issues);
  check(typeof recording.vehicle_identity === 'string' && typeof recording.vehicle_compatibility === 'string'); time(recording.start_timestamp_us); time(recording.end_timestamp_us);
  const telemetry = rows(v.telemetry); check(telemetry.length > 0 && telemetry.length === recording.reading_count);
  const identities = new Map<number, Record<string, unknown>>(); let previousRow = 0;
  telemetry.forEach(item => { const r = object(item); count(r.row_id); check(r.row_id > previousRow && !identities.has(r.row_id)); previousRow = r.row_id; time(r.timestamp_us);
    Object.values(object(r.values)).forEach(nullable); identities.set(r.row_id, r); });
  const battery = object(v.battery); nullable(battery.latest_soc); nullable(battery.latest_soh);
  for (const name of ['soc', 'soh']) { const measurement = battery[`latest_${name}`]; const stamp = battery[`${name}_timestamp_us`];
    if (measurement === null) check(stamp === null); else { number(measurement); check(measurement >= 0 && measurement <= 100); time(stamp); }
  }
  check(battery.estimated_range_km === null && battery.range_status === 'unavailable' && typeof battery.range_reason === 'string');
  const a = object(v.anomaly); check(['completed', 'unavailable', 'failed'].includes(a.status as string)); check(a.reason === null || typeof a.reason === 'string');
  check(a.score_direction === 'lower_is_more_unusual'); ['analyzed_count', 'skipped_count', 'unusual_count'].forEach(k => count(a[k])); number(a.unusual_percentage);
  const predictions = rows(a.results); check(predictions.length === a.analyzed_count && (a.analyzed_count as number) + (a.skipped_count as number) === telemetry.length);
  let unusual = 0; previousRow = 0;
  if (a.status === 'completed') { check(a.model_version === 'nissan-leaf-isolation-forest-v1'); number(a.threshold); check(predictions.length > 0 && a.explanation_status === 'top_three_shap_contributions_for_unusual_rows'); }
  else check(predictions.length === 0 && a.threshold === null);
  predictions.forEach(item => { const p = object(item); count(p.row_id); check(p.row_id > previousRow); previousRow = p.row_id;
    const reading = identities.get(p.row_id); check(reading && reading.timestamp_us === p.timestamp_us); number(p.anomaly_score);
    check(typeof p.is_unusual === 'boolean' && p.is_unusual === (p.anomaly_score < (a.threshold as number)));
    if (!p.is_unusual) check(p.explanation === null);
    else { unusual++; const e = object(p.explanation); check(e.method === 'shap_permutation' && typeof e.output === 'string' && typeof e.interpretation === 'string'); number(e.baseline_score);
      const contributions = rows(e.contributions); check(contributions.length === 3); const features = new Set(); let magnitude = Infinity;
      contributions.forEach((item, index) => { const c = object(item); check(c.rank === index + 1 && leafFeatures.includes(c.feature as typeof leafFeatures[number]) && !features.has(c.feature)); features.add(c.feature);
        number(c.measured_value); check(c.measured_value === object(reading.values)[c.feature as string]); number(c.shap_value);
        check(Math.abs(c.shap_value) <= magnitude); magnitude = Math.abs(c.shap_value);
        check(c.direction === (c.shap_value < 0 ? 'toward_anomaly' : 'toward_typical')); });
    }
  });
  check(unusual === a.unusual_count && Math.abs((a.unusual_percentage as number) - (predictions.length ? 100 * unusual / predictions.length : 0)) < 1e-8);
  for (const name of ['health', 'rul']) { const c = object(v[name]); check(['completed', 'unavailable', 'insufficient_history', 'failed'].includes(c.status as string)); check(c.reason === null || typeof c.reason === 'string');
    if (c.status === 'completed' || c.status === 'insufficient_history') {
      const result = object(c.result); check(result.schema_version === 1);
      if (name === 'health') { check(result.model_version === 'nissan-leaf-soh-bands-v1'); count(result.health_score); check(result.health_score >= 1 && result.health_score <= 5 && typeof result.label === 'string'); number(result.soh_pct); rows(result.bands); }
      else { check(result.model_version === 'nissan-leaf-soh-theilsen-v1'); check(['ok','threshold_reached','insufficient_history','insufficient_odometer_variation','non_declining_trend','no_valid_history'].includes(result.status as string)); nullable(result.rul_km); strings(result.limitations); confidenceInterval(result); }
    } else check(c.result === null);
  }
  Object.values(object(v.units)).forEach(unit => check(typeof unit === 'string')); strings(v.warnings); strings(v.limitations);
  return value as LeafAnalysis;
}
