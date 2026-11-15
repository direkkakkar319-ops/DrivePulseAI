// Public NHTSA suggestions only; no account data, Firebase tokens, API keys, images or vehicle writes.
export interface CatalogMake { id: number; name: string }
export interface VehicleCatalog {
  makes: () => Promise<readonly CatalogMake[]>;
  models: (make: CatalogMake) => Promise<readonly string[]>;
}
const base = 'https://vpic.nhtsa.dot.gov/api/vehicles';
const ttl = 6 * 60 * 60 * 1000;
// Cache only successful public responses, with bounded model entries and shared in-flight requests.
const cache = new Map<string, { expires: number; data: unknown }>();
const pending = new Map<string, Promise<unknown>>();
async function request<T>(path: string, parse: (rows: unknown[]) => T): Promise<T> {
  const hit = cache.get(path);
  if (hit && hit.expires > Date.now()) return hit.data as T;
  if (pending.has(path)) return pending.get(path) as Promise<T>;
  const task = (async () => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetch(`${base}/${path}?format=json`, { signal: controller.signal });
      if (!response.ok) throw new Error('Catalog request failed');
      const body = await response.json();
      if (!Array.isArray(body?.Results)) throw new Error('Invalid catalog response');
      const data = parse(body.Results);
      if (cache.size >= 33) cache.delete(cache.keys().next().value!);
      cache.set(path, { data, expires: Date.now() + ttl });
      return data;
    } catch { throw new Error('Could not load vehicle suggestions. You can retry or enter your vehicle manually.'); }
    finally { clearTimeout(timer); }
  })();
  pending.set(path, task);
  try { return await task; } finally { pending.delete(path); }
}

export const vehicleCatalog: VehicleCatalog = {
  makes: () => request('GetAllMakes', rows => {
    const byName = new Map<string, CatalogMake>();
    for (const item of rows) {
      if (!item || typeof item !== 'object') throw new Error('Invalid make');
      const row = item as Record<string, unknown>;
      if (!Number.isInteger(row.Make_ID) || (row.Make_ID as number) <= 0 || typeof row.Make_Name !== 'string' || !row.Make_Name.trim()) throw new Error('Invalid make');
      const name = row.Make_Name.trim();
      byName.set(name.toLocaleLowerCase(), { id: row.Make_ID as number, name });
    }
    return [...byName.values()].sort((a, b) => a.name.localeCompare(b.name));
  }),
  models: make => request(`GetModelsForMakeId/${make.id}`, rows => {
    const names = new Map<string, string>();
    for (const item of rows) {
      if (!item || typeof item !== 'object') throw new Error('Invalid model');
      const row = item as Record<string, unknown>;
      if (row.Make_ID !== make.id || typeof row.Model_Name !== 'string' || !row.Model_Name.trim()) throw new Error('Model belongs to another make');
      const name = row.Model_Name.trim(); names.set(name.toLocaleLowerCase(), name);
    }
    return [...names.values()].sort((a, b) => a.localeCompare(b));
  }),
};
