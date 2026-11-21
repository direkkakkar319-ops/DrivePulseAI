// On-demand native boundary. No CSV reads, cache copies, broad storage permissions or uploads.
import { validateCsvFile } from '@/api/leaf-analysis';
import type { LeafCsvFile } from '@/types/leaf-analysis';

// CSV aliases plus text/binary fallbacks used by Android document providers.
// There is no cross-provider extension filter; validate .csv after selection too.
export const csvPickerMimeTypes = ['text/csv', 'application/csv', 'text/comma-separated-values',
  'application/vnd.ms-excel', 'text/plain', 'application/octet-stream'];
export async function pickLeafCsv(): Promise<LeafCsvFile | null> {
  let picker: typeof import('expo-document-picker');
  try {
    // Keep missing native modules recoverable in older installed development builds.
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    picker = require('expo-document-picker') as typeof import('expo-document-picker');
  } catch {
    throw new Error('CSV selection is unavailable in this installed build. Use a built-in sample or update the app.');
  }
  let selected: Awaited<ReturnType<typeof picker.getDocumentAsync>>;
  try {
    // Android providers sometimes give CSV an octet-stream MIME. Validate the
    // extension/metadata here; the backend validates bytes, columns and units.
    selected = await picker.getDocumentAsync({ type: csvPickerMimeTypes, multiple: false, copyToCacheDirectory: false, base64: false });
  } catch {
    throw new Error('Could not open the document picker. Check file access and try again.');
  }
  if (selected.canceled) return null;
  if (!selected.assets || selected.assets.length !== 1) throw new Error('Select exactly one leaf-csv-v1 CSV file.');
  const asset = selected.assets[0];
  if (typeof asset.uri !== 'string' || typeof asset.name !== 'string') throw new Error('The selected file is unavailable. Select it again.');
  const file: LeafCsvFile = { uri: asset.uri, name: asset.name,
    ...(typeof asset.mimeType === 'string' ? { mimeType: asset.mimeType } : {}),
    ...(asset.size !== undefined ? { sizeBytes: asset.size } : {}),
  };
  validateCsvFile(file);
  return file;
}

export const pickKitCsv = pickLeafCsv; // Legacy test callers; active route uses pickLeafCsv.
