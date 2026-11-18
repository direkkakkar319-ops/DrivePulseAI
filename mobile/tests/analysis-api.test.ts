import { authService } from '../src/api/auth';
import { analysisApi, AnalysisCancelled, analysisTimeouts } from '../src/api/analysis';
import { parseKitAnalysis, parseKitCatalog, isRecordingDate } from '../src/lib/kit-analysis';
import { csvFile, sampleResult, uploadResult } from './analysis-fixtures';
import type { AuthUser } from '../src/api/auth.types';
import flaggedExcerpt from './fixtures/kit-flagged-excerpt.json';

jest.mock('../src/api/auth', () => ({ authService: { getToken: jest.fn(), subscribe: jest.fn() } }));
jest.mock('../src/api/client', () => ({ ...jest.requireActual('../src/api/client'), API_BASE_URL: 'https://api.example.test' }));
const context = { uid: 'alice' };
let listener: (user: AuthUser | null) => void;
const user: AuthUser = { uid: 'alice', email: 'driver@example.test', displayName: null, emailVerified: true };
const unsubscribe = jest.fn();
const originalFetch = global.fetch;
const originalFormData = global.FormData;
const reply = (status = 200, data: unknown = sampleResult()) => ({ status, ok: status === 200, json: async () => data });

beforeEach(() => {
  jest.resetAllMocks(); global.fetch = jest.fn();
  // Jest defaults to web FormData. Exercise the actual RN URI-part implementation.
  // eslint-disable-next-line @typescript-eslint/no-require-imports -- Test the native implementation rather than web FormData.
  global.FormData = require('react-native/Libraries/Network/FormData').default;
  jest.mocked(authService.getToken).mockResolvedValue('firebase-id-token');
  jest.mocked(authService.subscribe).mockImplementation(callback => { listener = callback; callback(user); return unsubscribe; });
});
afterEach(() => { global.fetch = originalFetch; global.FormData = originalFormData; jest.useRealTimers(); });

it('loads the catalog with a Firebase bearer token from the existing backend URL', async () => {
  const catalog = { schema_version: 1, samples: [sampleResult().sample] };
  jest.mocked(fetch).mockResolvedValue(reply(200, catalog) as Response);
  await expect(analysisApi.samples(context)).resolves.toEqual(catalog);
  expect(fetch).toHaveBeenCalledWith('https://api.example.test/api/v1/analysis/samples', expect.objectContaining({
    method: 'GET', headers: { Authorization: 'Bearer firebase-id-token', Accept: 'application/json' }, signal: expect.anything(),
  }));
  expect(authService.getToken).toHaveBeenCalledWith(false); expect(unsubscribe).toHaveBeenCalledTimes(1);
});
it('posts a selected real-source ID without a vehicle or manufactured request body', async () => {
  const result = sampleResult(); jest.mocked(fetch).mockResolvedValue(reply(200, result) as Response);
  await expect(analysisApi.sample(result.sample.id, context)).resolves.toEqual(result);
  const [url, options] = jest.mocked(fetch).mock.calls[0];
  expect(url).toBe(`https://api.example.test/api/v1/analysis/samples/${result.sample.id}/analyze`);
  expect(options?.method).toBe('POST'); expect(options?.body).toBeUndefined();
});
it('uploads a native file reference and explicit date without setting multipart headers', async () => {
  const result = uploadResult(); jest.mocked(fetch).mockResolvedValue(reply(200, result) as Response);
  await expect(analysisApi.upload(csvFile, '2018-03-20', context)).resolves.toEqual(result);
  const [url, options] = jest.mocked(fetch).mock.calls[0];
  expect(url).toBe('https://api.example.test/api/v1/analysis/upload');
  expect(options?.headers).toEqual({ Authorization: 'Bearer firebase-id-token', Accept: 'application/json' });
  const parts = (options?.body as unknown as { getParts(): { fieldName: string; uri?: string; string?: string }[] }).getParts();
  expect(parts).toEqual(expect.arrayContaining([
    expect.objectContaining({ fieldName: 'file', uri: csvFile.uri }),
    expect.objectContaining({ fieldName: 'recording_date', string: '2018-03-20' }),
  ]));
});
it('refreshes on 401 once and reconstructs multipart data for the retry', async () => {
  jest.mocked(fetch).mockResolvedValueOnce(reply(401) as Response).mockResolvedValue(reply(200, uploadResult()) as Response);
  await analysisApi.upload(csvFile, '2018-03-20', context);
  expect(authService.getToken).toHaveBeenNthCalledWith(1, false); expect(authService.getToken).toHaveBeenNthCalledWith(2, true);
  expect(jest.mocked(fetch).mock.calls[0][1]?.body).not.toBe(jest.mocked(fetch).mock.calls[1][1]?.body);
});
it.each([401, 403, 404, 408, 413, 415, 422, 429, 500, 502, 503, 504])('sanitizes HTTP %s and never retries service failures', async status => {
  jest.mocked(fetch).mockResolvedValue(reply(status, { detail: 'private upstream key/path' }) as Response);
  await expect(analysisApi.samples(context)).rejects.toMatchObject({ status, message: expect.not.stringContaining('private') });
  expect(fetch).toHaveBeenCalledTimes(status === 401 ? 2 : 1);
});
it('handles network failure and malformed JSON without leaking exception text', async () => {
  jest.mocked(fetch).mockRejectedValueOnce(new Error('private network internals'));
  await expect(analysisApi.samples(context)).rejects.toThrow('Could not reach the analysis service');
  jest.mocked(fetch).mockResolvedValue({ ...reply(), json: async () => { throw new Error('private body'); } } as unknown as Response);
  await expect(analysisApi.samples(context)).rejects.toThrow('incompatible response');
});
it.each([null, { ...user, uid: 'bob' }, { ...user, emailVerified: false }])('does not request a token for an invalid initial account %j', async identity => {
  jest.mocked(authService.subscribe).mockImplementation(callback => { callback(identity); return unsubscribe; });
  await expect(analysisApi.samples(context)).rejects.toBeInstanceOf(AnalysisCancelled);
  expect(fetch).not.toHaveBeenCalled(); expect(authService.getToken).not.toHaveBeenCalled();
});
it('cancels during a token fetch on account switching and does not send the late token', async () => {
  let token!: (value: string) => void;
  jest.mocked(authService.getToken).mockReturnValue(new Promise(resolve => { token = resolve; }));
  const pending = analysisApi.samples(context); const assertion = expect(pending).rejects.toBeInstanceOf(AnalysisCancelled);
  await Promise.resolve(); listener({ ...user, uid: 'bob' }); token('late-account-token');
  await assertion; expect(fetch).not.toHaveBeenCalled();
});
it('cancels an in-flight request even if fetch ignores the abort signal', async () => {
  jest.mocked(fetch).mockReturnValue(new Promise(() => {}));
  const controller = new AbortController();
  const assertion = expect(analysisApi.samples({ ...context, signal: controller.signal })).rejects.toBeInstanceOf(AnalysisCancelled);
  await Promise.resolve(); controller.abort(); await assertion; expect(unsubscribe).toHaveBeenCalled();
});
it('bounds long-running analysis and native token operations with an analysis-specific timeout', async () => {
  jest.useFakeTimers(); jest.mocked(authService.getToken).mockReturnValue(new Promise(() => {}));
  const assertion = expect(analysisApi.sample(sampleResult().sample.id, context)).rejects.toMatchObject({ status: 504 });
  await jest.advanceTimersByTimeAsync(analysisTimeouts.sample); await assertion;
  expect(analysisTimeouts.sample).toBeGreaterThan(180_000); expect(fetch).not.toHaveBeenCalled();
});
it.each(['2018-02-30', '2018-3-20', 'not-a-date', '0000-01-01'])('rejects an invalid recording date %s before HTTP', async day => {
  await expect(analysisApi.upload(csvFile, day, context)).rejects.toThrow('YYYY-MM-DD'); expect(fetch).not.toHaveBeenCalled();
});
it.each([
  { ...csvFile, sizeBytes: 0 }, { ...csvFile, sizeBytes: Infinity }, { ...csvFile, sizeBytes: 2097153 },
  { ...csvFile, name: 'image.jpg' }, { ...csvFile, uri: 'https://untrusted.test/file.csv' },
])('rejects incompatible file metadata before HTTP (%j)', async file => {
  await expect(analysisApi.upload(file, '2018-03-20', context)).rejects.toThrow(); expect(fetch).not.toHaveBeenCalled();
});
it('accepts real-shaped contract data with additive fields and preserves telemetry zeros', () => {
  const data = { ...sampleResult(), future_additive_field: true };
  expect(parseKitAnalysis(data)).toBe(data);
  expect(parseKitCatalog({ schema_version: 1, samples: [] }).samples).toEqual([]);
  expect(isRecordingDate('2024-02-29')).toBe(true);
});
it('accepts genuine flagged-pair deviations and target intervals without creating charts or diagnoses', () => {
  const data = parseKitAnalysis(flaggedExcerpt);
  expect(data.summary.novel_pairs).toBe(2);
  expect(data.flagged_intervals.map(i => [i.start_seconds, i.end_seconds])).toEqual([[31660, 31670], [31770, 31780]]);
});
it.each(['duplicate', 'unflagged', 'gap', 'peak', 'segment'])('rejects invalid interval traceability (%s)', mode => {
  const data = JSON.parse(JSON.stringify(flaggedExcerpt)) as typeof flaggedExcerpt;
  if (mode === 'duplicate') data.flagged_intervals[1].pair_ids = data.flagged_intervals[0].pair_ids;
  if (mode === 'unflagged') data.predictions[0].is_novel = false;
  if (mode === 'gap') data.flagged_intervals[0].start_seconds++;
  if (mode === 'peak') data.flagged_intervals[0].peak_anomaly_score++;
  if (mode === 'segment') data.flagged_intervals[0].segment_id++;
  expect(() => parseKitAnalysis(data)).toThrow('incompatible response');
});
it.each(['version', 'count', 'score', 'missing', 'point', 'sample', 'persisted', 'model', 'signals', 'recording'])('rejects incompatible analysis JSON (%s)', async mode => {
  const data = sampleResult();
  if (mode === 'version') Object.assign(data, { schema_version: 2 });
  if (mode === 'count') data.pair_count++;
  if (mode === 'score') data.predictions[0].anomaly_score = NaN;
  if (mode === 'missing') delete (data as Partial<typeof data>).explanation;
  if (mode === 'point') data.score_series[0].window.start_seconds++;
  if (mode === 'sample') data.sample.id = 'other-sample';
  if (mode === 'persisted') Object.assign(data, { persisted: true });
  if (mode === 'model') Object.assign(data.model, { model_version: 'unrelated-model' });
  if (mode === 'signals') data.signals.pop();
  if (mode === 'recording') data.sample.recording_id = 'unrelated-recording';
  jest.mocked(fetch).mockResolvedValue(reply(200, data) as Response);
  await expect(analysisApi.sample(sampleResult().sample.id, context)).rejects.toThrow('incompatible response');
});
it('rejects malformed/duplicate catalogs and unsafe sample IDs', async () => {
  const sample = sampleResult().sample;
  expect(() => parseKitCatalog({ schema_version: 1, samples: [sample, sample] })).toThrow();
  expect(() => parseKitCatalog({ schema_version: 1, samples: [{ ...sample, window_count: '2' }] })).toThrow();
  await expect(analysisApi.sample('../secret', context)).rejects.toThrow('available KIT sample'); expect(fetch).not.toHaveBeenCalled();
});
