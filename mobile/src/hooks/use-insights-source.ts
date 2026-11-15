// Exclusive demo/CSV selection with cancellation, duplicate-request, and unmount protection.
import { useEffect, useRef, useState } from 'react';
import type { InsightsSource, PickCsv } from '@/types/ai-insights';

export function useInsightsSource(initialDemo: boolean, pickCsv?: PickCsv) {
  const [source, setSource] = useState<InsightsSource>(initialDemo ? { kind: 'demo' } : { kind: 'none' });
  const [selecting, setSelecting] = useState(false);
  const [error, setError] = useState('');
  const busy = useRef(false), alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);

  function useDemo(enabled: boolean) {
    if (busy.current) return;
    setError('');
    setSource(enabled ? { kind: 'demo' } : { kind: 'none' });
  }
  async function selectCsv() {
    if (!pickCsv || busy.current) return;
    busy.current = true; setSelecting(true); setError('');
    try {
      const file = await pickCsv();
      if (!alive.current || !file) return;
      if (!file.name.trim().toLowerCase().endsWith('.csv')) throw new Error('Please select a CSV file (.csv).');
      if (file.sizeBytes !== undefined && (!Number.isFinite(file.sizeBytes) || file.sizeBytes < 0)) {
        throw new Error('The file size could not be read. Please select the file again.');
      }
      setSource({ kind: 'csv', file });
    } catch (failure) {
      if (alive.current) setError(failure instanceof Error ? failure.message : 'Could not select a file. Please try again.');
    } finally {
      busy.current = false;
      if (alive.current) setSelecting(false);
    }
  }
  function clearCsv() { if (!busy.current) { setSource({ kind: 'none' }); setError(''); } }
  return { source, selecting, error, useDemo, selectCsv, clearCsv };
}
