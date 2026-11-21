// Test-only excerpt: real first-pair scores/telemetry, not an advertised backend sample.
import excerpt from './fixtures/kit-first-pair.json';
import type { KitSampleAnalysis, KitUploadedAnalysis } from '../src/types/kit-analysis';
export const sampleResult = () => JSON.parse(JSON.stringify(excerpt)) as KitSampleAnalysis;
export const csvFile = { uri: 'content://documents/drive.csv', name: 'drive.csv', mimeType: 'text/csv', sizeBytes: 1200 };
export function uploadResult(): KitUploadedAnalysis {
  const { sample: _sample, source_type: _kind, ...core } = sampleResult();
  const result: KitUploadedAnalysis = { ...core, source_type: 'uploaded_csv', source: {
    kind: 'uploaded_csv', format_version: 'kit_obd_raw_v1', preprocessing_version: 'kit-10s-window-recipe-v1',
    recording_id: 'upload-contract-fixture', recording_date: '2018-03-20', metadata_verification: 'caller_supplied_unverified',
    input_bytes: 1200, accepted_rows: 2, missing_cells: 0, discarded_incomplete_windows: 0,
    backward_timestamp_jumps: 0, duplicate_timestamp_rows: 0,
  } };
  // Source-only metadata varies for wire-validation tests, not a claimed raw-to-model run.
  for (const window of result.telemetry.map(t => t.window).concat(
    result.predictions.flatMap(p => [p.current_window, p.next_window]), result.score_series.map(p => p.window))) {
    window.recording_id = result.source.recording_id; window.split = 'uploaded';
  }
  return result;
}
