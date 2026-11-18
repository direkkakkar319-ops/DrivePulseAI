// Minimal source/run controls; detailed result presentation belongs to Phase 4.2.
import { AppButton } from '@/components/ui/app-button';
import { AppSelect } from '@/components/ui/app-select';
import { AppText } from '@/components/ui/app-text';
import { AppTextField } from '@/components/ui/app-text-field';
import type { AnalysisController } from '@/hooks/use-analysis';

export function KitAnalysisControls({ analysis }: { analysis: AnalysisController }) {
  const { catalog, source, result } = analysis;
  const selected = catalog.status === 'ready' && source.kind === 'sample'
    ? catalog.data.samples.find(sample => sample.id === source.sampleId) : undefined;
  return <>
    <AppSelect label="Prerecorded KIT sample" value={source.kind === 'sample' ? source.sampleId : null}
      options={catalog.status === 'ready' ? catalog.data.samples.map(sample => ({ value: sample.id, label: sample.display_name })) : []}
      onOpen={() => { void analysis.loadSamples(); }} onSelect={analysis.selectSample}
      loading={catalog.status === 'loading'} loadError={catalog.status === 'error' ? catalog.message : undefined}
      onRetry={() => { void analysis.loadSamples(); }} disabled={analysis.selecting}
      hint="Real recorded combustion-engine telemetry. Independent of your Garage and the simulated demo." />
    {selected && <AppText variant="caption" tone="secondary">{selected.dataset} · {selected.window_count} windows · {selected.valid_pair_count} pairs · {selected.window_seconds}-second windows</AppText>}
    {source.kind === 'csv' && <AppTextField label="Recording date" value={analysis.recordingDate}
      onChangeText={analysis.setRecordingDate} placeholder="YYYY-MM-DD" maxLength={10}
      autoCapitalize="none" autoCorrect={false} editable={!analysis.selecting}
      hint="Enter the actual recording date. It is caller-supplied, not independently verified. UTF-8 KIT raw CSV only; up to 2 MiB under the documented server defaults." />}
    {(source.kind === 'sample' || source.kind === 'csv') && <AppButton
      title={source.kind === 'sample' ? 'Analyze KIT sample' : 'Upload and analyze CSV'}
      loading={result.status === 'loading'} disabled={analysis.selecting} onPress={() => { void analysis.run(); }} />}
    {result.status === 'loading' && <AppButton title="Cancel analysis" variant="text" onPress={analysis.cancel} />}
  </>;
}
