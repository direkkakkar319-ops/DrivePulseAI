// Exercise generic Insights and metadata-only future picker integration without account/ML providers.
import { act, fireEvent, render, screen, within } from '@testing-library/react-native';
import { AIInsightsScreen } from '../src/components/insights/ai-insights-screen';
import InsightsRoute from '../src/app/(main)/(tabs)/insights';
import { demoInsights } from '../src/config/demo-insights';
import type { CsvFileMetadata } from '../src/types/ai-insights';

let mockParams: { demo?: string } = {};
jest.mock('expo-router', () => ({ useLocalSearchParams: () => mockParams }));
beforeEach(() => { mockParams = {}; });
const csv: CsvFileMetadata = { name: 'my-drive.csv', sizeBytes: 1200, mimeType: 'text/csv' };

it('starts empty and marks the unavailable native CSV control honestly', async () => {
  await render(<AIInsightsScreen />);
  expect(screen.getAllByRole('header').map(header => header.props.children)).toEqual([
    'AI Insights', 'Choose Data Source', 'Analysis Results', 'Telemetry Data',
  ]);
  expect(screen.getByRole('switch', { name: 'Use Demo Data' })).not.toBeChecked();
  expect(screen.getByRole('button', { name: 'Select CSV file' })).toBeDisabled();
  expect(screen.getByText('CSV selection and upload are not yet available in this build.')).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'Select CSV file' }));
  expect(screen.getByText('No analysis results yet')).toBeTruthy();
  expect(screen.getByText('No telemetry data selected')).toBeTruthy();
  expect(screen.queryByText('94.2%')).toBeNull();
});

it('toggles all illustrative values and labels without requiring a Garage vehicle or ML provider', async () => {
  await render(<AIInsightsScreen />);
  await fireEvent(screen.getByRole('switch'), 'valueChange', true);
  for (const result of demoInsights.results) {
    const card = within(screen.getByTestId(`analysis-${result.id}`));
    expect(card.getByText(result.title)).toBeTruthy();
    expect(card.getByText(result.value)).toBeTruthy();
    expect(card.getByText('Demo')).toBeTruthy();
    expect(card.getByText(result.explanation)).toBeTruthy();
  }
  for (const value of ['360 V', '42 A', '29°C', '64 km/h', '78%']) expect(screen.getByText(value)).toBeTruthy();
  expect(screen.getByText('Sample telemetry · Demo')).toBeTruthy();
  expect(screen.getByText(/Not from a vehicle or a trained model/)).toBeTruthy();
  expect(screen.queryByText(/TRIP|model version/i)).toBeNull();
  await fireEvent(screen.getByRole('switch'), 'valueChange', false);
  expect(screen.queryByText('94.2%')).toBeNull();
  expect(screen.queryByText('360 V')).toBeNull();
  expect(screen.getByText('No analysis results yet')).toBeTruthy();
});

it('renders selected CSV metadata and unavailable inference, replacing demo results rather than relabeling them', async () => {
  const picker = jest.fn(async () => csv);
  await render(<AIInsightsScreen initialDemo pickCsv={picker} />);
  await fireEvent.press(screen.getByRole('button', { name: 'Select CSV file' }));
  expect(picker).toHaveBeenCalledTimes(1);
  expect(screen.getByText(csv.name)).toBeTruthy();
  expect(screen.getByText('1,200 bytes')).toBeTruthy();
  expect(screen.getByText('text/csv')).toBeTruthy();
  expect(screen.getByText('Selected CSV · Not uploaded')).toBeTruthy();
  expect(screen.getByText('Analysis not available yet')).toBeTruthy();
  expect(screen.getByRole('switch')).not.toBeChecked();
  expect(screen.queryByText('94.2%')).toBeNull();
  expect(screen.queryByText('360 V')).toBeNull();
  await fireEvent(screen.getByRole('switch'), 'valueChange', true);
  expect(screen.queryByText(csv.name)).toBeNull();
  expect(screen.getByText('94.2%')).toBeTruthy();
  await fireEvent(screen.getByRole('switch'), 'valueChange', false);
  expect(screen.queryByText(csv.name)).toBeNull();
  expect(screen.getByText('No analysis results yet')).toBeTruthy();
});

it('allows CSV replacement and removal using metadata only, including very large files', async () => {
  const large = { name: 'large.csv', sizeBytes: 1_000_000_000_000 };
  const picker = jest.fn().mockResolvedValueOnce(csv).mockResolvedValueOnce(large);
  await render(<AIInsightsScreen pickCsv={picker} />);
  await fireEvent.press(screen.getByRole('button', { name: 'Select CSV file' }));
  await fireEvent.press(screen.getByRole('button', { name: 'Replace CSV file' }));
  expect(screen.queryByText(csv.name)).toBeNull();
  expect(screen.getByText(large.name)).toBeTruthy();
  expect(screen.getByText('Analysis not available yet')).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'Remove CSV selection' }));
  expect(screen.getByText('No analysis results yet')).toBeTruthy();
});

it('keeps the current source on picker cancellation', async () => {
  await render(<AIInsightsScreen initialDemo pickCsv={async () => null} />);
  await fireEvent.press(screen.getByRole('button', { name: 'Select CSV file' }));
  expect(screen.getByText('94.2%')).toBeTruthy();
  expect(screen.queryByRole('alert')).toBeNull();
});

it.each([
  [async () => { throw new Error('File access denied'); }, 'File access denied'],
  [async () => ({ name: 'photo.jpg' }), 'Please select a CSV file (.csv).'],
  [async () => ({ name: 'drive.csv', sizeBytes: -1 }), 'The file size could not be read. Please select the file again.'],
])('shows selection failures without inventing results', async (picker, message) => {
  await render(<AIInsightsScreen pickCsv={picker} />);
  await fireEvent.press(screen.getByRole('button', { name: 'Select CSV file' }));
  expect(screen.getByRole('alert')).toHaveTextContent('Could not select CSV');
  expect(screen.getByText(message)).toBeTruthy();
  expect(screen.getByText('No analysis results yet')).toBeTruthy();
});

it('prevents duplicate picks and ignores a late picker result after unmount', async () => {
  let finish!: (file: CsvFileMetadata) => void;
  const picker = jest.fn(() => new Promise<CsvFileMetadata>(resolve => { finish = resolve; }));
  const view = await render(<AIInsightsScreen pickCsv={picker} />);
  await fireEvent.press(screen.getByRole('button', { name: 'Select CSV file' }));
  expect(screen.getByRole('switch')).toBeDisabled();
  await fireEvent.press(screen.getByRole('button', { name: 'Select CSV file' }));
  expect(picker).toHaveBeenCalledTimes(1);
  await view.unmount();
  await act(async () => finish(csv));
});

it('handles a fresh Home demo request without repeatedly overriding the switch on rerenders', async () => {
  const view = await render(<InsightsRoute />);
  expect(screen.getByText('No analysis results yet')).toBeTruthy();
  mockParams = { demo: 'request-1' };
  await view.rerender(<InsightsRoute />);
  expect(screen.getByText('94.2%')).toBeTruthy();
  await fireEvent(screen.getByRole('switch'), 'valueChange', false);
  await view.rerender(<InsightsRoute />);
  expect(screen.queryByText('94.2%')).toBeNull();
  mockParams = { demo: 'request-2' };
  await view.rerender(<InsightsRoute />);
  expect(screen.getByText('94.2%')).toBeTruthy();
});
