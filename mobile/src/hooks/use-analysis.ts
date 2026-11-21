// Transient analysis lifecycle. Tokens and results are never persisted or sent to History.
import { useCallback, useEffect, useRef, useState } from 'react';
import { AnalysisCancelled, analysisApi, validateCsvFile } from '@/api/analysis';
import { isRecordingDate } from '@/lib/kit-analysis';
import type { AnalysisApi, KitAnalysis, KitCsvFile, KitSampleCatalog, KitSource } from '@/types/kit-analysis';

type Resource<T> = { status: 'idle' } | { status: 'loading' } | { status: 'error'; message: string } | { status: 'ready'; data: T };
export type PickKitCsv = () => Promise<KitCsvFile | null>;

export function useAnalysis(uid: string | null, initialDemo = false, pickCsv?: PickKitCsv, api: AnalysisApi = analysisApi) {
  const [source, setSource] = useState<KitSource>(initialDemo ? { kind: 'demo' } : { kind: 'none' });
  const [catalog, setCatalog] = useState<Resource<KitSampleCatalog>>({ status: 'idle' });
  const [result, setResult] = useState<Resource<KitAnalysis>>({ status: 'idle' });
  const [recordingDate, setDate] = useState('');
  const [selecting, setSelecting] = useState(false), [selectionError, setSelectionError] = useState('');
  const request = useRef<AbortController | null>(null), catalogRequest = useRef<AbortController | null>(null);
  const ticket = useRef(0), pickTicket = useRef(0), alive = useRef(false), picking = useRef(false);
  const activeUid = useRef(uid);
  const owner = useRef(uid);
  const [ownerUid, setOwnerUid] = useState(uid);

  const invalidate = useCallback(() => { ticket.current++; request.current?.abort(); request.current = null; }, []);
  const invalidatePicker = useCallback(() => { pickTicket.current++; picking.current = false; }, []);
  useEffect(() => {
    alive.current = true; activeUid.current = uid;
    if (owner.current !== uid) {
      owner.current = uid;
      void Promise.resolve().then(() => {
        if (!alive.current || activeUid.current !== uid) return;
        setSource(initialDemo ? { kind: 'demo' } : { kind: 'none' }); setCatalog({ status: 'idle' });
        setResult({ status: 'idle' }); setDate(''); setSelecting(false); setSelectionError('');
        picking.current = false; catalogRequest.current = null; setOwnerUid(uid);
      });
    }
    return () => {
      alive.current = false; invalidate(); catalogRequest.current?.abort(); invalidatePicker();
    };
  }, [uid, initialDemo, invalidate, invalidatePicker]);
  // Routes key this hook by UID. Mask any old render immediately if reused by another consumer.
  const sameAccount = ownerUid === uid;
  function change(next: KitSource) {
    invalidate(); pickTicket.current++; picking.current = false;
    setSelecting(false); setSelectionError(''); setSource(next); setResult({ status: 'idle' });
  }
  async function loadSamples() {
    if (!uid || catalogRequest.current) return;
    const controller = new AbortController(); catalogRequest.current = controller;
    setCatalog({ status: 'loading' });
    try {
      const data = await api.samples({ uid, signal: controller.signal });
      if (alive.current && !controller.signal.aborted && activeUid.current === uid) setCatalog({ status: 'ready', data });
    } catch (failure) {
      if (alive.current && !controller.signal.aborted && !(failure instanceof AnalysisCancelled)) {
        setCatalog({ status: 'error', message: failure instanceof Error ? failure.message : 'Could not load KIT samples.' });
      } else if (alive.current && activeUid.current === uid && failure instanceof AnalysisCancelled) setCatalog({ status: 'idle' });
    } finally { if (catalogRequest.current === controller) catalogRequest.current = null; }
  }
  function selectSample(id: string) {
    if (catalog.status === 'ready' && catalog.data.samples.some(s => s.id === id)) change({ kind: 'sample', sampleId: id });
  }
  async function selectCsv() {
    if (!pickCsv || picking.current || !uid) return;
    const current = ++pickTicket.current; picking.current = true; setSelecting(true); setSelectionError('');
    // Choosing a replacement cancels inference immediately, even if the picker is later dismissed.
    invalidate(); setResult({ status: 'idle' });
    try {
      const file = await pickCsv();
      if (!alive.current || current !== pickTicket.current || activeUid.current !== uid || !file) return;
      validateCsvFile(file); setSource({ kind: 'csv', file }); setDate('');
    } catch (failure) {
      if (alive.current && current === pickTicket.current) setSelectionError(failure instanceof Error ? failure.message : 'Could not select CSV.');
    } finally {
      if (alive.current && current === pickTicket.current) { picking.current = false; setSelecting(false); }
    }
  }
  async function run() {
    if (!uid || !sameAccount || selecting || request.current || (source.kind !== 'sample' && source.kind !== 'csv')) return;
    if (source.kind === 'sample' && catalog.status === 'ready' && !catalog.data.samples.some(s => s.id === source.sampleId)) {
      setResult({ status: 'error', message: 'Choose an available KIT sample from the current list.' }); return;
    }
    if (source.kind === 'csv' && !isRecordingDate(recordingDate)) {
      setResult({ status: 'error', message: 'Enter the actual recording date as YYYY-MM-DD.' }); return;
    }
    const current = ++ticket.current, controller = new AbortController(); request.current = controller;
    setResult({ status: 'loading' });
    try {
      const context = { uid, signal: controller.signal };
      const data = source.kind === 'sample' ? await api.sample(source.sampleId, context) : await api.upload(source.file, recordingDate, context);
      if (alive.current && current === ticket.current && !controller.signal.aborted && activeUid.current === uid) setResult({ status: 'ready', data });
    } catch (failure) {
      if (alive.current && current === ticket.current && !controller.signal.aborted && !(failure instanceof AnalysisCancelled)) {
        setResult({ status: 'error', message: failure instanceof Error ? failure.message : 'Analysis could not be completed.' });
      } else if (alive.current && current === ticket.current) setResult({ status: 'idle' });
    } finally { if (request.current === controller) request.current = null; }
  }
  return {
    source: sameAccount ? source : { kind: 'none' } as KitSource,
    catalog: sameAccount ? catalog : { status: 'idle' } as Resource<KitSampleCatalog>,
    result: sameAccount ? result : { status: 'idle' } as Resource<KitAnalysis>,
    recordingDate: sameAccount ? recordingDate : '', selecting: sameAccount && selecting,
    selectionError: sameAccount ? selectionError : '', canPickCsv: Boolean(pickCsv),
    loadSamples, selectSample, selectCsv, run,
    useDemo: (enabled: boolean) => change(enabled ? { kind: 'demo' } : { kind: 'none' }),
    clearCsv: () => { change({ kind: 'none' }); setDate(''); },
    setRecordingDate: (date: string) => { invalidate(); setResult({ status: 'idle' }); setDate(date); },
    cancel: () => { invalidate(); setResult({ status: 'idle' }); },
  };
}
export type AnalysisController = ReturnType<typeof useAnalysis>;
