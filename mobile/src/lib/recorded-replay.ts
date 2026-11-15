// Pure replay transitions, score semantics and boundary validation; no model inference.
import type { PersistentInterval, ReplayClip, ReplayState, TelemetrySample } from '@/types/recorded-telemetry';
export const FROZEN_THRESHOLD = -0.6676090615628322;
export function isUnusual(score: number | null, threshold = FROZEN_THRESHOLD): boolean | null {
  return score === null || !Number.isFinite(score) ? null : score < threshold;
}
export function measurement(value: number | null | undefined, unit = '', digits = 2) {
  return value == null || !Number.isFinite(value) ? 'Unavailable' : `${Number(value.toFixed(digits))}${unit ? ` ${unit}` : ''}`;
}
export function recordedTime(timestamp?: string) {
  return timestamp && Number.isFinite(Date.parse(timestamp)) ? `${timestamp.replace('T', ' ').replace('Z', '')} UTC` : 'Recording time unavailable';
}
export function activeInterval(clip: ReplayClip, sample?: TelemetrySample): PersistentInterval | undefined {
  return sample && clip.persistent_intervals.find(i => sample.source_row >= i.start_source_row && sample.source_row <= i.end_source_row);
}
export type ReplayAction = 'play' | 'pause' | 'restart' | 'next';
export function transition(state: ReplayState, action: ReplayAction, count: number): ReplayState {
  if (action === 'restart') return { status: 'paused', index: 0 };
  if (action === 'pause') return { ...state, status: state.status === 'ended' ? 'ended' : 'paused' };
  if (action === 'play') return count < 2 || state.index >= count - 1 ? state : { ...state, status: 'playing' };
  if (state.status !== 'playing' || count === 0) return state;
  const index = Math.min(state.index + 1, count - 1);
  return { index, status: index === count - 1 ? 'ended' : 'playing' };
}
export function nextDelay(clip: ReplayClip, index: number) {
  return clip.samples[index + 1] ? clip.samples[index + 1].playback_offset_ms - clip.samples[index].playback_offset_ms : null;
}
export function validateClip(clip: ReplayClip): ReplayClip {
  const fail = () => { throw new Error('Recorded clip failed integrity checks.'); };
  if (clip.schema_version !== 1 || clip.threshold !== FROZEN_THRESHOLD ||
      clip.experiment_id !== '0c777345c64dfeba' || clip.preparation_run_id !== '1d6fc5b045ee25d0' ||
      !Array.isArray(clip.samples) || !Array.isArray(clip.persistent_intervals) ||
      clip.sample_count !== clip.samples.length) fail();
  const seen = new Set<number>();
  clip.samples.forEach((s, n) => {
    const previous = clip.samples[n - 1];
    if (!Number.isSafeInteger(s.source_row) || seen.has(s.source_row) ||
        !Number.isFinite(Date.parse(s.original_timestamp_utc)) || !Number.isFinite(s.playback_offset_ms) ||
        !Number.isInteger(s.quality_flags) || s.quality_flags < 0 ||
        [s.voltage_v, s.temperature_c, s.soc_percent, s.score_samples].some(v => v !== null && !Number.isFinite(v)) ||
        s.unusual !== isUnusual(s.score_samples, clip.threshold) ||
        (n === 0 && s.playback_offset_ms !== 0) ||
        Math.abs(Date.parse(s.original_timestamp_utc) - Date.parse(clip.recorded_start_utc) - s.playback_offset_ms) >= 1 ||
        (previous && (s.source_row <= previous.source_row || s.playback_offset_ms <= previous.playback_offset_ms ||
          s.playback_offset_ms - previous.playback_offset_ms > 1000))) fail();
    seen.add(s.source_row);
  });
  if (clip.samples.length && (clip.samples[0].original_timestamp_utc !== clip.recorded_start_utc ||
      clip.samples.at(-1)!.original_timestamp_utc !== clip.recorded_end_utc ||
      clip.samples.at(-1)!.playback_offset_ms !== clip.recorded_duration_ms)) fail();
  const ids = new Set<string>();
  clip.persistent_intervals.forEach(i => {
    const points = clip.samples.filter(s => s.source_row >= i.start_source_row && s.source_row <= i.end_source_row);
    if (ids.has(i.interval_id) || points.length !== i.row_count || !points.length ||
        points[0].source_row !== i.start_source_row || points.at(-1)!.source_row !== i.end_source_row ||
        points[0].original_timestamp_utc !== i.start_utc || points.at(-1)!.original_timestamp_utc !== i.end_utc ||
        Math.abs((points.at(-1)!.playback_offset_ms - points[0].playback_offset_ms) / 1000 - i.duration_seconds) > 1e-6 ||
        i.duration_seconds < 2 || points.some(s => !s.unusual)) fail();
    ids.add(i.interval_id);
  });
  return clip;
}
