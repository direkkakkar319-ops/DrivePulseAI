import { AppButton } from '@/components/ui/app-button';
import { AppSelect } from '@/components/ui/app-select';
import { AppText } from '@/components/ui/app-text';
import type { AnalysisController } from '@/hooks/use-leaf-analysis';
export function LeafAnalysisControls({ analysis }: { analysis: AnalysisController }) {
  const { catalog, source, result } = analysis;
  const selected = catalog.status === 'ready' && source.kind === 'sample' ? catalog.data.samples.find(s => s.id === source.sampleId) : undefined;
  return <>
    <AppSelect label="Built-in Nissan Leaf sample" value={source.kind === 'sample' ? source.sampleId : null}
      options={catalog.status === 'ready' ? catalog.data.samples.map(s => ({ value: s.id, label: s.display_name })) : []}
      onOpen={() => { void analysis.loadSamples(); }} onSelect={analysis.selectSample} loading={catalog.status === 'loading'}
      loadError={catalog.status === 'error' ? catalog.message : undefined} onRetry={() => { void analysis.loadSamples(); }} disabled={analysis.selecting}
      hint="The built-in fixture is synthetic, not a real vehicle recording. Predictions are calculated by the model." />
    {selected && <AppText variant="caption">{selected.provenance}</AppText>}
    {source.kind === 'csv' && <AppText variant="caption">leaf-csv-v1 · UTF-8 · up to 2 MiB and 256 rows by default. Single Nissan Leaf only. Timestamp must be Unix microseconds. SOC/SOH: %; voltage: V; current: A; pack temperature: °C; odometer: km. See CSV format below.</AppText>}
    {(source.kind === 'sample' || source.kind === 'csv') && <AppButton title={source.kind === 'sample' ? 'Analyze Nissan Leaf sample' : 'Upload and analyze CSV'} loading={result.status === 'loading'} disabled={analysis.selecting} onPress={() => { void analysis.run(); }} />}
    {result.status === 'ready' && <AppButton title="Clear analysis" variant="text" onPress={analysis.cancel} />}
    {result.status === 'loading' && <AppButton title="Cancel analysis" variant="text" onPress={analysis.cancel} />}
    <AppText variant="caption">CSV format: Timestamp plus available exact signal columns. Anomaly: HV_Bat_Voltage, Pack_1_C_Temp, SOC, HV_Bat_Current_2, Pack_2_C_Temp, Pack_4_C_Temp. Health: SOH. RUL: Timestamp, SOH, Odometer; at least 30 observed days spanning 90 days. Missing values are not imputed. Range is unavailable without verified energy and consumption. Not an arbitrary OBD CSV importer.</AppText>
  </>;
}
