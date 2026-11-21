// Display-only mapping: retain backend order, source clock and discontinuities.
import type { KitAnalysis, KitWindowReference } from '@/types/kit-analysis';

export const CHART_PAGE_SIZE = 48;
export interface PlotPoint {
  id: string; window: KitWindowReference; value: number | null;
  flagged?: boolean; threshold?: number; missingFraction?: number;
}
export function segmentKey(w: Pick<KitWindowReference, 'recording_id' | 'recording_date' | 'split' | 'segment_id'>): string {
  return JSON.stringify([w.recording_id, w.recording_date, w.split, w.segment_id]);
}
export function analysisSegments(data: KitAnalysis) {
  const seen = new Set<string>();
  return data.telemetry.flatMap(({ window }) => {
    const value = segmentKey(window);
    if (seen.has(value)) return [];
    seen.add(value);
    return [{ value, label: `${window.recording_date} · Segment ${window.segment_id} · ${window.recording_id}` }];
  });
}
export function scorePoints(data: KitAnalysis, segment: string): PlotPoint[] {
  return data.score_series.filter(p => segmentKey(p.window) === segment).map(p => ({
    id: p.pair_id, window: p.window, value: p.anomaly_score, flagged: p.is_novel, threshold: p.threshold,
  }));
}
export function telemetryPoints(data: KitAnalysis, segment: string, signal: keyof KitAnalysis['telemetry'][number]['medians']): PlotPoint[] {
  return data.telemetry.filter(p => segmentKey(p.window) === segment).map(p => ({
    id: p.window.id, window: p.window,
    value: Number.isFinite(p.medians[signal]) ? p.medians[signal] : null,
    missingFraction: p.missing_fractions[signal] ?? 0,
    flagged: data.flagged_intervals.some(i => segmentKey(i) === segment
      && p.window.start_seconds >= i.start_seconds && p.window.start_seconds < i.end_seconds),
  }));
}
export function clock(seconds: number): string {
  const h = Math.floor(seconds / 3600), m = Math.floor(seconds % 3600 / 60), s = seconds % 60;
  return [h, m, s].map(n => String(n).padStart(2, '0')).join(':');
}
export function plotNumber(value: number): string {
  if (value !== 0 && (Math.abs(value) < 0.001 || Math.abs(value) >= 100000)) return value.toExponential(2);
  return Number(value.toFixed(3)).toString();
}
/** Missing values, temporal gaps and identity changes start a new path. */
export function lineRuns(points: PlotPoint[]): PlotPoint[][] {
  const runs: PlotPoint[][] = [];
  let previous: PlotPoint | undefined;
  for (const point of points) {
    if (point.value === null || !Number.isFinite(point.value)) { previous = undefined; continue; }
    if (!previous || segmentKey(previous.window) !== segmentKey(point.window)
      || previous.window.end_seconds !== point.window.start_seconds) runs.push([]);
    runs[runs.length - 1].push(point); previous = point;
  }
  return runs;
}
