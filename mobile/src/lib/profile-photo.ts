// Image-library adapter returning only local preview metadata; no account or upload operations.
import { ProfilePhotoSelectionError, type PickProfilePhoto } from '@/types/profile-onboarding';

const permissionErrors = new Set([
  'E_NO_LIBRARY_PERMISSION',
  'ERR_MISSING_CAMERA_PERMISSION',
  'ERR_USER_REJECTED_PERMISSIONS',
]);

export const pickProfilePhoto: PickProfilePhoto = async () => {
  let picker: typeof import('expo-image-picker');
  try {
    // Older development builds can still open the app; selecting a photo reports
    // unavailable until the native module has been included in a rebuilt binary.
    // Keep the load synchronous within the user action (also needed by web pickers).
    // eslint-disable-next-line @typescript-eslint/no-require-imports -- Catch missing native modules at selection time.
    picker = require('expo-image-picker') as typeof import('expo-image-picker');
  } catch {
    throw new ProfilePhotoSelectionError('unavailable');
  }

  let result: Awaited<ReturnType<typeof picker.launchImageLibraryAsync>>;
  try {
    // Expo's system library picker needs no broad photo-library permission for
    // image-only selection on supported native platforms. Never request camera/audio.
    result = await picker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      allowsMultipleSelection: false,
      allowsEditing: false,
      quality: 0.8,
      exif: false,
      base64: false,
    });
  } catch (error) {
    const code = (error as { code?: unknown } | null)?.code;
    if (typeof code === 'string' && permissionErrors.has(code)) throw new ProfilePhotoSelectionError('permission');
    if (code === 'ERR_UNAVAILABLE') throw new ProfilePhotoSelectionError('unavailable');
    throw error;
  }
  if (result.canceled) return null;
  const asset = result.assets?.[0];
  if (!asset || typeof asset.uri !== 'string' || !asset.uri.trim()
    || !Number.isFinite(asset.width) || asset.width <= 0
    || !Number.isFinite(asset.height) || asset.height <= 0
    || (asset.type != null && asset.type !== 'image')
    || (asset.mimeType != null && !asset.mimeType.startsWith('image/'))) {
    throw new ProfilePhotoSelectionError('invalid-image');
  }
  return { uri: asset.uri, width: asset.width, height: asset.height,
    ...(asset.mimeType ? { mimeType: asset.mimeType } : {}) };
};
