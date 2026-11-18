import { useMemo, useState } from 'react';
import { AppButton } from '@/components/ui/app-button';
import { AppCard } from '@/components/ui/app-card';
import { AppSelect } from '@/components/ui/app-select';
import { AppText } from '@/components/ui/app-text';
import { analysisSegments, clock, plotNumber, scorePoints, telemetryPoints } from '@/lib/kit-visualization';
import type { KitAnalysis, KitSignal } from '@/types/kit-analysis';
import { KitLineChart } from './kit-line-chart';

export function KitAnalysisVisualization({ data, section }: { data: KitAnalysis; section: 'scores' | 'telemetry' }) {
  const segments = useMemo(() => analysisSegments(data), [data]);
  const [chosen, setChosen] = useState(''), [signal, setSignal] = useState<KitSignal>('speed_kmph');
  const segment = segments.some(s => s.value === chosen) ? chosen : segments[0]?.value ?? '';
  const scores = useMemo(() => scorePoints(data, segment), [data, segment]);
  const readings = useMemo(() => telemetryPoints(data, segment, signal), [data, segment, signal]);
  const [pairId, setPairId] = useState(''), [intervalPage, setIntervalPage] = useState(0);
  const pair = data.predictions.find(p => p.pair_id === pairId && scores.some(s => s.id === pairId))
    ?? data.predictions.find(p => p.pair_id === scores[0]?.id);
  const definition = data.signals.find(s => s.name === signal);
  const labels = new Map(data.signals.map(s => [s.name, s.display_name]));
  if (!segments.length) return <AppCard><AppText>No prepared telemetry is available for visualization.</AppText></AppCard>;
  return <>
    <AppCard testID={`kit-${section}-visualization`}>
      <AppText variant="subtitle">{section === 'scores' ? 'Novelty timeline' : 'Observed telemetry'}</AppText>
      <AppSelect label={section === 'scores' ? 'Score recording segment' : 'Telemetry recording segment'} value={segment}
        options={segments} onSelect={value => { setChosen(value); setPairId(''); }} />
      <AppText variant="caption" tone="secondary">{data.time_basis}. Segment timelines are separate; source clock resets are never joined.</AppText>
      {section === 'scores' ? <>
        <KitLineChart key={segment} title="Anomaly score" unit="dimensionless" points={scores} threshold={data.summary.threshold}
          onInspect={point => setPairId(point.id)} />
        {pair && <>
          <AppText variant="label">Selected pair: {pair.pair_id}</AppText>
          <AppText variant="caption">Input {pair.current_window.id} → target {pair.next_window.id}</AppText>
          <AppText variant="label">Largest normalized forecast deviations</AppText>
          {pair.top_signal_deviations.map((d, i) => <AppText key={d.signal}>{i + 1}. {labels.get(d.signal)}: {plotNumber(d.normalized_error)} (dimensionless)</AppText>)}
          <AppText variant="caption" tone="secondary">{data.contribution_definition}</AppText>
        </>}
      </> : <>
        <AppSelect label="Telemetry signal" value={signal} options={data.signals.map(s => ({ value: s.name, label: `${s.display_name} (${s.unit})` }))}
          onSelect={value => setSignal(value as KitSignal)} />
        <KitLineChart key={`${segment}:${signal}`} title="Telemetry" unit={definition?.unit ?? ''} points={readings} />
        <AppText variant="caption" tone="secondary">{definition?.display_name}. {data.explanation.measurement_definition}</AppText>
      </>}
    </AppCard>
    {section === 'scores' && <>
      <AppCard>
        <AppText variant="subtitle">Flagged intervals</AppText>
        <AppText variant="caption" tone="secondary">{data.interval_definition}. Times are source clock, not UTC. Flags indicate novelty, not confirmed failures.</AppText>
        {data.flagged_intervals.length === 0 ? <AppText>No target windows exceeded the novelty threshold.</AppText>
          : data.flagged_intervals.slice(intervalPage * 12, (intervalPage + 1) * 12).map((interval, i) => <AppCard key={`${intervalPage}:${i}`}>
            <AppText>{interval.recording_date} · Segment {interval.segment_id}</AppText>
            <AppText>{interval.recording_id}</AppText>
            <AppText>[{clock(interval.start_seconds)}, {clock(interval.end_seconds)}) · {interval.pair_ids.length} flagged pairs</AppText>
            <AppText>Peak score: {plotNumber(interval.peak_anomaly_score)}</AppText>
            <AppText variant="caption">Pairs: {interval.pair_ids.join(', ')}</AppText>
          </AppCard>)}
        {data.flagged_intervals.length > 12 && <>
          <AppText>Interval page {intervalPage + 1} of {Math.ceil(data.flagged_intervals.length / 12)}</AppText>
          <AppButton title="Previous intervals" variant="text" disabled={intervalPage === 0} onPress={() => setIntervalPage(intervalPage - 1)} />
          <AppButton title="Next intervals" variant="text" disabled={(intervalPage + 1) * 12 >= data.flagged_intervals.length} onPress={() => setIntervalPage(intervalPage + 1)} />
        </>}
      </AppCard>
      <AppCard>
        <AppText variant="subtitle">Actual vs predicted values</AppText>
        <AppText>Forecast values are not included in this API response. A comparison graph is unavailable.</AppText>
        <AppText tone="secondary">The backend returns observed medians and normalized forecast errors. Errors cannot reconstruct the model predictions.</AppText>
      </AppCard>
      <AppCard>
        <AppText variant="subtitle">Model and interpretation</AppText>
        <AppText>Model: {data.model.model_version}</AppText>
        <AppText>Forecast horizon: next {data.window_seconds}-second window medians</AppText>
        <AppText>{data.explanation.signal_summary}</AppText>
        <AppText tone="secondary">{data.explanation.score_definition}</AppText>
        <AppText tone="secondary">{data.explanation.threshold_definition}</AppText>
        <AppText tone="secondary">{data.explanation.signal_definition}</AppText>
        <AppText tone="secondary">{data.explanation.limitations}</AppText>
        {data.limitations.map((text, i) => <AppText key={i} variant="caption" tone="secondary">{text}</AppText>)}
      </AppCard>
    </>}
  </>;
}
