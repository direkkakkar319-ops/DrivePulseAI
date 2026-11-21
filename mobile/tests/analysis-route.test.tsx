// Exercise the production route, picker adapter, controller, client and validators.
// Only native Firebase/DocumentPicker and the HTTP transport are mocked.
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import InsightsRoute from '../src/app/(main)/(tabs)/insights';
import { authService } from '../src/api/auth';
import { csvFile, sampleResult, uploadResult, leafSample } from './leaf-fixtures';
import type { AuthUser } from '../src/api/auth.types';

let mockUser: AuthUser | null;
const mockPicker = jest.fn();
jest.mock('expo-router', () => ({ useLocalSearchParams: () => ({}) }));
jest.mock('../src/store/authStore', () => ({ useAuthStore: () => ({ user: mockUser }) }));
jest.mock('../src/api/auth', () => ({ authService: { subscribe: jest.fn(), getToken: jest.fn() } }));
jest.mock('../src/api/client', () => ({ ...jest.requireActual('../src/api/client'), API_BASE_URL: 'https://api.example.test' }));
jest.mock('expo-document-picker', () => ({ getDocumentAsync: (options: unknown) => mockPicker(options) }));

const listeners = new Set<(user: AuthUser | null) => void>();
const originalFetch = global.fetch, originalFormData = global.FormData;
const response = (data: unknown) => ({ ok: true, status: 200, json: async () => data }) as Response;
beforeEach(() => {
  // Preserve Expo's native-component mock implementations (notably Switch).
  jest.clearAllMocks(); mockPicker.mockReset(); listeners.clear();
  mockUser = { uid: 'alice', email: 'driver@example.test', emailVerified: true, displayName: null };
  jest.mocked(authService.subscribe).mockImplementation(listener => { listeners.add(listener); listener(mockUser); return () => listeners.delete(listener); });
  jest.mocked(authService.getToken).mockResolvedValue('firebase-route-token');
  // eslint-disable-next-line @typescript-eslint/no-require-imports -- Verify RN native URI parts, not Jest's web FormData.
  global.FormData = require('react-native/Libraries/Network/FormData').default;
  global.fetch = jest.fn(async (url: string | URL | Request) => {
    if (String(url).endsWith('/samples')) return response({ schema_version: 1, samples: [leafSample] });
    if (String(url).endsWith('/analyze')) return response(sampleResult());
    if (String(url).endsWith('/upload')) return response(uploadResult());
    throw new Error('Unexpected test endpoint');
  });
  mockPicker.mockResolvedValue({ canceled: false, assets: [{ uri: csvFile.uri, name: csvFile.name, size: csvFile.sizeBytes, mimeType: csvFile.mimeType }] });
});
afterEach(() => { global.fetch = originalFetch; global.FormData = originalFormData; });

it('loads backend samples and runs the selected sample through the production route', async () => {
  await render(<InsightsRoute />);
  expect(screen.getByRole('button', { name: 'Select CSV file' })).not.toBeDisabled();
  await fireEvent.press(screen.getByRole('button', { name: 'Built-in Nissan Leaf sample' }));
  await fireEvent.press(await screen.findByRole('button', { name: 'Synthetic Leaf test fixture' }));
  expect(fetch).toHaveBeenCalledTimes(1); // Selection alone does not run inference.
  await fireEvent.press(screen.getByRole('button', { name: 'Analyze Nissan Leaf sample' }));
  expect(await screen.findByText('Synthetic integration input · genuine model inference')).toBeTruthy();
  expect(screen.getByText('SOC: 70%')).toBeTruthy();
  expect(fetch).toHaveBeenLastCalledWith(expect.stringContaining('/samples/nissan-leaf-synthetic-integration-v1/analyze'), expect.objectContaining({
    method: 'POST', headers: { Authorization: 'Bearer firebase-route-token', Accept: 'application/json' },
  }));
});

it('uses the installed picker adapter and native multipart upload with the entered date', async () => {
  await render(<InsightsRoute />);
  await fireEvent.press(screen.getByRole('button', { name: 'Select CSV file' }));
  expect(mockPicker).toHaveBeenCalledWith(expect.objectContaining({ multiple: false, copyToCacheDirectory: false, base64: false }));
  expect(screen.getByText(csvFile.name)).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'Upload and analyze CSV' }));
  expect(await screen.findByText('Uploaded Nissan Leaf telemetry')).toBeTruthy();
  const [url, options] = jest.mocked(fetch).mock.calls[0];
  expect(url).toBe('https://api.example.test/api/v1/analysis/upload');
  expect(options?.headers).toEqual({ Authorization: 'Bearer firebase-route-token', Accept: 'application/json' });
  const parts = (options?.body as unknown as { getParts(): { fieldName: string; uri?: string; string?: string }[] }).getParts();
  expect(parts).toHaveLength(1);
  expect(parts).toEqual(expect.arrayContaining([expect.objectContaining({ fieldName: 'file', uri: csvFile.uri })]));
  await fireEvent(screen.getByRole('switch'), 'valueChange', true);
  expect(screen.queryByText('Synthetic integration input · genuine model inference')).toBeNull();
  expect(screen.getByText('94.2%')).toBeTruthy();
});

it('keeps the prior native file on cancellation and rejects non-CSV documents', async () => {
  await render(<InsightsRoute />);
  await fireEvent.press(screen.getByRole('button', { name: 'Select CSV file' }));
  mockPicker.mockResolvedValueOnce({ canceled: true, assets: null });
  await fireEvent.press(screen.getByRole('button', { name: 'Replace CSV file' }));
  expect(screen.getByText(csvFile.name)).toBeTruthy();
  expect(screen.queryByRole('alert')).toBeNull();
  mockPicker.mockResolvedValueOnce({ canceled: false, assets: [{ uri: 'content://photo', name: 'photo.jpg', mimeType: 'image/jpeg' }] });
  await fireEvent.press(screen.getByRole('button', { name: 'Replace CSV file' }));
  expect(screen.getByRole('alert')).toHaveTextContent('Could not select CSV');
  expect(fetch).not.toHaveBeenCalled();
});

it('aborts an upload on account change and cannot publish its late response', async () => {
  let finish!: (value: Response) => void;
  jest.mocked(fetch).mockReturnValue(new Promise(resolve => { finish = resolve; }));
  const view = await render(<InsightsRoute />);
  await fireEvent.press(screen.getByRole('button', { name: 'Select CSV file' }));
  await fireEvent.press(screen.getByRole('button', { name: 'Upload and analyze CSV' }));
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
  const signal = jest.mocked(fetch).mock.calls[0][1]?.signal;
  await act(async () => { mockUser = { ...mockUser!, uid: 'bob' }; listeners.forEach(listener => listener(mockUser)); });
  await view.rerender(<InsightsRoute />);
  await act(async () => { finish(response(uploadResult())); });
  expect(signal?.aborted).toBe(true);
  expect(screen.queryByText(csvFile.name)).toBeNull();
  expect(screen.queryByText('Synthetic integration input · genuine model inference')).toBeNull();
  expect(screen.getByText('No analysis results yet')).toBeTruthy();
});

it('shows a sanitized upload failure and retries through the real multipart client to charts', async () => {
  jest.mocked(fetch).mockResolvedValueOnce({ ok: false, status: 503, json: async () => ({ detail: 'private upstream secret' }) } as Response)
    .mockResolvedValueOnce(response(uploadResult()));
  await render(<InsightsRoute />);
  await fireEvent.press(screen.getByRole('button', { name: 'Select CSV file' }));
  await fireEvent.press(screen.getByRole('button', { name: 'Upload and analyze CSV' }));
  expect(screen.getByText('The analysis service is unavailable. Please try again later.')).toBeTruthy();
  expect(screen.queryByText(/private upstream/)).toBeNull(); expect(screen.queryByTestId('Anomaly score chart')).toBeNull();
  await fireEvent.press(screen.getByRole('button', { name: 'Retry analysis' }));
  expect(await screen.findByTestId('Anomaly score chart')).toBeTruthy();
  expect(screen.getByTestId('SOC chart')).toBeTruthy(); expect(fetch).toHaveBeenCalledTimes(2);
});
it('does not display late upload charts after cancellation and switching to demo', async () => {
  let finish!: (value: Response) => void;
  jest.mocked(fetch).mockReturnValueOnce(new Promise(resolve => { finish = resolve; }));
  await render(<InsightsRoute />);
  await fireEvent.press(screen.getByRole('button', { name: 'Select CSV file' }));
  await fireEvent.press(screen.getByRole('button', { name: 'Upload and analyze CSV' }));
  expect(screen.getByText('Running Nissan Leaf analysis')).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'Cancel analysis' }));
  expect(jest.mocked(fetch).mock.calls[0][1]?.signal?.aborted).toBe(true);
  await fireEvent(screen.getByRole('switch'), 'valueChange', true);
  await act(async () => { finish(response(uploadResult())); });
  expect(screen.getByText('94.2%')).toBeTruthy(); expect(screen.queryByTestId('Anomaly score chart')).toBeNull();
  expect(screen.queryByTestId('SOC chart')).toBeNull();
});
