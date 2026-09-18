// Google sign-in is currently supported on Android only.
export const googleAvailable = false;
export async function getGoogleIdToken(): Promise<string | null> {
  throw new Error('Google sign-in is available in the Android app.');
}
