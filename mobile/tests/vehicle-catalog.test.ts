// Public catalog wire validation, make-ID filtering, bounded requests and successful-response caching.
import type { VehicleCatalog } from '../src/api/vehicle-catalog';
let catalog: VehicleCatalog;
const originalFetch = global.fetch;
beforeEach(() => { jest.resetModules(); catalog = require('../src/api/vehicle-catalog').vehicleCatalog; global.fetch = jest.fn(); });
afterEach(() => { global.fetch = originalFetch; jest.useRealTimers(); });
const response = (Results: unknown, status = 200) => ({ ok: status === 200, status, json: async () => ({ Results }) });

it('loads all makes without Firebase credentials and caches successful responses', async () => {
  (fetch as jest.Mock).mockResolvedValue(response([{ Make_ID: 448, Make_Name: 'TOYOTA' }, { Make_ID: 2146, Make_Name: 'MAHINDRA' }]));
  const result = await catalog.makes();
  expect(result.map(make => make.name)).toEqual(['MAHINDRA', 'TOYOTA']);
  await catalog.makes();
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(fetch).toHaveBeenCalledWith('https://vpic.nhtsa.dot.gov/api/vehicles/GetAllMakes?format=json', { signal: expect.anything() });
});

it('uses exact make IDs rather than partial-name model matching', async () => {
  (fetch as jest.Mock).mockResolvedValue(response([{ Make_ID: 448, Model_Name: 'Corolla' }, { Make_ID: 448, Model_Name: 'Corolla' }]));
  expect(await catalog.models({ id: 448, name: 'TOYOTA' })).toEqual(['Corolla']);
  expect(fetch).toHaveBeenCalledWith('https://vpic.nhtsa.dot.gov/api/vehicles/GetModelsForMakeId/448?format=json', expect.anything());
});

it.each([response(null), response([{ Make_ID: 0, Make_Name: 'Broken' }]), response([], 429)])('rejects unavailable or malformed make catalogs without caching failures', async value => {
  (fetch as jest.Mock).mockResolvedValue(value);
  await expect(catalog.makes()).rejects.toThrow('retry or enter');
  await expect(catalog.makes()).rejects.toThrow();
  expect(fetch).toHaveBeenCalledTimes(2);
});

it('rejects models belonging to another manufacturer', async () => {
  (fetch as jest.Mock).mockResolvedValue(response([{ Make_ID: 2146, Model_Name: 'Wrong make' }]));
  await expect(catalog.models({ id: 448, name: 'TOYOTA' })).rejects.toThrow();
});

it('shares in-flight requests and returns a genuine empty model list', async () => {
  let resolve!: (value: ReturnType<typeof response>) => void;
  (fetch as jest.Mock).mockImplementation(() => new Promise(done => { resolve = done; }));
  const a = catalog.models({ id: 448, name: 'TOYOTA' }); const b = catalog.models({ id: 448, name: 'TOYOTA' });
  resolve(response([]));
  expect(await a).toEqual([]); expect(await b).toEqual([]);
  expect(fetch).toHaveBeenCalledTimes(1);
});

it('aborts slow catalog requests and permits a later retry', async () => {
  jest.useFakeTimers();
  (fetch as jest.Mock).mockImplementation((_url, options) => new Promise((_resolve, reject) => {
    options.signal.addEventListener('abort', () => reject(new Error('aborted')));
  }));
  const assertion = expect(catalog.makes()).rejects.toThrow('manually');
  await jest.advanceTimersByTimeAsync(8000); await assertion;
  (fetch as jest.Mock).mockResolvedValue(response([]));
  expect(await catalog.makes()).toEqual([]);
});
