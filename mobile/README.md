# DrivePulseAI mobile

React Native / Expo SDK 57 Android app. Use Node.js 22.13 or newer.

## Local password authentication
## Password authentication

Start the backend using [its setup instructions](../backend/README.md), then:

```bash
cd mobile
npm ci
cp .env.example .env
npm start
```

`EXPO_PUBLIC_API_URL` defaults to `http://10.0.2.2:8000` on Android emulators.
For a physical phone, use your computer's LAN IP and keep both devices on the
same network. For a browser preview, set it to `http://localhost:8000`.
Restart Metro after changing environment variables. Use HTTPS outside local development.

The app opens on login. Create an account with an email and a password of at least
12 characters. Authentication protects the main routes, stores the native session
in SecureStore, checks it on startup/foreground, and clears expired sessions.
Logout revokes the session on the backend; if the server cannot be reached, it
reports an error so you can retry. Web preview uses memory-only sessions and
requires login after reload. Existing vehicle screens still contain mock data.
Password signup validates credentials but does not verify email ownership.

## Google sign-in on Android

1. Configure an OAuth consent screen in Google Cloud and add test users if needed.
2. Create a **Web application** OAuth client. Set its public client ID in both
   `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` (mobile `.env`) and `GOOGLE_WEB_CLIENT_ID`
   (backend `.env`). Never put a client secret in an `EXPO_PUBLIC_` variable.
3. Create an **Android** OAuth client in the same project for package
   `com.drivepulseai.mobile` and the SHA-1 of the signing certificate used for your
   build. Register the production signing certificate separately when applicable.
4. Build a native development app with the Android SDK and emulator/device ready:

   ```bash
   npx expo run:android
   ```

Nitro Google Sign-In uses Android Credential Manager and native autolinking.
An explicit Web client ID is used, so Firebase configuration files are not required.
The package config plugin is omitted for this Android-only integration: its
non-Firebase branch only configures iOS, and requires an iOS URL scheme. Google
sign-in appears only on Android when a client ID is configured and the app is
not running in Expo Go. Password login can be tried in Expo Go. Google sign-in
for iOS and web is outside this issue's Android scope.

The backend verifies the Google ID token before issuing an application session.
Cancelling Google sign-in leaves you on login. Accounts using the same email
are not automatically linked; use password login for an existing password account.

References: [Expo Google authentication](https://docs.expo.dev/guides/google-authentication/),
[Nitro Expo setup](https://react-native-nitro-google-sign-in.github.io/docs/setup/expo/).

## Verification

```bash
npm run lint
npx tsc --noEmit
```

On an emulator/device, check signup, wrong password, duplicate signup, relaunch,
logout, opening a protected deep link while logged out, Google cancellation,
and successful Google login. Live Google testing needs your project configuration.

Auth files: `src/auth/` contains secure storage and Google integration;
`src/store/authStore.tsx` manages the session; `src/api/client.ts` calls the API;
`src/types/auth.ts` mirrors backend contracts. `src/app/_layout.tsx` gates routes.
