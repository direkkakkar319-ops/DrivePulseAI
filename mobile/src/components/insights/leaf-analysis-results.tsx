import { useState } from 'react';
import { AppButton } from '@/components/ui/app-button';
import { AppCard } from '@/components/ui/app-card';
import { AppDataState } from '@/components/ui/app-data-state';
import { AppText } from '@/components/ui/app-text';
import { AppSelect } from '@/components/ui/app-select';
import type { AnalysisController } from '@/hooks/use-leaf-analysis';
import type { Capability, LeafAnalysis, RulConfidenceInterval } from '@/types/leaf-analysis';
import { LeafReadingChart } from './leaf-reading-chart';
function CapabilityResult({ title, capability }: { title: string; capability: Capability }) {
  const ci = capability.result?.confidence_interval as RulConfidenceInterval | null | undefined;
  return <AppCard><AppText variant="subtitle">{title}</AppText><AppText>{capability.status.replaceAll('_', ' ')}</AppText>
    {capability.reason && <AppText>{capability.reason}</AppText>}
    {capability.result && Object.entries(capability.result).filter(([key]) => !['bands', 'context_summary', 'limitations', 'schema_version', 'assessment_type', 'confidence_interval'].includes(key)).map(([key, value]) =>
      <AppText key={key} variant="caption">{key.replaceAll('_', ' ')}: {value === null ? 'Unavailable' : String(value)}</AppText>)}
    {ci && <><AppText>{ci.level_pct}% bootstrap interval: {ci.rul_km_p10.toPrecision(5)}–{ci.rul_km_p90.toPrecision(5)} km · median {ci.rul_km_p50.toPrecision(5)} km</AppText><AppText variant="caption">Valid bootstrap fits: {ci.bootstrap_iterations_valid}. Experimental sample-based uncertainty, not validated failure confidence; unobserved late-life changes are not covered.</AppText>{ci.estimated_days_p10 != null && ci.estimated_days_p90 != null && <AppText variant="caption">Estimated calendar interval: {ci.estimated_days_p10.toPrecision(5)}–{ci.estimated_days_p90.toPrecision(5)} days</AppText>}</>}
    {capability.result && Array.isArray(capability.result.bands) && capability.result.bands.map((band, i) => <AppText key={i} variant="caption">SOH {(band as Record<string, unknown>).minimum_soh_pct as number}–{(band as Record<string, unknown>).maximum_soh_pct as number}% · score {(band as Record<string, unknown>).score as number}</AppText>)}
  </AppCard>;
}
export function LeafResults({ data, telemetryOnly = false }: { data: LeafAnalysis; telemetryOnly?: boolean }) {
  const signals = Object.keys(data.units), [signal, setSignal] = useState(signals[0] ?? 'SOC'), [page, setPage] = useState(0);
  const flagged = data.anomaly.results.filter(p => p.is_unusual), pages = Math.max(1, Math.ceil(flagged.length / 8));
  const flags = new Set(flagged.map(p => p.row_id));
  if (telemetryOnly) return <AppCard>
    <AppSelect label="Recorded signal" value={signal} options={signals.map(name => ({ value: name, label: `${name} · ${data.units[name]}` }))} onSelect={setSignal} />
    <LeafReadingChart key={signal} title={signal} unit={data.units[signal] ?? ''} points={data.telemetry.map(r => ({ row_id: r.row_id, timestamp_us: r.timestamp_us, value: r.values[signal] ?? null, unusual: flags.has(r.row_id) }))} />
    <AppText variant="caption">Original recorded values, not model forecasts. Times are Unix timestamps displayed in UTC.</AppText>
  </AppCard>;
  return <>
    <AppCard testID="leaf-analysis-summary">
      <AppText variant="subtitle">{data.source.synthetic ? data.anomaly.status === 'completed' ? 'Synthetic integration input · genuine model inference' : 'Synthetic integration input · anomaly analysis unavailable' : 'Uploaded Nissan Leaf telemetry'}</AppText>
      <AppText>{data.source.provenance}</AppText>
      <AppText>SOC: {data.battery.latest_soc === null ? 'Unavailable' : `${data.battery.latest_soc}%`}</AppText>
      <AppText>SOH: {data.battery.latest_soh === null ? 'Unavailable' : `${data.battery.latest_soh}%`}</AppText>
      <AppText>Estimated driving range: Unavailable</AppText><AppText variant="caption">{data.battery.range_reason}</AppText>
      <AppText>{data.recording.reading_count} timestamp-valid readings · {data.recording.skipped_timestamp_rows} skipped timestamp rows · {data.recording.missing_or_invalid_cells} missing/invalid cells</AppText>
      <AppText>Transient analysis · Not saved · Not linked to Garage</AppText>
    </AppCard>
    <AppCard><AppText variant="subtitle">Telemetry novelty detection</AppText><AppText>{data.anomaly.status}</AppText>
      {data.anomaly.reason && <AppText>{data.anomaly.reason}</AppText>}
      <AppText>{data.anomaly.unusual_count} unusual of {data.anomaly.analyzed_count} analyzed · {data.anomaly.unusual_percentage.toFixed(2)}% · {data.anomaly.skipped_count} skipped</AppText>
      <AppText variant="caption">Lower scores are more unusual. Flagged only when score is strictly below the threshold. Not a fault probability.</AppText>
      <AppText variant="caption">{data.anomaly.model_version ?? 'Model unavailable'} · {data.anomaly.explanation_status ?? 'No explanations available'}</AppText>
      {data.anomaly.status === 'completed' && <LeafReadingChart title="Anomaly score" unit="score" threshold={data.anomaly.threshold!} points={data.anomaly.results.map(p => ({ ...p, value: p.anomaly_score, unusual: p.is_unusual }))} />}
    </AppCard>
    <AppCard><AppText variant="subtitle">Unusual readings and SHAP</AppText>
      {!flagged.length && <AppText>{data.anomaly.status === 'completed' ? 'No readings flagged. SHAP is computed only for unusual readings.' : 'No unusual-reading results available.'}</AppText>}
      {flagged.slice(Math.min(page, pages - 1)*8, Math.min(page, pages - 1)*8+8).map(p => <AppCard key={p.row_id}>
        <AppText>Row {p.row_id} · {new Date(p.timestamp_us / 1000).toISOString()} · score {p.anomaly_score.toPrecision(5)}</AppText>
        {p.explanation?.contributions.map(c => <AppText key={c.feature}>{c.rank}. {c.feature}: {c.measured_value} {data.units[c.feature]} · SHAP {c.shap_value.toPrecision(4)} · {c.shap_value === 0 ? 'Neutral contribution' : c.direction.replaceAll('_', ' ')}</AppText>)}
        {p.explanation && <AppText variant="caption">Baseline score: {p.explanation.baseline_score.toPrecision(5)}. {p.explanation.interpretation}</AppText>}
      </AppCard>)}
      {pages > 1 && <><AppButton title="Previous unusual readings" disabled={page === 0} onPress={() => setPage(page-1)} /><AppText>Page {page+1}/{pages}</AppText><AppButton title="Next unusual readings" disabled={page >= pages-1} onPress={() => setPage(page+1)} /></>}
      <AppText variant="caption">Top three local score contributions only; omitted contributions prevent a complete additive reconstruction. SHAP is not a physical fault diagnosis.</AppText>
    </AppCard>
    <CapabilityResult title="Battery health · SOH bands, not a trained prediction" capability={data.health} />
    <CapabilityResult title="Experimental RUL · distance to SOH threshold" capability={data.rul} />
    <AppCard><AppText variant="subtitle">Data quality and limitations</AppText>{[...data.warnings, ...data.limitations].map((text, i) => <AppText key={i} variant="caption">{text}</AppText>)}</AppCard>
  </>;
}
export function LeafAnalysisFeedback({ analysis }: { analysis: AnalysisController }) {
  if (analysis.result.status === 'loading') return <AppCard><AppDataState status="loading" title="Running Nissan Leaf analysis" message="Requesting genuine model results. SHAP may take longer for unusual readings. You can cancel." /></AppCard>;
  if (analysis.result.status === 'error') return <AppCard><AppDataState status="error" title="Analysis unavailable" message={analysis.result.message} retryLabel="Retry analysis" onRetry={() => { void analysis.run(); }} /></AppCard>;
  return analysis.result.status === 'ready' ? <LeafResults key={analysis.source.kind} data={analysis.result.data} /> : null;
}
