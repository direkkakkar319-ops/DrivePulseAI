# DrivePulseAI Android app

React Native + Expo frontend with Firebase email/password and Android Google authentication.

## Implemented

- Signup with exactly Username, Email, and Password; email/password login.
- Google sign-in through Android Credential Manager, exchanged for a Firebase session.
- Show/hide password controls on signup and login.
- Username stored in the Firebase Auth `displayName` profile field. It is not
  unique and cannot be used instead of email to log in.
- Verification screen with send/resend and a check-verification action.
- Password reset through Firebase-hosted email links.
- Native Firebase session persistence and logout on this device.
- Protected routes: signed-out users see login; unverified users see verification;
  only verified users enter the account area.
- Account screen replaces the old dummy vehicle scores.

Firebase stores authentication accounts, including email and the explicitly saved
display name. It stores passwords using its salted, modified scrypt hashing
scheme. Password text exists temporarily in the form state while typing; we do
not persist it ourselves. The native SDK manages session persistence and tokens.
`src/api/auth.android.ts` owns Firebase operations;
`src/store/authStore.ts` shares account state; `src/app/_layout.tsx` guards routes.
The account screen now sends a fresh token to FastAPI to synchronize the minimal
PostgreSQL profile. `src/api/client.ts` sends bearer tokens, limits retries, and
handles server/network failures. Configure `EXPO_PUBLIC_API_URL` in `mobile/.env`
as described in [the backend setup](../backend/README.md). Client-side guards do not replace server-side token and
permission checks.

FastAPI validation and PostgreSQL profile storage are implemented in `backend/`.
Live use requires server credentials and a reachable API. Cloud deployment remains
a subsequent step. Vehicle/report routes still contain prototype placeholders.
iOS and web authentication have not been configured; they display a setup message.
The Firebase Auth config plugin only adds iOS setup in the installed version, so
it is omitted for this Android integration. Add it with the iOS Firebase config
when implementing iOS support.

## Firebase setup

1. Use project `drivepulse-d2034` and enable **Authentication → Sign-in method →
   Email/Password**. Passwordless email-link sign-in is not required.
2. Register the Android package `com.drivepulseai.app`.
3. Download its `google-services.json` into this `mobile/` directory.
   `app.json` references this file. It is client configuration, not an Admin SDK
   service-account private key. Never put an Admin SDK key in the mobile app.
4. Review the Firebase password policy and email-enumeration protection settings.
   The SDK enforces the configured password policy during signup.

Verification/reset links open Firebase's hosted page in a browser. After verifying,
return to the app and tap **I have verified my email**. No legacy Dynamic Links
configuration is needed for this flow. Signup deliberately asks the user to send
verification from that screen so email-delivery failures can be retried.

Account creation and saving `displayName` are two separate Firebase requests.
If only the profile write fails, the account still exists: the verification/account
screen offers **Retry saving username**, without recreating the account. That
retry draft is held only in memory, so retry before closing the app or logging out.
Existing accounts are not assigned a username automatically.

### Google sign-in

1. Enable **Google** in Firebase Authentication for `drivepulse-d2034`.
2. Register the SHA-1/SHA-256 fingerprints for each development/release signing
   key against `com.drivepulseai.app`, then download the updated `google-services.json`.
3. Set `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` in `mobile/.env` to the **Web** OAuth
   client ID from that same project. Leave it empty to hide the Google button.
4. Rebuild the Android development APK: this merge adds the native
   `react-native-nitro-google-signin` and `react-native-nitro-modules` packages.

The Google ID token is exchanged with Firebase using `signInWithCredential`.
FastAPI receives only the resulting Firebase ID token through the same profile API
used by email/password accounts; there is no separate `/auth/google` backend.
Google's display name becomes the initial profile username. Cancelling the account
picker leaves the session unchanged. Account linking is not implemented; if Firebase
reports an existing account with a different credential, use its existing sign-in method.
Google provider settings, client IDs, and signing fingerprints need a real-device check.

Login and logout publish the SDK's current account after the operation succeeds,
as well as listening for token events, so navigation does not depend solely on
the timing of the native event. Unverified users can sign in but remain on the
verification screen. Firebase errors are shown with friendly messages; otherwise
unrecognized `auth/...` codes are displayed without raw SDK errors or credentials.

## Install and build

Use Node.js 22.13 or newer and run commands from `mobile/`:

```bash
npm ci
```

This app now uses native Firebase modules and must run in an Android development
build. **Expo Go cannot load these modules.**

For a local build, install the Expo-compatible Android Studio/SDK and JDK, connect
an Android device with USB debugging (or start an emulator), then run:

```bash
npm run android
```

Alternatively, use Expo's EAS cloud build service (requires an Expo account):

```bash
npx eas-cli login
npx eas-cli build --platform android --profile development
```

The EAS CLI will ask to link/create an Expo project on the first build. The
`development` profile in `eas.json` produces an installable APK. Install it on your
Android phone. To serve the JavaScript during development, run:

```bash
npm start
```

Connect the phone and development computer to the same network and open the
project using the installed development app. Rebuild the APK whenever native
packages or Firebase native configuration change.

## Checks

```bash
npm run lint
npx tsc --noEmit
npm test -- --runInBand
npx expo export --platform android --output-dir /tmp/drivepulse-android-export
```

If local generated route types are stale after adding routes, briefly run
`npm start` to regenerate `.expo/types/router.d.ts`, then rerun TypeScript.

Tests mock Firebase and native navigation. They check authentication errors,
verification, account creation validation, token retrieval, session restoration,
and which route groups are exposed. They do not prove live Firebase connectivity,
email delivery, native compilation, or Android back-stack/deep-link behavior.

## Manual acceptance on an Android device

1. Sign up with a username and an email you own. Check the password eye toggle.
   Confirm the account and display name appear in Firebase Auth.
2. Send the verification email and try entering the app before verification: access
   must remain restricted. Check that signed-out deep links cannot open main routes.
3. Follow the email link, return, and check verification. The account screen appears.
4. Close and reopen the app: the signed-in account should be restored.
5. Log out: back navigation and direct links must not reopen protected screens.
   Log in again with the exact same email/password and confirm the account returns.
6. Try an incorrect password, a password reset, and an offline login.
7. Repeat signup/login, verification, and session refresh on target Indian Wi-Fi
   and mobile networks before relying on the integration for real users.

8. With Google configured, sign in and confirm the Firebase UID matches the synced
   PostgreSQL profile. Log out and cancel the Google picker: protected routes must
   remain closed. Also test provider/configuration failures and account conflicts.

## References

- [Expo Firebase integration](https://docs.expo.dev/guides/using-firebase/)
- [React Native Firebase setup](https://rnfirebase.io/)
- [Firebase Android setup](https://firebase.google.com/docs/android/setup)
