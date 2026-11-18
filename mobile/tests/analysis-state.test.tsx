import { act, fireEvent, render, renderHook, screen } from '@testing-library/react-native';
import { useAnalysis } from '../src/hooks/use-analysis';
import { AIInsightsScreen } from '../src/components/insights/ai-insights-screen';
import { csvFile, sampleResult, uploadResult } from './analysis-fixtures';
import type { AnalysisApi, KitSampleAnalysis } from '../src/types/kit-analysis';

jest.mock('../src/api/auth', () => ({ authService: { getToken: jest.fn(), subscribe: jest.fn() } }));
function setup() {
  const sample = sampleResult().sample;
  const api = { samples: jest.fn(async () => ({ schema_version: 1 as const, samples: [sample, { ...sample, id: 'other-sample', display_name: 'Other test sample' }] })),
    sample: jest.fn(async () => sampleResult()), upload: jest.fn(async () => uploadResult()) };
  const pick = jest.fn(async () => csvFile);
  return { api, pick, id: sample.id };
}
function deferred<T>() { let resolve!: (value: T) => void; return { promise: new Promise<T>(r => { resolve = r; }), resolve: (value: T) => resolve(value) }; }

it('loads backend options only on request and runs the selected sample explicitly', async () => {
  const { api, pick, id } = setup();
  const hook = await renderHook(() => useAnalysis('alice', false, pick, api));
  expect(api.samples).not.toHaveBeenCalled();
  await act(() => hook.result.current.loadSamples());
  await act(() => hook.result.current.selectSample(id));
  expect(api.sample).not.toHaveBeenCalled();
  await act(() => hook.result.current.run());
  expect(api.sample).toHaveBeenCalledWith(id, expect.objectContaining({ uid: 'alice' }));
  expect(hook.result.current.result.status).toBe('ready');
});
it('retries catalog failure and refreshes an already loaded list on explicit requests', async () => {
  const { api, pick, id } = setup();
  api.samples.mockRejectedValueOnce(new Error('Catalog unavailable'));
  const hook = await renderHook(() => useAnalysis('alice', false, pick, api));
  await act(() => hook.result.current.loadSamples()); expect(hook.result.current.catalog.status).toBe('error');
  await act(() => hook.result.current.loadSamples()); await act(() => hook.result.current.selectSample(id));
  api.samples.mockResolvedValueOnce({ schema_version: 1, samples: [] });
  await act(() => hook.result.current.loadSamples()); expect(api.samples).toHaveBeenCalledTimes(3);
  await act(() => hook.result.current.run()); expect(api.sample).not.toHaveBeenCalled();
  expect(hook.result.current.result.status).toBe('error');
});
it('ignores an old response after the user cancels and starts another analysis', async () => {
  const { api, pick, id } = setup(), old = deferred<KitSampleAnalysis>();
  api.sample.mockImplementationOnce(() => old.promise);
  const hook = await renderHook(() => useAnalysis('alice', false, pick, api));
  await act(() => hook.result.current.loadSamples()); await act(() => hook.result.current.selectSample(id));
  let pending!: Promise<void>; await act(() => { pending = hook.result.current.run(); });
  await act(() => hook.result.current.cancel()); await act(() => hook.result.current.run());
  await act(async () => { old.resolve(sampleResult()); await pending; });
  expect(hook.result.current.result.status).toBe('ready'); expect(api.sample).toHaveBeenCalledTimes(2);
});
it('clears results on source/date changes and uploads a native reference with the explicit date', async () => {
  const { api, pick, id } = setup();
  const hook = await renderHook(() => useAnalysis('alice', false, pick, api));
  await act(() => hook.result.current.loadSamples()); await act(() => hook.result.current.selectSample(id));
  await act(() => hook.result.current.run());
  await act(() => hook.result.current.selectCsv());
  expect(hook.result.current.result.status).toBe('idle');
  await act(() => hook.result.current.run());
  expect(hook.result.current.result.status).toBe('error'); expect(api.upload).not.toHaveBeenCalled();
  await act(() => hook.result.current.setRecordingDate('2018-03-20'));
  await act(() => hook.result.current.run());
  expect(api.upload).toHaveBeenCalledWith(csvFile, '2018-03-20', expect.objectContaining({ uid: 'alice' }));
  await act(() => hook.result.current.useDemo(true));
  expect(hook.result.current.source.kind).toBe('demo'); expect(hook.result.current.result.status).toBe('idle');
  await act(() => hook.result.current.run()); expect(api.upload).toHaveBeenCalledTimes(1);
});
it('rejects duplicate submissions and ignores a superseded response even when the adapter ignores cancellation', async () => {
  const { api, pick, id } = setup(), old = deferred<KitSampleAnalysis>();
  api.sample.mockImplementationOnce(() => old.promise);
  const hook = await renderHook(() => useAnalysis('alice', false, pick, api));
  await act(() => hook.result.current.loadSamples()); await act(() => hook.result.current.selectSample(id));
  let request!: Promise<void>;
  await act(() => { request = hook.result.current.run(); });
  await act(() => hook.result.current.run()); expect(api.sample).toHaveBeenCalledTimes(1);
  const signal = (api.sample.mock.calls[0] as unknown as [string, { signal: AbortSignal }])[1].signal;
  await act(() => hook.result.current.selectSample('other-sample')); expect(signal.aborted).toBe(true);
  await act(() => hook.result.current.run());
  await act(async () => { old.resolve(sampleResult()); await request; });
  expect(hook.result.current.source).toEqual({ kind: 'sample', sampleId: 'other-sample' });
  expect(hook.result.current.result.status).toBe('ready');
});
it('cancels and can explicitly retry a failed request without dropping its selection', async () => {
  const { api, pick, id } = setup();
  api.sample.mockRejectedValueOnce(new Error('Analysis service unavailable'));
  const hook = await renderHook(() => useAnalysis('alice', false, pick, api));
  await act(() => hook.result.current.loadSamples()); await act(() => hook.result.current.selectSample(id));
  await act(() => hook.result.current.run()); expect(hook.result.current.result.status).toBe('error');
  await act(() => hook.result.current.run()); expect(hook.result.current.result.status).toBe('ready');
  await act(() => hook.result.current.cancel()); expect(hook.result.current.result.status).toBe('idle');
});
it('clears both results and file references on logout and account switching', async () => {
  const { api, pick } = setup();
  const hook = await renderHook(({ uid }: { uid: string | null }) => useAnalysis(uid, false, pick, api), { initialProps: { uid: 'alice' as string | null } });
  await act(() => hook.result.current.selectCsv()); await act(() => hook.result.current.setRecordingDate('2018-03-20'));
  await act(() => hook.result.current.run());
  await hook.rerender({ uid: 'bob' });
  expect(hook.result.current.source.kind).toBe('none'); expect(hook.result.current.result.status).toBe('idle');
  expect(hook.result.current.recordingDate).toBe('');
  await act(() => hook.result.current.loadSamples());
  expect(api.samples).toHaveBeenLastCalledWith(expect.objectContaining({ uid: 'bob' }));
  await hook.rerender({ uid: null });
  await act(() => hook.result.current.run()); expect(api.upload).toHaveBeenCalledTimes(1);
});
it('does not publish late inference or picker results after unmount', async () => {
  const { api, id } = setup(), pending = deferred<KitSampleAnalysis>();
  api.sample.mockImplementation(() => pending.promise);
  const hook = await renderHook(() => useAnalysis('alice', false, undefined, api));
  await act(() => hook.result.current.loadSamples()); await act(() => hook.result.current.selectSample(id));
  let request!: Promise<void>; await act(() => { request = hook.result.current.run(); });
  const signal = (api.sample.mock.calls[0] as unknown as [string, { signal: AbortSignal }])[1].signal;
  await hook.unmount(); expect(signal.aborted).toBe(true);
  await act(async () => { pending.resolve(sampleResult()); await request; });
});
it('renders minimal real-source success and keeps the simulated demo separate', async () => {
  const { api, pick } = setup();
  function Connected() { const analysis = useAnalysis('alice', false, pick, api as AnalysisApi); return <AIInsightsScreen analysis={analysis} />; }
  await render(<Connected />);
  await fireEvent.press(screen.getByRole('button', { name: 'Prerecorded KIT sample' }));
  await fireEvent.press(await screen.findByRole('button', { name: 'KIT first-pair test excerpt' }));
  await fireEvent.press(screen.getByRole('button', { name: 'Analyze KIT sample' }));
  expect(await screen.findByText('Real KIT analysis received')).toBeTruthy();
  expect(screen.getByText('Maximum anomaly score: 3.435')).toBeTruthy();
  expect(screen.queryByText('94.2%')).toBeNull();
  await fireEvent(screen.getByRole('switch'), 'valueChange', true);
  expect(screen.queryByText('Real KIT analysis received')).toBeNull(); expect(screen.getByText('94.2%')).toBeTruthy();
});
it('submits the explicit recording date from the minimal CSV form and labels transient results honestly', async () => {
  const { api, pick } = setup();
  function Connected() { const analysis = useAnalysis('alice', false, pick, api); return <AIInsightsScreen analysis={analysis} />; }
  await render(<Connected />);
  await fireEvent.press(screen.getByRole('button', { name: 'Select CSV file' }));
  expect(screen.getByText(csvFile.name)).toBeTruthy();
  expect(screen.getByText('Selected CSV · Not saved')).toBeTruthy();
  await fireEvent.changeText(screen.getByLabelText('Recording date'), '2018-03-20');
  await fireEvent.press(screen.getByRole('button', { name: 'Upload and analyze CSV' }));
  expect(api.upload).toHaveBeenCalledWith(csvFile, '2018-03-20', expect.objectContaining({ uid: 'alice' }));
  expect(await screen.findByText('Real KIT analysis received')).toBeTruthy();
  expect(screen.getByText('CSV analysis received · Not saved')).toBeTruthy();
  expect(screen.queryByText('94.2%')).toBeNull();
});
