// Web preview sessions stay in memory; reload requires login.
let session: string | null = null;
export const sessionStorage = {
  get: async () => session,
  set: async (value: string) => { session = value; },
  remove: async () => { session = null; },
};
