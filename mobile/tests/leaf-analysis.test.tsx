import { act, fireEvent, render, renderHook, screen } from '@testing-library/react-native';
import { authService } from '../src/api/auth';
import { analysisApi, AnalysisCancelled } from '../src/api/leaf-analysis';
import { parseLeafAnalysis, parseLeafCatalog } from '../src/lib/leaf-analysis';
import { useLeafAnalysis } from '../src/hooks/use-leaf-analysis';
import { LeafResults } from '../src/components/insights/leaf-analysis-results';
import { readingRuns, LeafReadingChart } from '../src/components/insights/leaf-reading-chart';
import { csvFile, sampleResult, uploadResult, leafSample } from './leaf-fixtures';
import type { LeafAnalysis } from '../src/types/leaf-analysis';

jest.mock('../src/api/auth', () => ({ authService: { subscribe: jest.fn(), getToken: jest.fn() } }));
jest.mock('../src/api/client', () => ({ ...jest.requireActual('../src/api/client'), API_BASE_URL: 'https://api.example.test' }));
const oldFetch = global.fetch;
beforeEach(() => { jest.clearAllMocks(); jest.mocked(authService.subscribe).mockImplementation(listener => { listener({ uid: 'alice', emailVerified: true, email: 'unit@example.test', displayName: null }); return () => {}; }); jest.mocked(authService.getToken).mockResolvedValue('unit-token'); });
afterEach(() => { global.fetch = oldFetch; });
const response = (data: unknown) => ({ ok: true, status: 200, json: async () => data }) as Response;
const context = { uid: 'alice' };
function api() { return { samples: jest.fn(async () => ({ schema_version: 1 as const, samples: [leafSample] })), sample: jest.fn(async () => sampleResult()), upload: jest.fn(async () => uploadResult()) }; }
it('validates the catalog and rejects obsolete KIT payloads', () => { expect(parseLeafCatalog({ schema_version: 1, samples: [leafSample] }).samples[0].synthetic).toBe(true); expect(() => parseLeafAnalysis({ analysis_type: 'kit_telemetry_novelty' })).toThrow(); expect(parseLeafAnalysis(sampleResult()).persisted).toBe(false); });
it.each(['direction','identity','count','infinity','percentage','timestamp'])('rejects incompatible %s results', failure => {
  const value = sampleResult();
  if (failure === 'direction') value.anomaly.results[0].is_unusual = true;
  if (failure === 'identity') value.anomaly.results[0].row_id = 2;
  if (failure === 'count') value.anomaly.analyzed_count = 2;
  if (failure === 'infinity') value.anomaly.results[0].anomaly_score = Infinity;
  if (failure === 'percentage') value.anomaly.unusual_percentage = 100;
  if (failure === 'timestamp') value.telemetry[0].timestamp_us = 1704067200;
  expect(() => parseLeafAnalysis(value)).toThrow();
});
it('refreshes Firebase on 401 and never sends an ML key', async () => {
  global.fetch = jest.fn().mockResolvedValueOnce({ ok: false, status: 401 }).mockResolvedValueOnce(response({ schema_version: 1, samples: [leafSample] }));
  expect((await analysisApi.samples(context)).samples[0].id).toBe(leafSample.id);
  expect(authService.getToken).toHaveBeenNthCalledWith(1, false); expect(authService.getToken).toHaveBeenNthCalledWith(2, true);
  expect(fetch).toHaveBeenLastCalledWith('https://api.example.test/api/v1/analysis/samples', expect.objectContaining({ headers: { Authorization: 'Bearer unit-token', Accept: 'application/json' } }));
});
it('fails safely on malformed responses and network errors', async () => {
  global.fetch = jest.fn().mockResolvedValueOnce(response({ results: [] })).mockRejectedValueOnce(new Error('private network detail'));
  await expect(analysisApi.sample(leafSample.id,context)).rejects.toThrow('incompatible response');
  await expect(analysisApi.samples(context)).rejects.toThrow('Could not reach');
});
it('cancels before token acquisition', async () => { const controller = new AbortController(); controller.abort(); global.fetch = jest.fn(); await expect(analysisApi.samples({ ...context, signal: controller.signal })).rejects.toBeInstanceOf(AnalysisCancelled); expect(fetch).not.toHaveBeenCalled(); });
it('invalidates pending results after source and account changes', async () => {
  const client = api(); let finish!: (value: LeafAnalysis) => void;
  client.sample.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
  const hook = await renderHook(({ uid }: { uid: string | null }) => useLeafAnalysis(uid, false, undefined, client), { initialProps: { uid: 'alice' as string | null } });
  await act(() => hook.result.current.loadSamples()); await act(() => hook.result.current.selectSample(leafSample.id));
  let running!: Promise<void>; await act(() => { running = hook.result.current.run(); });
  await act(() => hook.result.current.useDemo(true)); await act(async () => { finish(sampleResult()); await running; });
  expect(hook.result.current.result.status).toBe('idle'); expect(hook.result.current.source.kind).toBe('demo');
  await hook.rerender({ uid: 'bob' }); expect(hook.result.current.source.kind).toBe('none');
  await hook.rerender({ uid: null }); expect(hook.result.current.result.status).toBe('idle');
});
it('uses CSV timestamps directly without a caller recording_date', async () => { const client = api(); const hook = await renderHook(() => useLeafAnalysis('alice',false,async () => csvFile,client)); await act(() => hook.result.current.selectCsv()); await act(() => hook.result.current.run()); expect(client.upload).toHaveBeenCalledWith(csvFile,expect.objectContaining({ uid:'alice' })); });
it('renders missing SOH, unavailable range and honest experimental statuses', async () => { const data=sampleResult(); await render(<LeafResults data={data} />); expect(screen.getByText('SOH: Unavailable')).toBeTruthy(); expect(screen.getByText('Estimated driving range: Unavailable')).toBeTruthy(); expect(screen.getByText('No valid reported SOH measurement')).toBeTruthy(); expect(screen.getByText('Experimental RUL · distance to SOH threshold')).toBeTruthy(); expect(screen.getByText('No readings flagged. SHAP is computed only for unusual readings.')).toBeTruthy(); });
it('renders actual supplied SHAP fields and validates their mapping', async () => {
  const data=sampleResult(), prediction=data.anomaly.results[0]; prediction.is_unusual=true; prediction.anomaly_score=-0.7; data.anomaly.unusual_count=1; data.anomaly.unusual_percentage=100;
  prediction.explanation={ method:'shap_permutation',output:'score_samples',baseline_score:-0.4,interpretation:'Not physical cause',contributions:[{rank:1,feature:'HV_Bat_Voltage',measured_value:360,shap_value:-0.2,direction:'toward_anomaly'},{rank:2,feature:'SOC',measured_value:70,shap_value:-0.1,direction:'toward_anomaly'},{rank:3,feature:'Pack_1_C_Temp',measured_value:25,shap_value:0,direction:'toward_typical'}] };
  expect(parseLeafAnalysis(data)).toBe(data); await render(<LeafResults data={data} />); expect(screen.getByText(/1. HV_Bat_Voltage: 360/)).toBeTruthy(); expect(screen.getByText(/Neutral contribution/)).toBeTruthy();
  prediction.explanation.contributions[0].measured_value=999; expect(() => parseLeafAnalysis(data)).toThrow();
});
it('breaks lines at missing readings, skipped rows and clock reversals', () => { const base={row_id:1,timestamp_us:1704067200000000,value:0}; expect(readingRuns([base,{...base,row_id:2,value:null},{...base,row_id:3,timestamp_us:base.timestamp_us+500000},{...base,row_id:4,timestamp_us:base.timestamp_us-1000000}])).toHaveLength(3); });
it('paginates large results and inspects source readings', async () => { const points=Array.from({length:1000},(_,i)=>({row_id:i+1,timestamp_us:1704067200000000+i*250000,value:i===0?null:-0.5})); await render(<LeafReadingChart title="Test score" unit="score" points={points} threshold={-0.6} />); expect(screen.getByText(/Page 1\/21/)).toBeTruthy(); expect(screen.getByText(/Measurement unavailable/)).toBeTruthy(); await fireEvent.press(screen.getByRole('button',{name:'Next Test score page'})); expect(screen.getByText(/Page 2\/21/)).toBeTruthy(); expect(screen.getByTestId('leaf-threshold')).toBeTruthy(); });

function resultWithInterval() {
  const data = sampleResult();
  data.rul = { status: 'completed', reason: null, result: {
    schema_version: 1, model_version: 'nissan-leaf-soh-theilsen-v1', status: 'ok', rul_km: 1000,
    rul_km_p10: 800, rul_km_p50: 1000, rul_km_p90: 1200, limitations: ['Synthetic protocol fixture, not a prediction'],
    confidence_interval: { level_pct: 80, rul_km_p10: 800, rul_km_p50: 1000, rul_km_p90: 1200,
      estimated_days_p10: 80, estimated_days_p50: 100, estimated_days_p90: 120, bootstrap_iterations_valid: 100 },
  } };
  return data;
}
it('renders optional RUL intervals as experimental uncertainty, not failure confidence', async () => {
  const data = resultWithInterval(); expect(parseLeafAnalysis(data)).toBe(data);
  await render(<LeafResults data={data} />);
  expect(screen.getByText(/80% bootstrap interval:/)).toBeTruthy();
  expect(screen.getByText(/not validated failure confidence/)).toBeTruthy();
  expect(screen.getByText(/Estimated calendar interval:/)).toBeTruthy();
  expect(JSON.stringify(screen.toJSON())).not.toContain('[object Object]');
});
it.each(['absent', 'null'])('accepts %s RUL intervals from compatible services', state => {
  const data = resultWithInterval(); const result = data.rul.result!;
  if (state === 'absent') { delete result.confidence_interval; delete result.rul_km_p10; delete result.rul_km_p50; delete result.rul_km_p90; }
  else { result.confidence_interval = null; result.rul_km_p10 = null; result.rul_km_p50 = null; result.rul_km_p90 = null; }
  expect(parseLeafAnalysis(data)).toBe(data);
});
it.each(['order', 'nonfinite', 'mismatch', 'partial'])('rejects malformed RUL uncertainty: %s', issue => {
  const data = resultWithInterval(); const ci = data.rul.result!.confidence_interval!;
  if (issue === 'order') ci.rul_km_p10 = 1300;
  if (issue === 'nonfinite') ci.rul_km_p50 = Infinity;
  if (issue === 'mismatch') data.rul.result!.rul_km_p10 = 700;
  if (issue === 'partial') delete data.rul.result!.rul_km_p50;
  expect(() => parseLeafAnalysis(data)).toThrow();
});

it('labels RUL intervals with the supplied level and preserves the original point estimate', async () => {
  const data = resultWithInterval(); data.rul.result!.confidence_interval!.level_pct = 95;
  expect(parseLeafAnalysis(data)).toBe(data); await render(<LeafResults data={data} />);
  expect(screen.getByText(/95% bootstrap interval:/)).toBeTruthy();
  expect(screen.queryByText(/80% bootstrap interval:/)).toBeNull();
  expect(screen.getByText('Point estimate: 1000.0 km')).toBeTruthy();
});
