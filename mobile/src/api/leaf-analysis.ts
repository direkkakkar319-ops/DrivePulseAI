import { ApiError } from './client';
import { request } from './analysis-http';
import { parseLeafAnalysis, parseLeafCatalog } from '@/lib/leaf-analysis';
import type { LeafApi, LeafCsvFile } from '@/types/leaf-analysis';
export { AnalysisCancelled } from './analysis-http';
export function validateCsvFile(file: LeafCsvFile) {
  if (!file.name.toLowerCase().endsWith('.csv') || file.name.length > 255) throw new ApiError('Select one leaf-csv-v1 CSV file.');
  if (!/^(file|content):\/\//i.test(file.uri)) throw new ApiError('Select the file again.');
  if (file.sizeBytes !== undefined && (!Number.isSafeInteger(file.sizeBytes) || file.sizeBytes <= 0 || file.sizeBytes > 2 * 1024 * 1024)) throw new ApiError('Select a nonempty CSV no larger than 2 MiB.');
}
function validated<T>(parse: () => T): T {
  try { return parse(); } catch { throw new ApiError('The analysis service returned an incompatible response.'); }
}
export const analysisApi: LeafApi = {
  async samples(context) { const data = await request('/samples', context, 30_000, 'GET'); return validated(() => parseLeafCatalog(data)); } ,
  async sample(id, context) {
    if (!/^[a-z0-9][a-z0-9-]{0,63}$/.test(id)) throw new ApiError('Choose an available Nissan Leaf sample.');
    const data = await request(`/samples/${encodeURIComponent(id)}/analyze`, context, 150_000, 'POST');
    return validated(() => {
      const result = parseLeafAnalysis(data);
      if (result.source_type !== 'built_in_sample' || result.source.sample_id !== id) throw new Error();
      return result;
    });
  },
  async upload(file, context) {
    validateCsvFile(file);
    const data = await request('/upload', context, 150_000, 'POST', () => {
      const form = new FormData();
      form.append('file', { uri: file.uri, name: file.name, type: 'text/csv' } as unknown as Blob);
      return form;
    });
    return validated(() => { const result = parseLeafAnalysis(data); if (result.source_type !== 'uploaded_csv') throw new Error(); return result; });
  },
};
