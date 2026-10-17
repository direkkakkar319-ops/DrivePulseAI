// Overview, telemetry, insights and replay share a provider and the same recorded observation.
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useReplay } from '@/store/recordedReplayStore';
import { activeInterval, measurement, recordedTime, validateClip } from '@/lib/recorded-replay';
import type { ApiState, ReplayClip } from '@/types/recorded-telemetry';
import { Button, Copy, DataGate, Measurements, Page, Panel, Recording, Score, SectionHeader, StatusPill, ui } from './ui';
import { channels, TelemetryChart } from './telemetry-chart';
import { colors, radius, spacing, type } from './theme';
const detailRoute = (clipId: string, id: string) => ({ pathname: '/(main)/recorded-insight/[id]' as const, params: { id, clipId } });
export function OverviewScreen() {
  const router = useRouter();
  const { replay } = useReplay();
  return <Page title="Battery overview"><DataGate>{(clip, sample) => <>
    <Recording clip={clip} sample={sample} />
    <View style={[ui.row, { justifyContent: 'space-between' }]}>
      <Copy muted style={type.caption}>REPLAY STATUS</Copy>
      <StatusPill label={replay.status === 'playing' ? 'Playing recording' : replay.status === 'ended' ? 'Playback complete' : 'Paused'} />
    </View>
    <SectionHeader eyebrow="Current sample" title="Battery telemetry" detail="Measurements at the original recording timestamp shown above." />
    <Measurements sample={sample} />
    <SectionHeader eyebrow="Experimental model" title="Anomaly observation" />
    <Score clip={clip} sample={sample} />
    <Button title="Open recorded replay" onPress={() => router.push('/(main)/replay')} />
    <View style={styles.actionRow}>
      <Button title="View telemetry" secondary style={styles.actionButton} onPress={() => router.push('/(main)/(tabs)/telemetry')} />
      <Button title="View insights" secondary style={styles.actionButton} onPress={() => router.push('/(main)/(tabs)/insights')} />
    </View>
    <Copy muted style={type.caption}>Recorded research telemetry with saved experimental ML results. No live vehicle connection.</Copy>
  </>}</DataGate></Page>;
}
export function TelemetryScreen() {
  const { replay } = useReplay();
  const router = useRouter();
  return <Page title="Telemetry"><DataGate>{(clip, sample) => <>
    <Recording clip={clip} sample={sample} />
    <SectionHeader title="Recorded history" detail="Charts include observations up to the current replay position. Values use their original timestamps." />
    {channels.map(channel => <Panel key={channel.key}>
      <View style={[ui.row, { justifyContent: 'space-between' }]}>
        <View style={{ flex: 1, minWidth: 150 }}><Copy style={type.section}>{channel.label}</Copy><Copy muted style={type.caption}>CURRENT RECORDED VALUE</Copy></View>
        <Copy style={styles.chartValue}>{measurement(sample[channel.key], channel.unit)}</Copy>
      </View>
      <View style={ui.divider} />
      <TelemetryChart samples={clip.samples.slice(0, replay.index + 1)} channel={channel} intervals={clip.persistent_intervals} />
    </Panel>)}
    <Button title="Replay controls" onPress={() => router.push('/(main)/replay')} />
    <Copy muted style={type.caption}>{clip.vehicle.recording_source} · {clip.source_dataset}</Copy>
  </>}</DataGate></Page>;
}
export function InsightsScreen() {
  const router = useRouter();
  return <Page title="Insights"><DataGate>{(clip, sample) => <>
    <Recording clip={clip} sample={sample} />
    <Panel style={styles.scientificNote}>
      <Copy style={type.section}>How to read these results</Copy>
      <Copy muted>Isolation Forest identifies statistical patterns that differ from its training distribution. An unusual score is not a confirmed fault, diagnosis, failure probability, or battery-health estimate.</Copy>
      <Copy muted style={type.caption}>Frozen rule: score_samples &lt; {clip.threshold}</Copy>
    </Panel>
    <View style={styles.summaryRow}>
      <SummaryStat label="FLAGGED SAMPLES" value={String(clip.samples.filter(row => row.unusual).length)} />
      <SummaryStat label="PERSISTENT INTERVALS" value={String(clip.persistent_intervals.length)} />
    </View>
    <SectionHeader eyebrow="Full recording" title="Persistent intervals" detail="A persistent interval contains consecutive unusual samples lasting at least 2 seconds. Individual flagged samples remain visible during replay." />
    {!clip.persistent_intervals.length && <Panel><Copy>No persistent unusual intervals in this clip.</Copy><Copy muted>This does not establish that the battery is healthy.</Copy></Panel>}
    {clip.persistent_intervals.map((interval, index) => <Panel key={interval.interval_id} style={styles.intervalPanel}>
      <View style={[ui.row, { justifyContent: 'space-between' }]}><StatusPill label={`Persistent interval ${index + 1}`} unusual /><Copy muted style={type.caption}>TRIP {clip.trip_id}</Copy></View>
      <Copy style={type.section}>Unusual battery telemetry pattern</Copy>
      <Copy>{recordedTime(interval.start_utc)}</Copy>
      <View style={styles.detailGrid}><Detail label="DURATION" value={measurement(interval.duration_seconds, 's', 3)} /><Detail label="OBSERVATIONS" value={String(interval.row_count)} /></View>
      <Copy muted style={type.caption}>Saved score range {measurement(interval.score_min, '', 6)} to {measurement(interval.score_max, '', 6)}</Copy>
      <Button title="View interval details" secondary onPress={() => router.push(detailRoute(clip.clip_id, interval.interval_id))} />
    </Panel>)}
    <Button title="Choose a recording" secondary onPress={() => router.push('/(main)/replay')} />
  </>}</DataGate></Page>;
}
export function ReplayScreen() {
  const { catalog, selectClip, selectedId, replay, dispatch } = useReplay();
  const router = useRouter();
  return <Page title="Recorded replay" back>
    <SectionHeader title="Choose a recording" detail="Playback uses original sample timing and saved Isolation Forest scores." />
    {catalog.status === 'ready' && <View style={{ gap: spacing.sm }}>{catalog.data.map(clip => {
      const selected = selectedId === clip.clip_id;
      return <Pressable key={clip.clip_id} accessibilityRole="radio" accessibilityState={{ selected }} accessibilityLabel={`${clip.title}, Trip ${clip.trip_id}, ${clip.sample_count} observations`} onPress={() => { void selectClip(clip.clip_id); }} style={({ pressed }) => [styles.clipOption, selected && styles.clipOptionSelected, pressed && { opacity: 0.78 }]}>
        <View style={{ flex: 1, gap: spacing.xxs }}><Copy style={{ fontWeight: '600' }}>{clip.title} · Trip {clip.trip_id}</Copy><Copy muted style={type.caption}>{clip.sample_count} observations · {measurement(clip.recorded_duration_ms / 1000, 's', 3)}</Copy></View>
        <View style={[styles.radio, selected && styles.radioSelected]}>{selected && <View style={styles.radioDot} />}</View>
      </Pressable>;
    })}</View>}
    <DataGate>{(clip, sample) => {
      const interval = activeInterval(clip, sample);
      const progress = clip.recorded_duration_ms ? sample.playback_offset_ms / clip.recorded_duration_ms : 0;
      return <><Recording clip={clip} sample={sample} />
        <Panel style={styles.playbackPanel} accessibilityLabel={`Replay ${replay.status}, sample ${replay.index + 1} of ${clip.sample_count}`}>
          <View style={[ui.row, { justifyContent: 'space-between' }]}><StatusPill label={replay.status === 'playing' ? 'Playing' : replay.status === 'ended' ? 'Playback complete' : 'Paused'} /><Copy style={styles.elapsed}>{measurement(sample.playback_offset_ms / 1000, 's', 3)} / {measurement(clip.recorded_duration_ms / 1000, 's', 3)}</Copy></View>
          <View accessibilityRole="progressbar" accessibilityLabel="Recorded replay progress" accessibilityValue={{ min: 0, max: 100, now: Math.round(progress * 100) }} style={styles.progressTrack}><View style={[styles.progressFill, { width: `${progress * 100}%` }]} /></View>
          <View style={styles.actionRow}><Button title={replay.status === 'playing' ? 'Pause' : 'Play'} style={styles.actionButton} disabled={replay.status === 'ended' || clip.samples.length < 2} onPress={() => dispatch(replay.status === 'playing' ? 'pause' : 'play')} /><Button title="Restart" style={styles.actionButton} secondary onPress={() => dispatch('restart')} /></View>
          {replay.status === 'ended' && <Copy style={{ color: colors.typical, fontWeight: '600' }}>Playback complete. Restart to review the recording again.</Copy>}
          <Copy muted style={type.caption}>Sample {replay.index + 1} of {clip.sample_count} · Source row {sample.source_row} · Elapsed replay time follows the recorded offsets.</Copy>
        </Panel><Measurements sample={sample} /><Score clip={clip} sample={sample} />
        {interval && <Button title="Open active interval" onPress={() => router.push(detailRoute(clip.clip_id, interval.interval_id))} />}
        <Button title="Telemetry history" secondary onPress={() => router.push('/(main)/(tabs)/telemetry')} /><Button title="All saved insights" secondary onPress={() => router.push('/(main)/(tabs)/insights')} />
      </>;
    }}</DataGate>
  </Page>;
}
export function InsightDetailScreen() {
  const { id, clipId } = useLocalSearchParams<{ id: string; clipId: string }>();
  return <InsightDetails key={`${clipId}/${id}`} clipId={clipId} id={id} />;
}
function InsightDetails({ clipId, id }: { clipId?: string; id?: string }) {
  const { provider } = useReplay();
  const [state, setState] = useState<ApiState<ReplayClip>>(
    clipId ? { status: 'loading' } : { status: 'error', message: 'This link does not identify a recording.' },
  );
  useEffect(() => {
    let active = true;
    if (!clipId) return;
    void provider.getClip(clipId).then(clip => {
      validateClip(clip);
      if (clip.clip_id !== clipId) throw new Error('Recording identity mismatch.');
      if (active) setState({ status: 'ready', data: clip });
    }).catch(() => { if (active) setState({ status: 'error', message: 'Recording unavailable. Return to Insights and choose an interval.' }); });
    return () => { active = false; };
  }, [provider, clipId]);
  const clip = state.status === 'ready' ? state.data : undefined;
  const interval = clip?.persistent_intervals.find(i => i.interval_id === id);
  const points = clip && interval ? clip.samples.filter(s => s.source_row >= interval.start_source_row && s.source_row <= interval.end_source_row) : [];
  return <Page title="Experimental observation" back>
    {state.status === 'loading' ? <Copy>Loading observation…</Copy> : !clip || !interval ? <Panel><Copy>{state.status === 'error' ? state.message : 'Interval unavailable for this recording.'}</Copy></Panel> : <>
      <Recording clip={clip} />
      <StatusPill label="Persistent unusual interval" unusual />
      <SectionHeader title="Unusual battery telemetry pattern" detail="The charts below show this interval highlighted within the complete recorded clip." />
      <Panel>
        <Detail label="START" value={recordedTime(interval.start_utc)} />
        <View style={ui.divider} />
        <Detail label="END" value={recordedTime(interval.end_utc)} />
        <View style={styles.detailGrid}><Detail label="DURATION" value={measurement(interval.duration_seconds, 's', 3)} /><Detail label="OBSERVATIONS" value={String(interval.row_count)} /></View>
        <Copy muted style={type.caption}>Source rows {interval.start_source_row}–{interval.end_source_row}</Copy>
      </Panel>
      <Panel style={styles.scientificNote}><Copy style={type.section}>Model interpretation</Copy><Copy>Saved score range: {measurement(interval.score_min, '', 6)} to {measurement(interval.score_max, '', 6)}</Copy><Copy muted>Frozen rule: score &lt; {clip.threshold}</Copy>
        <Copy muted>The model identifies an unusual statistical combination of voltage, temperature and SOC. It does not establish a cause or verify a mechanical fault.</Copy>
        <Copy muted>{points.every(s => s.quality_flags === 0) ? 'No preparation quality flags in this interval. This is not proof of sensor accuracy.' : 'Preparation quality flags are present; interpretation requires review.'}</Copy>
      </Panel>
      <Copy style={{ fontWeight: '600' }}>Observed ranges and full clip context</Copy>
      {channels.map(channel => {
        const values = points.map(p => p[channel.key]).filter((v): v is number => v !== null && Number.isFinite(v));
        return <Panel key={channel.key}><View style={[ui.row, { justifyContent: 'space-between' }]}><Copy style={type.section}>{channel.label}</Copy><Copy style={styles.range}>{values.length ? `${measurement(Math.min(...values), channel.unit)} – ${measurement(Math.max(...values), channel.unit)}` : 'Unavailable'}</Copy></View><TelemetryChart samples={clip.samples} channel={channel} intervals={[interval]} /></Panel>;
      })}
      <Panel><Copy style={type.section}>Recording provenance</Copy><Copy muted>{clip.vehicle.recording_source}</Copy><Copy muted>{clip.source_dataset}</Copy><Copy muted style={type.caption}>Experiment {clip.experiment_id}</Copy><Copy muted style={type.caption}>Preparation {clip.preparation_run_id}</Copy></Panel>
    </>}
  </Page>;
}

function SummaryStat({ label, value }: { label: string; value: string }) {
  return <View style={styles.summaryStat} accessible accessibilityLabel={`${label}: ${value}`}><Copy muted style={type.caption}>{label}</Copy><Copy style={styles.summaryValue}>{value}</Copy></View>;
}
function Detail({ label, value }: { label: string; value: string }) {
  return <View style={{ flex: 1, minWidth: 120, gap: spacing.xxs }}><Copy muted style={type.caption}>{label}</Copy><Copy style={{ fontWeight: '600', fontVariant: ['tabular-nums'] }}>{value}</Copy></View>;
}

const styles = StyleSheet.create({
  actionRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  actionButton: { flex: 1, minWidth: 132 },
  chartValue: { ...type.metric, fontVariant: ['tabular-nums'], textAlign: 'right' },
  scientificNote: { backgroundColor: colors.surfaceMuted },
  summaryRow: { flexDirection: 'row', gap: spacing.sm },
  summaryStat: { flex: 1, minWidth: 130, borderTopWidth: 2, borderTopColor: colors.accent, paddingTop: spacing.sm, gap: spacing.xxs },
  summaryValue: { fontSize: 26, lineHeight: 32, fontWeight: '600', fontVariant: ['tabular-nums'] },
  intervalPanel: { borderLeftWidth: 3, borderLeftColor: colors.unusual },
  detailGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.md },
  clipOption: { minHeight: 64, padding: spacing.md, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surface, flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  clipOptionSelected: { borderColor: colors.accent, backgroundColor: colors.accentSoft },
  radio: { width: 22, height: 22, borderRadius: 11, borderWidth: 2, borderColor: colors.borderStrong, alignItems: 'center', justifyContent: 'center' },
  radioSelected: { borderColor: colors.accent },
  radioDot: { width: 10, height: 10, borderRadius: 5, backgroundColor: colors.accent },
  playbackPanel: { gap: spacing.md },
  elapsed: { fontWeight: '600', fontVariant: ['tabular-nums'] },
  progressTrack: { height: 8, borderRadius: radius.pill, backgroundColor: colors.border, overflow: 'hidden' },
  progressFill: { height: 8, borderRadius: radius.pill, backgroundColor: colors.accent },
  range: { fontWeight: '600', fontVariant: ['tabular-nums'] },
});
