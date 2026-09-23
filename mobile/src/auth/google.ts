// Android Credential Manager integration, loaded only on demand.
import Constants from 'expo-constants';
import { Platform } from 'react-native';
export const googleAvailable = Platform.OS === 'android' &&
  Constants.appOwnership !== 'expo' && Boolean(process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID);
export async function getGoogleIdToken(): Promise<string | null> {
  if (!googleAvailable) throw new Error('Google sign-in is unavailable in this build.');
  const { GoogleOneTapSignIn, isSuccessResponse, isCancelledResponse,
    isErrorWithCode, statusCodes } = await import('react-native-nitro-google-signin');
  GoogleOneTapSignIn.configure({ webClientId: process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID! });
  try {
    await GoogleOneTapSignIn.checkPlayServices();
    const result = await GoogleOneTapSignIn.presentExplicitSignIn();
    if (isCancelledResponse(result)) return null;
    if (!isSuccessResponse(result) || !result.data.idToken) {
      throw new Error('Google sign-in did not complete.');
    }
    return result.data.idToken;
  } catch (error) {
    if (isErrorWithCode(error) && error.code === statusCodes.SIGN_IN_CANCELLED) return null;
    throw new Error('Google sign-in failed. Please try again or use your password.');
  }
}
