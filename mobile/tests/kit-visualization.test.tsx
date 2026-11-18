import { fireEvent, render, screen, within } from '@testing-library/react-native';
import { KitAnalysisVisualization } from '../src/components/insights/kit-analysis-visualization';
import { KitLineChart } from '../src/components/insights/kit-line-chart';
import { AIInsightsScreen } from '../src/components/insights/ai-insights-screen';
import { useAnalysis } from '../src/hooks/use-analysis';
import { parseKitAnalysis } from '../src/lib/kit-analysis';
import { analysisSegments, clock, lineRuns, plotNumber, scorePoints, segmentKey, telemetryPoints, type PlotPoint } from '../src/lib/kit-visualization';
import { sampleResult, uploadResult } from './analysis-fixtures';
import flagged from './fixtures/kit-flagged-excerpt.json';
import type { AnalysisApi } from '../src/types/kit-analysis';

jest.mock('../src/api/auth', () => ({ authService: { getToken: jest.fn(), subscribe: jest.fn() } }));
const flaggedResult = () => parseKitAnalysis(JSON.parse(JSON.stringify(flagged)));
const reading = () => telemetryPoints(sampleResult(), analysisSegments(sampleResult())[0].value, 'speed_kmph')[0];

it('maps genuine scores to target window times without recomputation', () => {
  const data = sampleResult();
  const points = scorePoints(data, analysisSegments(data)[0].value);
  expect(points).toEqual([{ id: data.predictions[0].pair_id, window: data.predictions[0].next_window,
    value: data.predictions[0].anomaly_score, flagged: false, threshold: data.model.threshold }]);
  expect(points[0].window.start_seconds).toBe(30490);
  expect(clock(points[0].window.start_seconds)).toBe('08:28:10');
});
it('maps observed medians, valid zeros and sparse partial missingness', () => {
  const data = sampleResult(); data.telemetry[0].medians.speed_kmph = 0; data.telemetry[0].missing_fractions.speed_kmph = 0.25;
  const points = telemetryPoints(data, analysisSegments(data)[0].value, 'speed_kmph');
  expect(points[0]).toMatchObject({ value: 0, missingFraction: 0.25, flagged: false });
  expect(points[1].value).toBe(data.telemetry[1].medians.speed_kmph); expect(points[1].missingFraction).toBe(0);
});
it('shades only genuine half-open target intervals', () => {
  const data = flaggedResult(), segment = analysisSegments(data)[0].value;
  expect(telemetryPoints(data, segment, 'speed_kmph').filter(p => p.flagged).map(p => p.window.start_seconds)).toEqual([31660, 31770]);
  expect(scorePoints(data, segment).map(p => p.value)).toEqual(data.score_series.map(p => p.anomaly_score));
});
it('separates recording, date, split and segment identities despite overlapping clocks', () => {
  const data = sampleResult(), first = data.telemetry[0];
  data.telemetry.push({ ...first, window: { ...first.window, id: 'other-segment', segment_id: 1 } });
  const segments = analysisSegments(data); expect(segments).toHaveLength(2);
  expect(telemetryPoints(data, segments[1].value, 'speed_kmph')).toHaveLength(1);
  for (const update of [{ recording_date: '2018-03-21' }, { recording_id: 'other' }, { split: 'uploaded' }])
    expect(segmentKey({ ...first.window, ...update })).not.toBe(segmentKey(first.window));
});
it('breaks lines at gaps, missing values, segment changes and backward clocks', () => {
  const base = reading();
  const at = (time: number, value: number | null = 1, segment_id = 0): PlotPoint => ({ ...base, value,
    window: { ...base.window, start_seconds: time, end_seconds: time + 10, segment_id } });
  expect(lineRuns([at(0), at(10), at(30), at(40, null), at(50), at(60, 1, 1), at(0, 1, 1)]).map(r => r.length)).toEqual([2, 1, 1, 1, 1]);
});
it('rejects malformed API measurements and out-of-order telemetry before rendering', () => {
  for (const value of [NaN, Infinity, null, undefined]) {
    const data = sampleResult(); data.telemetry[0].medians.speed_kmph = value as number;
    expect(() => parseKitAnalysis(data)).toThrow('incompatible');
  }
  const reversed = sampleResult(); reversed.telemetry.reverse(); expect(() => parseKitAnalysis(reversed)).toThrow('incompatible');
});
it('formats clocks and small or large values without inventing UTC or hiding tiny readings', () => {
  expect(clock(31660)).toBe('08:47:40'); expect(plotNumber(1e-10)).toBe('1.00e-10');
  expect(plotNumber(1e200)).toBe('1.00e+200'); expect(plotNumber(0)).toBe('0');
});
it('renders real intervals, threshold, actual rankings and unavailable forecasts', async () => {
  const data = flaggedResult(); await render(<KitAnalysisVisualization data={data} section="scores" />);
  expect(screen.getByText('[08:47:40, 08:47:50) · 1 flagged pairs')).toBeTruthy();
  expect(screen.getByText('[08:49:30, 08:49:40) · 1 flagged pairs')).toBeTruthy();
  expect(screen.getByText('Forecast values are not included in this API response. A comparison graph is unavailable.')).toBeTruthy();
  expect(screen.getAllByTestId('flagged-window-band')).toHaveLength(2); expect(screen.getByTestId('novelty-threshold-line')).toBeTruthy();
  const deviation = data.predictions[0].top_signal_deviations[0];
  expect(screen.getByText(`1. ${data.signals.find(s => s.name === deviation.signal)!.display_name}: ${plotNumber(deviation.normalized_error)} (dimensionless)`)).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'Next anomaly score reading' }));
  expect(screen.getByText('Selected pair: pair-000001')).toBeTruthy();
});
it('renders no-flag empty state without inventing model accuracy', async () => {
  await render(<KitAnalysisVisualization data={sampleResult()} section="scores" />);
  expect(screen.getByText('No target windows exceeded the novelty threshold.')).toBeTruthy();
  expect(screen.queryAllByTestId('flagged-window-band')).toHaveLength(0);
  expect(screen.queryByText(/confidence:|accuracy:/i)).toBeNull();
});
it('selects actual signals with units, zero readings and partial missingness', async () => {
  const data = sampleResult(); data.telemetry[0].medians.speed_kmph = 0; data.telemetry[0].missing_fractions.speed_kmph = 0.25;
  await render(<KitAnalysisVisualization data={data} section="telemetry" />);
  expect(within(screen.getByTestId('Telemetry inspection')).getByText('0 km/h')).toBeTruthy(); expect(screen.getByText('Missing readings: 25% of this window.')).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'Telemetry signal' }));
  const coolant = data.signals[0]; await fireEvent.press(screen.getByRole('button', { name: `${coolant.display_name} (${coolant.unit})` }));
  expect(within(screen.getByTestId('Telemetry inspection')).getByText(`${plotNumber(data.telemetry[0].medians.coolant_temp_c)} ${coolant.unit}`)).toBeTruthy();
});
it('switches segments without joining clock timelines', async () => {
  const data = sampleResult(), base = data.telemetry[0];
  data.telemetry.push({ ...base, window: { ...base.window, id: 'another-window', segment_id: 1 } });
  await render(<KitAnalysisVisualization data={data} section="telemetry" />);
  await fireEvent.press(screen.getByRole('button', { name: 'Telemetry recording segment' }));
  await fireEvent.press(screen.getByRole('button', { name: analysisSegments(data)[1].label }));
  expect(screen.getByText(/another-window/)).toBeTruthy();
  expect(screen.getByText('Showing readings 1–1 of 1. All pages retain original backend values.')).toBeTruthy();
});
it('renders honest no-point and missing-value states', async () => {
  const view = await render(<KitLineChart title="Telemetry" unit="km/h" points={[]} />);
  expect(screen.getByText('No telemetry points are available.')).toBeTruthy();
  await view.rerender(<KitLineChart title="Telemetry" unit="km/h" points={[{ ...reading(), value: null }]} />);
  expect(screen.getByText('Measurement unavailable')).toBeTruthy();
});
it('bounds SVG work to 48 points while preserving access to 1000 readings', async () => {
  const base = reading();
  // Repeated genuine median with synthetic identities/times for pagination load testing only.
  const points = Array.from({ length: 1000 }, (_, i) => ({ ...base, id: `load-${i}`, window: {
    ...base.window, start_seconds: i * 10, end_seconds: i * 10 + 10 } }));
  const inspect = jest.fn(); await render(<KitLineChart title="Telemetry" unit="km/h" points={points} onInspect={inspect} />);
  expect(screen.getByText('Showing readings 1–48 of 1000. All pages retain original backend values.')).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'Next telemetry page' })); expect(inspect).toHaveBeenLastCalledWith(points[48]);
  expect(screen.getByText('Showing readings 49–96 of 1000. All pages retain original backend values.')).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'Previous telemetry page' })); expect(inspect).toHaveBeenLastCalledWith(points[0]);
});
it('keeps geometry finite for extreme positive and negative finite readings', async () => {
  const base = reading(); const points = [-1e308, 1e308].map((value, i) => ({ ...base, id: `${i}`, value,
    window: { ...base.window, start_seconds: i * 10, end_seconds: i * 10 + 10 } }));
  const view = await render(<KitLineChart title="Telemetry" unit="test" points={points} />);
  expect(JSON.stringify(view.toJSON())).not.toMatch(/NaN|Infinity/);
});
function connectedApi() {
  return { samples: jest.fn(async () => ({ schema_version: 1 as const, samples: [sampleResult().sample] })),
    sample: jest.fn(async () => sampleResult()), upload: jest.fn(async () => uploadResult()) };
}
async function analyze() {
  await fireEvent.press(screen.getByRole('button', { name: 'Prerecorded KIT sample' }));
  await fireEvent.press(await screen.findByRole('button', { name: 'KIT first-pair test excerpt' }));
  await fireEvent.press(screen.getByRole('button', { name: 'Analyze KIT sample' }));
}
it('removes charts on demo selection and keeps illustrative values separate', async () => {
  const api = connectedApi(); function Connected() { return <AIInsightsScreen analysis={useAnalysis('alice', false, undefined, api)} />; }
  await render(<Connected />); await analyze(); expect(screen.getByTestId('kit-scores-visualization')).toBeTruthy();
  await fireEvent(screen.getByRole('switch'), 'valueChange', true);
  expect(screen.queryByTestId('kit-scores-visualization')).toBeNull(); expect(screen.getByText('94.2%')).toBeTruthy();
  expect(screen.queryByTestId('Telemetry chart')).toBeNull();
});
it('removes charts on account switching and logout', async () => {
  const api = connectedApi();
  function Connected({ uid }: { uid: string | null }) { return <AIInsightsScreen analysis={useAnalysis(uid, false, undefined, api)} />; }
  const view = await render(<Connected uid="alice" />); await analyze(); expect(screen.getByTestId('kit-scores-visualization')).toBeTruthy();
  await view.rerender(<Connected uid="bob" />); expect(screen.queryByTestId('kit-scores-visualization')).toBeNull();
  await view.rerender(<Connected uid={null} />); expect(screen.queryByTestId('kit-telemetry-visualization')).toBeNull();
});
it('preserves Retry and clears charts on explicit cancellation', async () => {
  const api = connectedApi(); api.sample.mockRejectedValueOnce(new Error('Service temporarily unavailable'));
  function Connected() { return <AIInsightsScreen analysis={useAnalysis('alice', false, undefined, api as AnalysisApi)} />; }
  await render(<Connected />); await analyze(); expect(screen.queryByTestId('kit-scores-visualization')).toBeNull();
  await fireEvent.press(screen.getByRole('button', { name: 'Retry analysis' })); expect(screen.getByTestId('kit-scores-visualization')).toBeTruthy();
  await fireEvent.press(screen.getByRole('button', { name: 'Clear analysis' })); expect(screen.queryByTestId('kit-scores-visualization')).toBeNull();
});
it('uses the same graphs for uploaded CSV without persistence', async () => {
  const data = parseKitAnalysis(uploadResult()); await render(<KitAnalysisVisualization data={data} section="telemetry" />);
  expect(screen.getByTestId('Telemetry chart')).toBeTruthy(); expect(data.source_type).toBe('uploaded_csv'); expect(data.persisted).toBe(false);
});
it('supports tapping the graph and accessible reading navigation', async () => {
  const points = telemetryPoints(sampleResult(), analysisSegments(sampleResult())[0].value, 'speed_kmph'), inspect = jest.fn();
  await render(<KitLineChart title="Telemetry" unit="km/h" points={points} onInspect={inspect} />);
  const plot = screen.getByRole('image');
  await fireEvent(plot, 'layout', { nativeEvent: { layout: { width: 300 } } });
  await fireEvent.press(plot, { nativeEvent: { locationX: 170 } });
  expect(inspect).toHaveBeenLastCalledWith(points[1]);
  await fireEvent.press(screen.getByRole('button', { name: 'Previous telemetry reading' }));
  expect(inspect).toHaveBeenLastCalledWith(points[0]);
});
it('paginates interval details without hiding remaining backend intervals', async () => {
  const data = flaggedResult();
  // Repeated genuine intervals are only a UI pagination fixture, not a valid API analysis.
  data.flagged_intervals = Array.from({ length: 13 }, () => data.flagged_intervals[0]);
  await render(<KitAnalysisVisualization data={data} section="scores" />);
  expect(screen.getAllByText('[08:47:40, 08:47:50) · 1 flagged pairs')).toHaveLength(12);
  await fireEvent.press(screen.getByRole('button', { name: 'Next intervals' }));
  expect(screen.getByText('Interval page 2 of 2')).toBeTruthy();
  expect(screen.getAllByText('[08:47:40, 08:47:50) · 1 flagged pairs')).toHaveLength(1);
});
