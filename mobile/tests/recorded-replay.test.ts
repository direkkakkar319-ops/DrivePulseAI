// Verify real clip integrity and replay semantics without training or inventing vehicle records.
import fixtures from '../src/demo/recorded/clips.json';
import { localRecordedProvider } from '../src/api/recorded-telemetry-provider';
import { activeInterval, FROZEN_THRESHOLD, isUnusual, measurement, nextDelay, recordedTime, transition, validateClip } from '../src/lib/recorded-replay';
import type { ReplayClip, ReplayState } from '../src/types/recorded-telemetry';
const clips = fixtures as ReplayClip[];
const copy = (index = 0): ReplayClip => JSON.parse(JSON.stringify(clips[index]));
it('loads exactly the reviewed source-aligned clips and no fabricated score', async () => {
  expect((await localRecordedProvider.listClips()).map(c => c.clip_id)).toEqual(['leaf-typical', 'leaf-unusual']);
  const a = await localRecordedProvider.getClip('leaf-typical');
  const b = await localRecordedProvider.getClip('leaf-unusual');
  expect([a.samples.length, b.samples.length]).toEqual([211, 205]);
  expect([a.samples[0].source_row, a.samples.at(-1)!.source_row]).toEqual([1637821, 1638031]);
  expect([b.samples[0].source_row, b.samples.at(-1)!.source_row]).toEqual([1759260, 1759464]);
  expect([a.samples.filter(s => s.unusual).length, b.samples.filter(s => s.unusual).length]).toEqual([0, 132]);
  expect([a.persistent_intervals.length, b.persistent_intervals.length]).toEqual([0, 2]);
  for (const c of [a, b]) { expect(validateClip(c)).toBe(c); expect(c.samples.every(s => s.quality_flags === 0)).toBe(true); }
  a.samples[0].voltage_v = null;
  expect((await localRecordedProvider.getClip('leaf-typical')).samples[0].voltage_v).not.toBeNull();
  await expect(localRecordedProvider.getClip('missing')).rejects.toThrow('Recording not found');
});
it('uses the strict frozen threshold and never treats missing scores as normal', () => {
  expect(isUnusual(FROZEN_THRESHOLD)).toBe(false);
  expect(isUnusual(FROZEN_THRESHOLD - 0.000001)).toBe(true);
  expect(isUnusual(null)).toBeNull(); expect(isUnusual(NaN)).toBeNull();
});
it('plays, pauses, advances only one sample, ends and restarts deterministically', () => {
  let s: ReplayState = { index: 0, status: 'paused' };
  expect(transition(s, 'next', 3)).toEqual(s);
  s = transition(s, 'play', 3); s = transition(s, 'next', 3);
  expect(s).toEqual({ index: 1, status: 'playing' });
  s = transition(s, 'pause', 3); expect(transition(s, 'next', 3)).toEqual(s);
  s = transition(transition(s, 'play', 3), 'next', 3);
  expect(s).toEqual({ index: 2, status: 'ended' });
  expect(transition(s, 'play', 3)).toEqual(s);
  expect(transition(s, 'restart', 3)).toEqual({ index: 0, status: 'paused' });
  expect(transition({ index: 0, status: 'paused' }, 'play', 0).status).toBe('paused');
});
it('uses actual irregular offsets, not a fixed quarter-second clock', () => {
  const c = copy(1);
  const delays = c.samples.slice(0, -1).map((_, i) => nextDelay(c, i));
  expect(new Set(delays).size).toBeGreaterThan(1);
  expect(delays.reduce<number>((sum, n) => sum + n!, 0)).toBe(c.recorded_duration_ms);
  expect(nextDelay(c, c.samples.length - 1)).toBeNull();
});
it('honors both interval boundaries and keeps isolated flags separate', () => {
  const clip = copy(1), interval = clip.persistent_intervals[0];
  const at = (row: number) => clip.samples.find(s => s.source_row === row);
  expect(activeInterval(clip, at(interval.start_source_row - 1))).toBeUndefined();
  expect(activeInterval(clip, at(interval.start_source_row))).toEqual(interval);
  expect(activeInterval(clip, at(interval.end_source_row))).toEqual(interval);
  expect(activeInterval(clip, at(interval.end_source_row + 1))).toBeUndefined();
  expect(at(1759309)!.unusual).toBe(true);
  expect(activeInterval(clip, at(1759309))).toBeUndefined();
});
it.each(['order', 'gap', 'score', 'timestamp', 'threshold', 'interval', 'nan'])(
  'rejects malformed %s before presentation', kind => {
    const c = copy(1);
    if (kind === 'order') c.samples[1].playback_offset_ms = 0;
    if (kind === 'gap') c.samples[1].playback_offset_ms += 5000;
    if (kind === 'score') c.samples[0].unusual = !c.samples[0].unusual;
    if (kind === 'timestamp') c.samples[0].original_timestamp_utc = 'invalid';
    if (kind === 'threshold') c.threshold = -0.5;
    if (kind === 'interval') c.persistent_intervals[0].end_source_row++;
    if (kind === 'nan') c.samples[0].voltage_v = Infinity;
    expect(() => validateClip(c)).toThrow();
  },
);
it('formats missing data and preserves original timestamp text', () => {
  expect(measurement(null, 'V')).toBe('Unavailable');
  expect(measurement(Infinity, '%')).toBe('Unavailable');
  expect(measurement(332.12, 'V')).toBe('332.12 V');
  expect(recordedTime('2022-03-17T07:39:06.251000Z')).toContain('07:39:06.251000 UTC');
  const c = copy(); c.samples[0].voltage_v = null; c.samples[0].score_samples = null; c.samples[0].unusual = null;
  expect(validateClip(c)).toBe(c);
});
