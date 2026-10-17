// Shared recording selection and sample-by-sample playback inside the authenticated area.
import { createContext, useCallback, useContext, useEffect, useRef, useState, type PropsWithChildren } from 'react';
import { AppState } from 'react-native';
import { localRecordedProvider, type RecordedTelemetryProvider } from '@/api/recorded-telemetry-provider';
import { nextDelay, transition, validateClip, type ReplayAction } from '@/lib/recorded-replay';
import type { ApiState, ReplayClip, ReplayClipMetadata, ReplayState } from '@/types/recorded-telemetry';
function useRecordedState(provider: RecordedTelemetryProvider) {
  const [catalog, setCatalog] = useState<ApiState<ReplayClipMetadata[]>>({ status: 'loading' });
  const [resource, setResource] = useState<ApiState<ReplayClip>>({ status: 'loading' });
  const [selectedId, setSelectedId] = useState('');
  const [replay, setReplay] = useState<ReplayState>({ status: 'paused', index: 0 });
  const request = useRef(0);
  const catalogRequest = useRef(0);
  const selectClip = useCallback(async (id: string) => {
    const ticket = ++request.current;
    setSelectedId(id); setResource({ status: 'loading' }); setReplay({ status: 'paused', index: 0 });
    try {
      const clip = validateClip(await provider.getClip(id));
      if (clip.clip_id !== id) throw new Error('The provider returned a different recording.');
      if (ticket === request.current) setResource(clip.samples.length ? { status: 'ready', data: clip } : { status: 'empty' });
    } catch (error) {
      if (ticket === request.current) setResource({ status: 'error', message: error instanceof Error ? error.message : 'Could not load the recording.' });
    }
  }, [provider]);
  const reload = useCallback(async () => {
    const ticket = ++catalogRequest.current;
    setCatalog({ status: 'loading' });
    try {
      const clips = await provider.listClips();
      if (ticket !== catalogRequest.current) return;
      setCatalog(clips.length ? { status: 'ready', data: clips } : { status: 'empty' });
      if (clips.length) await selectClip(clips[0].clip_id);
      else setResource({ status: 'empty' });
    } catch {
      if (ticket === catalogRequest.current) setCatalog({ status: 'error', message: 'Could not load recordings. Try again.' });
    }
  }, [provider, selectClip]);
  const invalidateRequests = useCallback(() => {
    request.current++;
    catalogRequest.current++;
  }, []);
  useEffect(() => {
    let active = true;
    void Promise.resolve().then(() => { if (active) void reload(); });
    return () => { active = false; invalidateRequests(); };
  }, [reload, invalidateRequests]);
  const clip = resource.status === 'ready' ? resource.data : undefined;
  const dispatch = useCallback((action: ReplayAction) => setReplay(s => transition(s, action, clip?.samples.length ?? 0)), [clip]);
  useEffect(() => {
    if (!clip || replay.status !== 'playing') return;
    const delay = nextDelay(clip, replay.index);
    if (delay === null) return;
    // One observed sample per tick: a delayed frame cannot jump over an alert boundary.
    const timer = setTimeout(() => dispatch('next'), delay);
    return () => clearTimeout(timer);
  }, [clip, replay, dispatch]);
  useEffect(() => {
    const subscription = AppState.addEventListener('change', state => { if (state !== 'active') dispatch('pause'); });
    return () => subscription.remove();
  }, [dispatch]);
  return { catalog, resource, selectedId, selectClip, reload, replay, dispatch, clip, sample: clip?.samples[replay.index], provider };
}
const Context = createContext<ReturnType<typeof useRecordedState> | null>(null);
export function RecordedReplayProvider({ children, provider = localRecordedProvider }: PropsWithChildren<{ provider?: RecordedTelemetryProvider }>) {
  return <Context.Provider value={useRecordedState(provider)}>{children}</Context.Provider>;
}
export function useReplay() {
  const context = useContext(Context);
  if (!context) throw new Error('RecordedReplayProvider required');
  return context;
}
