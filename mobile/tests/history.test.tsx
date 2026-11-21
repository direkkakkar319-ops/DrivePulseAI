// Future records exist only as typed test fixtures; production has no history data adapter.
import { fireEvent, render, screen } from '@testing-library/react-native';
import HistoryRoute from '../src/app/(main)/(tabs)/history';
import { HistoryScreen } from '../src/components/history/history-screen';
import { AnalysisHistoryCard } from '../src/components/history/analysis-history-card';
import { AnalysisDetailsScreen } from '../src/components/history/analysis-details-screen';
import { AIInsightsScreen } from '../src/components/insights/ai-insights-screen';
import type { AnalysisDetails, AnalysisHistoryRecord } from '../src/types/analysis-history';

const mockNavigate = jest.fn();
jest.mock('expo-router', () => ({ useRouter: () => ({ navigate: mockNavigate }) }));
beforeEach(() => jest.clearAllMocks());

// Genuine-shaped records for rendering tests, never imported by application code.
const record: AnalysisHistoryRecord = { id: 'analysis-test-17', createdAt: '2026-11-15T12:30:00Z',
  source: { kind: 'csv-upload', label: 'inspection.csv' }, status: 'Completed', summary: 'Stored backend summary.' };
const detail: AnalysisDetails = { ...record,
  results: [{ id: 'result-1', label: 'Processing outcome', value: 'Inspection complete', explanation: 'Stored explanation supplied by the service.' }],
  telemetryMetadata: [{ id: 'file', label: 'Original filename', value: 'inspection.csv' }],
};

it('renders the normal empty History without an account, Garage, or ML provider', async () => {
  await render(<HistoryRoute />);
  expect(screen.getByRole('header', { name: 'History' })).toBeTruthy();
  expect(screen.getByText('Your vehicle analysis records')).toBeTruthy();
  expect(screen.getByText('No analysis history yet')).toBeTruthy();
  expect(screen.getByText('Your completed vehicle analyses will appear here once real analysis is available.')).toBeTruthy();
  expect(screen.queryAllByTestId(/^history-record-/)).toHaveLength(0);
  expect(screen.queryByText(/94\.2%|360 V|anomaly score|maintenance risk/i)).toBeNull();
  expect(mockNavigate).not.toHaveBeenCalled();
  await fireEvent.press(screen.getByRole('button', { name: 'Explore AI Insights' }));
  expect(mockNavigate).toHaveBeenCalledTimes(1);
  expect(mockNavigate).toHaveBeenCalledWith('/(main)/(tabs)/insights');
});

it('keeps demo results out of History after opening demo Insights', async () => {
  const view = await render(<AIInsightsScreen initialDemo />);
  expect(screen.getByText('94.2%')).toBeTruthy();
  await view.rerender(<HistoryRoute />);
  expect(screen.getByText('No analysis history yet')).toBeTruthy();
  expect(screen.queryByText('94.2%')).toBeNull();
  expect(screen.queryByText('Sample telemetry · Demo')).toBeNull();
  expect(screen.queryAllByTestId(/^history-record-/)).toHaveLength(0);
});

it('renders a supplied persisted-shaped record and enables only its supplied detail action', async () => {
  const open = jest.fn();
  await render(<AnalysisHistoryCard record={record} onOpen={open} />);
  expect(screen.getByText('Analysis ID: analysis-test-17')).toBeTruthy();
  expect(screen.getByText(/^Date and time:/)).toHaveTextContent(/2026/);
  expect(screen.getByText('Data source: CSV upload · inspection.csv')).toBeTruthy();
  expect(screen.getByText('Status: Completed')).toBeTruthy();
  expect(screen.getByText(record.summary!)).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'View analysis analysis-test-17' }));
  expect(open).toHaveBeenCalledWith(record.id);
});

it.each([
  ['csv-upload', 'CSV upload'], ['recorded-dataset', 'Recorded dataset'], ['other', 'Other source'],
] as const)('supports %s provenance without inferring a Garage vehicle', async (kind, label) => {
  await render(<AnalysisHistoryCard record={{ id: 'source-test', source: { kind } }} />);
  expect(screen.getByText(`Data source: ${label}`)).toBeTruthy();
  expect(screen.queryByText(/active vehicle|My Car/)).toBeNull();
  expect(screen.queryAllByRole('button')).toHaveLength(0);
});

it.each([undefined, null, '', 'not-a-date'])('handles missing or invalid record metadata (%s)', async createdAt => {
  await render(<AnalysisHistoryCard record={{ id: 'incomplete', createdAt, summary: '  ', status: null }} />);
  expect(screen.getByText('Date and time: Date and time unavailable')).toBeTruthy();
  expect(screen.getByText('Data source: Data source unavailable')).toBeTruthy();
  expect(screen.getByText('Status: Unavailable')).toBeTruthy();
  expect(screen.getByText('No summary provided.')).toBeTruthy();
});

it('renders supplied loading, real-request error/retry, empty and populated states independently', async () => {
  const retry = jest.fn(), explore = jest.fn(), open = jest.fn();
  const view = await render(<HistoryScreen resource={{ status: 'loading' }} onExploreInsights={explore} />);
  expect(screen.getByLabelText('Loading analysis history')).toBeTruthy();
  expect(screen.queryByText('No analysis history yet')).toBeNull();
  await view.rerender(<HistoryScreen resource={{ status: 'error', message: 'History service unavailable' }}
    onRetry={retry} onExploreInsights={explore} />);
  expect(screen.getByRole('alert')).toHaveTextContent('Could not load analysis history');
  expect(screen.getByText('History service unavailable')).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'Retry' }));
  expect(retry).toHaveBeenCalledTimes(1);
  expect(explore).not.toHaveBeenCalled();
  await view.rerender(<HistoryScreen resource={{ status: 'ready', data: [] }} onExploreInsights={explore} />);
  expect(screen.getByText('No analysis history yet')).toBeTruthy();
  await view.rerender(<HistoryScreen resource={{ status: 'ready', data: [record] }} onExploreInsights={explore} onOpenRecord={open} />);
  expect(screen.getAllByTestId(/^history-record-/)).toHaveLength(1);
  expect(screen.queryByText('No analysis history yet')).toBeNull();
  await fireEvent.press(screen.getByRole('button', { name: `View analysis ${record.id}` }));
  expect(open).toHaveBeenCalledWith(record.id);
});

it('renders genuine-shaped details and delegates Back without creating a navigation route', async () => {
  const back = jest.fn();
  await render(<AnalysisDetailsScreen resource={{ status: 'ready', data: detail }} onBack={back} />);
  expect(screen.getByRole('header', { name: 'Analysis details' })).toBeTruthy();
  expect(screen.getByText('Analysis ID: analysis-test-17')).toBeTruthy();
  expect(screen.getByText('Inspection complete')).toBeTruthy();
  expect(screen.getByText('Stored explanation supplied by the service.')).toBeTruthy();
  expect(screen.getByText('Original filename')).toBeTruthy();
  expect(screen.getByText('inspection.csv')).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'Back' }));
  expect(back).toHaveBeenCalledTimes(1);
});

it.each([undefined, null, []])('shows missing result/telemetry sections without invented values (%s)', async results => {
  await render(<AnalysisDetailsScreen resource={{ status: 'ready', data: { id: 'partial', results, telemetryMetadata: results } }} />);
  expect(screen.getByText('No analysis results available')).toBeTruthy();
  expect(screen.getByText('No telemetry metadata available')).toBeTruthy();
  expect(screen.queryByText(/94\.2|Normal|Low|360/)).toBeNull();
});

it('renders missing values and explanation explicitly', async () => {
  await render(<AnalysisDetailsScreen resource={{ status: 'ready', data: { id: 'partial',
    results: [{ id: 'missing', label: 'Service result' }], telemetryMetadata: [{ id: 'missing', label: 'Service metadata', value: null }],
  } }} />);
  expect(screen.getByText('Result unavailable')).toBeTruthy();
  expect(screen.getByText('No explanation provided.')).toBeTruthy();
  expect(screen.getByText('Metadata unavailable')).toBeTruthy();
});

it('supports unavailable details, loading, and retryable errors without displaying stale records', async () => {
  const retry = jest.fn();
  const view = await render(<AnalysisDetailsScreen resource={{ status: 'not-integrated' }} />);
  expect(screen.getByText('Analysis unavailable')).toBeTruthy();
  await view.rerender(<AnalysisDetailsScreen resource={{ status: 'ready', data: null }} />);
  expect(screen.getByText('Analysis unavailable')).toBeTruthy();
  await view.rerender(<AnalysisDetailsScreen resource={{ status: 'loading' }} />);
  expect(screen.getByLabelText('Loading analysis details')).toBeTruthy();
  await view.rerender(<AnalysisDetailsScreen resource={{ status: 'error', message: 'Record access failed' }} onRetry={retry} />);
  expect(screen.getByRole('alert')).toHaveTextContent('Could not load analysis details');
  expect(screen.queryByText('Analysis ID: analysis-test-17')).toBeNull();
  await fireEvent.press(screen.getByRole('button', { name: 'Retry' }));
  expect(retry).toHaveBeenCalledTimes(1);
});
