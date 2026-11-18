// Main backend only. No model key, raw CSV decoding, persistence, or Garage association.
import { authService } from './auth';
import { authErrorMessage } from './auth-errors';
import { API_BASE_URL, ApiError } from './client';
import { isRecordingDate, parseKitAnalysis, parseKitCatalog } from '@/lib/kit-analysis';
import type { AnalysisApi, AnalysisContext, KitCsvFile } from '@/types/kit-analysis';

export const analysisTimeouts = { catalog: 30_000, sample: 240_000, upload: 90_000 } as const;
// Current documented server default; the backend remains authoritative for content/workload limits.
export const csvMaxBytes = 2 * 1024 * 1024;
export class AnalysisCancelled extends Error {
  constructor() { super('Analysis request cancelled.'); this.name = 'AnalysisCancelled'; }
}
export function validateCsvFile(file: KitCsvFile) {
  if (!file.name.trim().toLowerCase().endsWith('.csv') || file.name.length > 255) {
    throw new ApiError('Select one KIT-compatible CSV file (.csv).');
  }
  if (!/^(file|content):\/\//i.test(file.uri)) throw new ApiError('The selected file is unavailable. Select it again.');
  if (file.sizeBytes !== undefined && (!Number.isSafeInteger(file.sizeBytes) || file.sizeBytes <= 0)) {
    throw new ApiError('The selected file is empty or its size is invalid.');
  }
  if (file.sizeBytes !== undefined && file.sizeBytes > csvMaxBytes) throw new ApiError('Select a CSV no larger than 2 MiB.');
}
function httpError(status: number): ApiError {
  const messages: Record<number, string> = {
    401: 'Your session could not be verified. Please log in again.',
    403: 'Verify your email before running analysis.',
    404: 'This sample is no longer available. Reload the sample list.',
    408: 'The upload was interrupted. Select the file and try again.',
    413: 'This CSV exceeds the upload or analysis workload limits. Use a shorter compatible recording.',
    415: 'Unsupported file type or encoding. Select a UTF-8 KIT-compatible raw CSV.',
    422: 'Check the recording date and KIT CSV columns, units, timestamps and readings. At least two usable adjacent windows are required.',
    429: 'Analysis is busy. Please wait and try again.',
    502: 'The analysis service returned an invalid response. Please try again later.',
    503: 'The analysis service is unavailable. Please try again later.',
    504: 'Analysis timed out. The service may be starting. Please try again later.',
  };
  return new ApiError(messages[status] ?? 'Analysis could not be completed. Please try again later.', status);
}

async function request(path: string, context: AnalysisContext, timeout: number, method: 'GET' | 'POST', body?: () => FormData): Promise<unknown> {
  if (!API_BASE_URL) throw new ApiError('The analysis service is not configured yet.');
  const controller = new AbortController(); let expired = false, changed = false;
  let unsubscribe = () => {};
  const abort = () => controller.abort();
  context.signal?.addEventListener('abort', abort);
  if (context.signal?.aborted) controller.abort();
  const timer = setTimeout(() => { expired = true; controller.abort(); }, timeout);
  let rejectAbort!: (reason: Error) => void;
  const aborted = new Promise<never>((_resolve, reject) => { rejectAbort = reject; });
  void aborted.catch(() => {}); // A synchronous session rejection can precede wait().
  // Promise.race covers token refresh/JSON decoding too, even if a native task ignores abort.
  const onAbort = () => rejectAbort(new AnalysisCancelled());
  controller.signal.addEventListener('abort', onAbort);
  const wait = <T,>(task: Promise<T>) => {
    if (controller.signal.aborted) throw new AnalysisCancelled();
    return Promise.race([task, aborted]);
  };
  try {
    const ready = new Promise<void>((resolve, reject) => {
      try {
        unsubscribe = authService.subscribe(user => {
          if (!user || user.uid !== context.uid || !user.emailVerified) {
            changed = true; controller.abort(); resolve();
          } else resolve();
        });
      } catch { reject(new ApiError('Please sign in to the Android app again.')); }
    });
    await wait(ready);
    for (let attempt = 0; attempt < 2; attempt++) {
      const token = await wait(authService.getToken(attempt > 0));
      if (controller.signal.aborted) throw new AnalysisCancelled();
      const response = await wait(fetch(`${API_BASE_URL}/api/v1/analysis${path}`, {
        method, headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' },
        ...(body ? { body: body() } : {}), signal: controller.signal,
      }));
      if (response.status === 401 && attempt === 0) continue;
      if (!response.ok) throw httpError(response.status);
      try { return await wait(response.json()); }
      catch (error) {
        if (controller.signal.aborted) throw error;
        throw new ApiError('The analysis service returned an incompatible response.');
      }
    }
    throw httpError(401);
  } catch (error) {
    if (expired) throw new ApiError('Analysis request timed out. Please try again later.', 504);
    if (changed) throw new AnalysisCancelled();
    if (controller.signal.aborted || error instanceof AnalysisCancelled) throw new AnalysisCancelled();
    if (error instanceof ApiError) throw error;
    if ((error as { code?: unknown } | null)?.code) throw new ApiError(authErrorMessage(error));
    throw new ApiError('Could not reach the analysis service. Check your connection and try again.');
  } finally {
    clearTimeout(timer); unsubscribe(); context.signal?.removeEventListener('abort', abort);
    controller.signal.removeEventListener('abort', onAbort);
  }
}
function validated<T>(parse: () => T): T {
  try { return parse(); } catch { throw new ApiError('The analysis service returned an incompatible response.'); }
}
export const analysisApi: AnalysisApi = {
  async samples(context) {
    const data = await request('/samples', context, analysisTimeouts.catalog, 'GET');
    return validated(() => parseKitCatalog(data));
  },
  async sample(id, context) {
    if (!/^[a-z0-9][a-z0-9-]{0,63}$/.test(id)) throw new ApiError('Choose an available KIT sample.');
    const data = await request(`/samples/${encodeURIComponent(id)}/analyze`, context, analysisTimeouts.sample, 'POST');
    return validated(() => {
      const result = parseKitAnalysis(data);
      if (result.source_type !== 'packaged_sample' || result.sample.id !== id) throw new Error();
      return result;
    });
  },
  async upload(file, recordingDate, context) {
    validateCsvFile(file);
    if (!isRecordingDate(recordingDate)) throw new ApiError('Enter the actual recording date as YYYY-MM-DD.');
    const data = await request('/upload', context, analysisTimeouts.upload, 'POST', () => {
      const form = new FormData();
      // RN networking reads the native reference; no CSV text/base64 enters JavaScript.
      form.append('file', { uri: file.uri, name: file.name, type: 'text/csv' } as unknown as Blob);
      form.append('recording_date', recordingDate);
      return form; // Native networking supplies Content-Type and the multipart boundary.
    });
    return validated(() => {
      const result = parseKitAnalysis(data);
      if (result.source_type !== 'uploaded_csv' || result.source.recording_date !== recordingDate) throw new Error();
      return result;
    });
  },
};
