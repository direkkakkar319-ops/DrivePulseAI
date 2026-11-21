import { pickKitCsv, csvPickerMimeTypes } from '../src/lib/csv-picker';
import { csvFile } from './analysis-fixtures';
jest.mock('../src/api/auth', () => ({ authService: { subscribe: jest.fn(), getToken: jest.fn() } }));
const mockPick = jest.fn();
jest.mock('expo-document-picker', () => ({ getDocumentAsync: (options: unknown) => mockPick(options) }));
beforeEach(() => { mockPick.mockReset(); });
it('selects one native document reference without reading or copying the CSV', async () => {
  mockPick.mockResolvedValue({ canceled: false, assets: [{ uri: csvFile.uri, name: csvFile.name, size: 1200, mimeType: 'text/csv' }] });
  await expect(pickKitCsv()).resolves.toEqual(csvFile);
  expect(mockPick).toHaveBeenCalledWith({ type: csvPickerMimeTypes, multiple: false, copyToCacheDirectory: false, base64: false });
  expect(csvPickerMimeTypes).toContain('text/csv'); expect(csvPickerMimeTypes).not.toContain('*/*');
});
it('preserves unknown size and provider MIME without inferring data', async () => {
  mockPick.mockResolvedValue({ canceled: false, assets: [{ uri: csvFile.uri, name: csvFile.name, mimeType: 'application/octet-stream' }] });
  await expect(pickKitCsv()).resolves.toEqual({ uri: csvFile.uri, name: csvFile.name, mimeType: 'application/octet-stream' });
});
it('treats cancellation as no new selection', async () => {
  mockPick.mockResolvedValue({ canceled: true, assets: null }); await expect(pickKitCsv()).resolves.toBeNull();
});
it.each([
  { canceled: false, assets: [] }, { canceled: false, assets: [{ ...csvFile, name: 'image.png' }] },
  { canceled: false, assets: [{ ...csvFile, size: 2097153 }] }, { canceled: false, assets: [csvFile, csvFile] },
])('rejects an invalid selection (%j)', async response => {
  mockPick.mockResolvedValue(response); await expect(pickKitCsv()).rejects.toThrow();
});
it('handles permissions/provider errors without exposing native internals', async () => {
  mockPick.mockRejectedValue(new Error('private device details')); await expect(pickKitCsv()).rejects.toThrow('Check file access');
});
it('reports a missing native picker safely without breaking app startup', async () => {
  jest.resetModules();
  jest.doMock('expo-document-picker', () => { throw new Error('private missing native module'); });
  await expect(pickKitCsv()).rejects.toThrow('unavailable in this installed build');
});
