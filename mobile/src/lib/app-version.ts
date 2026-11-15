// Read installed version only if the native capability exists; config version is labeled separately.
import Constants from 'expo-constants';
import { requireOptionalNativeModule } from 'expo-modules-core';

export function appVersion() {
  let installed: string | null = null;
  try {
    const native = requireOptionalNativeModule<{ nativeApplicationVersion?: string | null }>('ExpoApplication');
    if (typeof native?.nativeApplicationVersion === 'string' && native.nativeApplicationVersion.trim()) {
      installed = native.nativeApplicationVersion;
    }
  } catch { /* Optional capability may be absent in an older development binary. */ }
  return { installed, configured: Constants.expoConfig?.version ?? null };
}
