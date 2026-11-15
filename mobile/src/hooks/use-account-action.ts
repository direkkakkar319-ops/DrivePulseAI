// Transient action feedback with duplicate-request and unmount protection; no account cache.
import { useEffect, useRef, useState } from 'react';

export function useAccountAction(formatError: (failure: unknown) => string) {
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [message, setMessage] = useState('');
  const pending = useRef(false), alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  function clear() { setError(''); setMessage(''); }
  async function run(operation: () => Promise<string | void>) {
    if (pending.current || !alive.current) return;
    pending.current = true; setBusy(true); clear();
    try { const result = await operation(); if (alive.current && result) setMessage(result); }
    catch (failure) { if (alive.current) setError(formatError(failure)); }
    finally { pending.current = false; if (alive.current) setBusy(false); }
  }
  return { busy, error, message, run, clear };
}
