// Functional recorded-data UI and async provider tests with real reviewed local clips.
import { act, fireEvent, render, screen } from '@testing-library/react-native';
import { Text } from 'react-native';
import { RecordedReplayProvider, useReplay } from '../src/store/recordedReplayStore';
import { localRecordedProvider, type RecordedTelemetryProvider } from '../src/api/recorded-telemetry-provider';
import { OverviewScreen, ReplayScreen, InsightsScreen, InsightDetailScreen } from '../src/components/recorded/screens';
import { DataGate } from '../src/components/recorded/ui';
const mockPush = jest.fn();
let mockParams: Record<string, string> = {};
jest.mock('expo-router', () => ({
  useRouter: () => ({ push: mockPush, replace: jest.fn(), back: jest.fn(), canGoBack: () => true }),
  useLocalSearchParams: () => mockParams,
}));
beforeEach(() => { jest.clearAllMocks(); mockParams = {}; });
afterEach(() => jest.useRealTimers());
it('shows recorded units and navigates without the conventional-vehicle demo', async () => {
  await render(<RecordedReplayProvider><OverviewScreen /></RecordedReplayProvider>);
  expect(await screen.findByText('Recorded data')).toBeTruthy();
  expect(screen.getByText('High-voltage battery')).toBeTruthy();
  expect(screen.queryByText('Illustrative assessment')).toBeNull();
  await fireEvent.press(screen.getByText('Open recorded replay'));
  expect(mockPush).toHaveBeenCalledWith('/(main)/replay');
  await fireEvent.press(screen.getByLabelText('Account'));
  expect(mockPush).toHaveBeenCalledWith('/(main)/account');
});
it('selects clips, plays actual sample steps, pauses and restarts', async () => {
  await render(<RecordedReplayProvider><ReplayScreen /></RecordedReplayProvider>);
  await screen.findByText('Typical telemetry · Trip 153');
  await fireEvent.press(screen.getByText('Unusual pattern · Trip 167'));
  expect(await screen.findByText('TRIP 167')).toBeTruthy();
  jest.useFakeTimers();
  await fireEvent.press(screen.getByText('Play'));
  await act(async () => { jest.advanceTimersByTime(250); });
  expect(screen.getByText(/Sample 2 of 205/)).toBeTruthy();
  await fireEvent.press(screen.getByText('Pause'));
  await act(async () => { jest.advanceTimersByTime(2000); });
  expect(screen.getByText(/Sample 2 of 205/)).toBeTruthy();
  await fireEvent.press(screen.getByText('Restart'));
  expect(screen.getByText(/Sample 1 of 205/)).toBeTruthy();
  await fireEvent.press(screen.getByText('Typical telemetry · Trip 153'));
  expect(await screen.findByText(/Sample 1 of 211/)).toBeTruthy();
});
it('opens saved insight details with source clip identity', async () => {
  function Choose() { const { selectClip } = useReplay(); return <Text onPress={() => { void selectClip('leaf-unusual'); }}>Choose unusual</Text>; }
  await render(<RecordedReplayProvider><Choose /><InsightsScreen /></RecordedReplayProvider>);
  await screen.findByText('TRIP 153');
  await fireEvent.press(screen.getByText('Choose unusual'));
  await screen.findAllByText('View interval details');
  await fireEvent.press(screen.getAllByText('View interval details')[0]);
  expect(mockPush).toHaveBeenCalledWith({ pathname: '/(main)/recorded-insight/[id]', params: { clipId: 'leaf-unusual', id: 'leaf-unusual-1759328' } });
});
it('loads detail directly without changing the selected replay', async () => {
  mockParams = { clipId: 'leaf-unusual', id: 'leaf-unusual-1759328' };
  await render(<RecordedReplayProvider><InsightDetailScreen /></RecordedReplayProvider>);
  expect(await screen.findByText('109')).toBeTruthy();
  expect(screen.getByText(/does not establish a cause/)).toBeTruthy();
});
it('handles loading, empty and failed data without fabricated values', async () => {
  const provider: RecordedTelemetryProvider = { listClips: () => new Promise(() => {}), getClip: localRecordedProvider.getClip };
  const view = await render(<RecordedReplayProvider provider={provider}><OverviewScreen /></RecordedReplayProvider>);
  expect(screen.getByLabelText('Loading recorded telemetry')).toBeTruthy();
  await view.unmount();
  const empty = await render(<RecordedReplayProvider provider={{ ...provider, listClips: async () => [] }}><OverviewScreen /></RecordedReplayProvider>);
  expect(await screen.findByText('No recorded measurements available')).toBeTruthy();
  await empty.unmount();
  await render(<RecordedReplayProvider provider={{ ...localRecordedProvider, getClip: async () => { throw new Error('Unavailable offline'); } }}><OverviewScreen /></RecordedReplayProvider>);
  expect(await screen.findByText('Unavailable offline')).toBeTruthy();
  expect(screen.queryByText(/Saved score:/)).toBeNull();
});
it('ignores an older clip response after a newer selection', async () => {
  const a = await localRecordedProvider.getClip('leaf-typical');
  const b = await localRecordedProvider.getClip('leaf-unusual');
  let resolveOld!: (clip: typeof a) => void;
  const provider: RecordedTelemetryProvider = { listClips: localRecordedProvider.listClips, getClip: id => id === a.clip_id ? new Promise(resolve => { resolveOld = resolve; }) : Promise.resolve(b) };
  function Harness() { const { selectClip } = useReplay(); return <><Text onPress={() => { void selectClip(b.clip_id); }}>Select B</Text><DataGate>{clip => <Text>{clip.clip_id}</Text>}</DataGate></>; }
  await render(<RecordedReplayProvider provider={provider}><Harness /></RecordedReplayProvider>);
  await fireEvent.press(screen.getByText('Select B'));
  expect(await screen.findByText(b.clip_id)).toBeTruthy();
  await act(async () => resolveOld(a));
  expect(screen.getByText(b.clip_id)).toBeTruthy();
  expect(screen.queryByText(a.clip_id)).toBeNull();
});
