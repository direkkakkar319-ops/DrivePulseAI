// Android Credential Manager integration, loaded only on demand.
import Constants from 'expo-constants';
import { Platform } from 'react-native';
export const googleAvailable = Platform.OS === 'android' &&
  Constants.appOwnership !== 'expo' && Boolean(process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID);
export async function getGoogleIdToken(): Promise<string | null> {
  if (!googleAvailable) throw { code: 'auth/google-sign-in-unavailable' };
  const { GoogleOneTapSignIn, isSuccessResponse, isCancelledResponse,
    isErrorWithCode, statusCodes } = await import('react-native-nitro-google-signin');
  try {
    GoogleOneTapSignIn.configure({ webClientId: process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID! });
    await GoogleOneTapSignIn.checkPlayServices();
    const result = await GoogleOneTapSignIn.presentExplicitSignIn();
    if (isCancelledResponse(result)) return null;
    if (!isSuccessResponse(result) || !result.data.idToken) {
      throw new Error('Google sign-in did not complete.');
    }
    return result.data.idToken;
  } catch (error) {
    if (isErrorWithCode(error) && error.code === statusCodes.SIGN_IN_CANCELLED) return null;
    throw { code: 'auth/google-sign-in-failed' };
  }
}
