// Exercise the production route, picker adapter, controller, client and validators.
// Only native Firebase/DocumentPicker and the HTTP transport are mocked.
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import InsightsRoute from '../src/app/(main)/(tabs)/insights';
import { authService } from '../src/api/auth';
import { csvFile, sampleResult, uploadResult } from './analysis-fixtures';
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
    if (String(url).endsWith('/samples')) return response({ schema_version: 1, samples: [sampleResult().sample] });
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
  await fireEvent.press(screen.getByRole('button', { name: 'Prerecorded KIT sample' }));
  await fireEvent.press(await screen.findByRole('button', { name: 'KIT first-pair test excerpt' }));
  expect(fetch).toHaveBeenCalledTimes(1); // Selection alone does not run inference.
  await fireEvent.press(screen.getByRole('button', { name: 'Analyze KIT sample' }));
  expect(await screen.findByText('Real KIT analysis received')).toBeTruthy();
  expect(screen.getByText('Maximum anomaly score: 3.435')).toBeTruthy();
  expect(fetch).toHaveBeenLastCalledWith(expect.stringContaining('/samples/kit-first-pair-excerpt/analyze'), expect.objectContaining({
    method: 'POST', headers: { Authorization: 'Bearer firebase-route-token', Accept: 'application/json' },
  }));
});

it('uses the installed picker adapter and native multipart upload with the entered date', async () => {
  await render(<InsightsRoute />);
  await fireEvent.press(screen.getByRole('button', { name: 'Select CSV file' }));
  expect(mockPicker).toHaveBeenCalledWith(expect.objectContaining({ multiple: false, copyToCacheDirectory: false, base64: false }));
  expect(screen.getByText(csvFile.name)).toBeTruthy();
  await fireEvent.changeText(screen.getByLabelText('Recording date'), '2018-03-20');
  await fireEvent.press(screen.getByRole('button', { name: 'Upload and analyze CSV' }));
  expect(await screen.findByText('Real KIT analysis received')).toBeTruthy();
  const [url, options] = jest.mocked(fetch).mock.calls[0];
  expect(url).toBe('https://api.example.test/api/v1/analysis/upload');
  expect(options?.headers).toEqual({ Authorization: 'Bearer firebase-route-token', Accept: 'application/json' });
  const parts = (options?.body as unknown as { getParts(): { fieldName: string; uri?: string; string?: string }[] }).getParts();
  expect(parts).toHaveLength(2);
  expect(parts).toEqual(expect.arrayContaining([expect.objectContaining({ fieldName: 'file', uri: csvFile.uri }),
    expect.objectContaining({ fieldName: 'recording_date', string: '2018-03-20' })]));
  await fireEvent(screen.getByRole('switch'), 'valueChange', true);
  expect(screen.queryByText('Real KIT analysis received')).toBeNull();
  expect(screen.getByText('94.2%')).toBeTruthy();
});

it('keeps the prior native file on cancellation and rejects non-CSV documents', async () => {
  await render(<InsightsRoute />);
  await fireEvent.press(screen.getByRole('button', { name: 'Select CSV file' }));
  await fireEvent.changeText(screen.getByLabelText('Recording date'), '2018-03-20');
  mockPicker.mockResolvedValueOnce({ canceled: true, assets: null });
  await fireEvent.press(screen.getByRole('button', { name: 'Replace CSV file' }));
  expect(screen.getByText(csvFile.name)).toBeTruthy();
  expect(screen.getByLabelText('Recording date').props.value).toBe('2018-03-20');
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
  await fireEvent.changeText(screen.getByLabelText('Recording date'), '2018-03-20');
  await fireEvent.press(screen.getByRole('button', { name: 'Upload and analyze CSV' }));
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
  const signal = jest.mocked(fetch).mock.calls[0][1]?.signal;
  await act(async () => { mockUser = { ...mockUser!, uid: 'bob' }; listeners.forEach(listener => listener(mockUser)); });
  await view.rerender(<InsightsRoute />);
  await act(async () => { finish(response(uploadResult())); });
  expect(signal?.aborted).toBe(true);
  expect(screen.queryByText(csvFile.name)).toBeNull();
  expect(screen.queryByText('Real KIT analysis received')).toBeNull();
  expect(screen.getByText('No analysis results yet')).toBeTruthy();
});
