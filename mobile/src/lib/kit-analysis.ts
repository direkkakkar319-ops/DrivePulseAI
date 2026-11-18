// Validate untrusted API JSON without coercing numbers or dropping additive fields.
import { segmentKey } from '@/lib/kit-visualization';
import { kitSignals, type KitAnalysis, type KitSampleCatalog, type KitWindowReference } from '@/types/kit-analysis';

type ObjectValue = Record<string, unknown>;
const bad = () => new Error('The analysis service returned an incompatible response.');
function check(condition: unknown): asserts condition { if (!condition) throw bad(); }
function object(value: unknown): ObjectValue { check(value !== null && typeof value === 'object' && !Array.isArray(value)); return value as ObjectValue; }
function text(value: unknown): asserts value is string { check(typeof value === 'string' && value.trim().length > 0); }
function numeric(value: unknown, minimum = -Infinity): asserts value is number { check(typeof value === 'number' && Number.isFinite(value) && value >= minimum); }
function integer(value: unknown, minimum = 0): asserts value is number { numeric(value, minimum); check(Number.isSafeInteger(value)); }
function array(value: unknown): unknown[] { check(Array.isArray(value)); return value; }
function strings(value: unknown) { const items = array(value); check(items.length > 0); items.forEach(text); }
function fields(value: ObjectValue, names: string[]) { names.forEach(name => text(value[name])); }
function literal(value: unknown, expected: unknown) { check(value === expected); }
function close(a: number, b: number) { return Math.abs(a - b) <= Math.max(1e-12, Math.abs(b) * 1e-9); }
export function isRecordingDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || value.startsWith('0000')) return false;
  const time = Date.parse(`${value}T00:00:00.000Z`);
  return Number.isFinite(time) && new Date(time).toISOString().slice(0, 10) === value;
}
function date(value: unknown) { text(value); check(isRecordingDate(value)); }
function sample(value: unknown) {
  const v = object(value);
  fields(v, ['id', 'display_name', 'recording_id', 'dataset', 'creator', 'source_doi', 'license', 'license_url']);
  check(typeof v.id === 'string' && /^[a-z0-9][a-z0-9-]{0,63}$/.test(v.id));
  date(v.recording_date); check(['train', 'validation', 'test'].includes(v.source_split as string));
  integer(v.window_count, 2); integer(v.valid_pair_count, 1); check(v.valid_pair_count < v.window_count);
  literal(v.window_seconds, 10); literal(v.compatible_model_version, 'kit-xgb-forecast-v1'); strings(v.limitations);
}
export function parseKitCatalog(value: unknown): KitSampleCatalog {
  const v = object(value); literal(v.schema_version, 1);
  const samples = array(v.samples); samples.forEach(sample);
  check(new Set(samples.map(item => object(item).id)).size === samples.length);
  return v as unknown as KitSampleCatalog;
}
const referenceFields = ['id', 'recording_id', 'recording_date', 'split', 'segment_id', 'start_seconds', 'end_seconds', 'relative_start_seconds'];
function window(value: unknown): ObjectValue {
  const v = object(value); fields(v, ['id', 'recording_id', 'split']); date(v.recording_date);
  integer(v.segment_id); integer(v.start_seconds); integer(v.end_seconds); integer(v.relative_start_seconds);
  check(v.start_seconds < 86400 && v.start_seconds % 10 === 0 && v.end_seconds === v.start_seconds + 10);
  return v;
}
function same(a: ObjectValue, b: ObjectValue, keys = referenceFields) { return keys.every(k => a[k] === b[k]); }
function signals(value: unknown, nonnegative: boolean, sparse = false): ObjectValue {
  const v = object(value); check(Object.keys(v).every(k => kitSignals.includes(k as typeof kitSignals[number])));
  if (!sparse) check(Object.keys(v).length === kitSignals.length);
  Object.values(v).forEach(n => numeric(n, nonnegative ? 0 : -Infinity)); return v;
}
function deviations(value: unknown) {
  const items = array(value); check(items.length <= 3);
  items.forEach(item => { const v = object(item); check(kitSignals.includes(v.signal as typeof kitSignals[number])); numeric(v.normalized_error, 0); });
  check(new Set(items.map(item => object(item).signal)).size === items.length);
}
export function parseKitAnalysis(value: unknown): KitAnalysis {
  const v = object(value); literal(v.schema_version, 1); literal(v.analysis_type, 'kit_telemetry_novelty');
  literal(v.window_seconds, 10); literal(v.persisted, false); integer(v.window_count, 2); integer(v.pair_count, 1);
  fields(v, ['time_basis', 'relative_time_basis', 'interval_definition', 'contribution_definition']); strings(v.limitations);
  const model = object(v.model); literal(model.schema_version, 1); literal(model.model_version, 'kit-xgb-forecast-v1');
  literal(model.assessment_type, 'novelty'); literal(model.label_status, 'unlabeled_dataset_not_fault_diagnosis');
  numeric(model.threshold, Number.MIN_VALUE);
  const threshold = model.threshold;
  if (v.source_type === 'packaged_sample') {
    sample(v.sample); const source = object(v.sample);
    literal(source.window_count, v.window_count); literal(source.valid_pair_count, v.pair_count);
  } else {
    literal(v.source_type, 'uploaded_csv'); const source = object(v.source);
    literal(source.kind, 'uploaded_csv'); literal(source.format_version, 'kit_obd_raw_v1');
    literal(source.preprocessing_version, 'kit-10s-window-recipe-v1'); literal(source.metadata_verification, 'caller_supplied_unverified');
    text(source.recording_id); date(source.recording_date);
    ['input_bytes', 'accepted_rows', 'missing_cells', 'discarded_incomplete_windows', 'backward_timestamp_jumps', 'duplicate_timestamp_rows'].forEach(k => integer(source[k]));
  }
  const defs = array(v.signals); check(defs.length === 10);
  defs.forEach((item, i) => { const d = object(item); literal(d.name, kitSignals[i]); text(d.unit); text(d.display_name); });
  const telemetry = array(v.telemetry); literal(telemetry.length, v.window_count);
  const source = object(v.source_type === 'packaged_sample' ? v.sample : v.source);
  const split = v.source_type === 'packaged_sample' ? source.source_split : 'uploaded';
  const windows = new Map<string, ObjectValue>();
  const windowOrder = new Map<string, number>();
  const segmentEnds = new Map<string, number>();
  telemetry.forEach((item, index) => {
    const t = object(item); const w = window(t.window); check(!windows.has(w.id as string)); windows.set(w.id as string, w);
    literal(w.recording_id, source.recording_id); literal(w.recording_date, source.recording_date); literal(w.split, split);
    const segment = segmentKey(w as unknown as KitWindowReference);
    const lastStart = segmentEnds.get(segment);
    check(lastStart === undefined || (w.start_seconds as number) > lastStart);
    segmentEnds.set(segment, w.start_seconds as number); windowOrder.set(w.id as string, index);
    signals(t.medians, false); const fractions = signals(t.missing_fractions, true, true);
    check(Object.values(fractions).every(n => (n as number) < 1));
  });
  const predictions = array(v.predictions); literal(predictions.length, v.pair_count);
  const points = array(v.score_series); literal(points.length, predictions.length);
  const ids = new Set<string>(); let flagged = 0; let maximum = 0;
  const scores: number[] = [];
  let lastTargetIndex = -1;
  predictions.forEach((item, i) => {
    const p = object(item); text(p.pair_id); check(!ids.has(p.pair_id)); ids.add(p.pair_id);
    const current = window(p.current_window), target = window(p.next_window);
    check(same(current, target, ['recording_id', 'recording_date', 'split', 'segment_id']));
    check(target.start_seconds === (current.start_seconds as number) + 10);
    check(same(current, windows.get(current.id as string) ?? {}) && same(target, windows.get(target.id as string) ?? {}));
    const targetIndex = windowOrder.get(target.id as string)!;
    check(targetIndex > lastTargetIndex); lastTargetIndex = targetIndex;
    numeric(p.anomaly_score, 0); literal(p.threshold, threshold); literal(p.is_novel, p.anomaly_score > threshold);
    const errors = signals(p.normalized_signal_errors, true); check(close(p.anomaly_score, Math.max(...Object.values(errors) as number[])));
    deviations(p.top_signal_deviations);
    const ranked = [...kitSignals].sort((a, b) => (errors[b] as number) - (errors[a] as number)).slice(0, 3);
    const top = array(p.top_signal_deviations); check(top.length === 3);
    ranked.forEach((name, j) => { const d = object(top[j]); literal(d.signal, name); literal(d.normalized_error, errors[name]); });
    const point = object(points[i]); literal(point.pair_id, p.pair_id); literal(point.anomaly_score, p.anomaly_score);
    literal(point.threshold, p.threshold); literal(point.is_novel, p.is_novel); check(same(window(point.window), target));
    flagged += p.is_novel ? 1 : 0; maximum = Math.max(maximum, p.anomaly_score); scores.push(p.anomaly_score);
  });
  const summary = object(v.summary); literal(summary.evaluated_pairs, predictions.length);
  literal(summary.novel_pairs, flagged); literal(summary.not_novel_pairs, predictions.length - flagged);
  literal(summary.threshold, model.threshold); numeric(summary.novel_percentage, 0); numeric(summary.mean_anomaly_score, 0);
  check(close(summary.novel_percentage, flagged / predictions.length * 100)); literal(summary.max_anomaly_score, maximum);
  const mean = maximum ? maximum * (scores.reduce((sum, n) => sum + n / maximum, 0) / scores.length) : 0;
  check(close(summary.mean_anomaly_score, mean));
  const intervalIds = new Set<string>(); let previous = -1;
  array(v.flagged_intervals).forEach(item => {
    const interval = object(item); fields(interval, ['recording_id', 'split']); date(interval.recording_date); integer(interval.segment_id);
    integer(interval.start_seconds); integer(interval.end_seconds); numeric(interval.peak_anomaly_score, 0);
    const pairs = array(interval.pair_ids); check(pairs.length > 0); let end = interval.start_seconds; let peak = 0;
    pairs.forEach(id => {
      text(id); check(!intervalIds.has(id)); intervalIds.add(id);
      const index = predictions.findIndex(p => object(p).pair_id === id); check(index > previous); previous = index;
      const p = object(predictions[index]); literal(p.is_novel, true); const target = object(p.next_window);
      check(same(target, interval, ['recording_id', 'recording_date', 'split', 'segment_id'])); literal(target.start_seconds, end);
      end = target.end_seconds as number; peak = Math.max(peak, p.anomaly_score as number);
    });
    literal(interval.end_seconds, end); literal(interval.peak_anomaly_score, peak);
  });
  literal(intervalIds.size, flagged);
  const explanation = object(v.explanation);
  fields(explanation, ['summary', 'signal_summary', 'score_definition', 'threshold_definition', 'signal_definition', 'measurement_definition', 'limitations']);
  literal(explanation.signal_scope, flagged ? 'flagged_pairs' : 'all_evaluated_pairs'); deviations(explanation.strongest_signal_deviations);
  return v as unknown as KitAnalysis;
}
