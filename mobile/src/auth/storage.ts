// Persist native sessions in OS secure storage.
import * as SecureStore from 'expo-secure-store';
const key = 'drivepulse.session';
export const sessionStorage = {
  get: () => SecureStore.getItemAsync(key),
  set: (value: string) => SecureStore.setItemAsync(key, value),
  remove: () => SecureStore.deleteItemAsync(key),
};
