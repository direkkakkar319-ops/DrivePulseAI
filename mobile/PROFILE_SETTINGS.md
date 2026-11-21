Profile and Settings implementation (Phase 4.6).

Account data and editing
------------------------

The Profile tab stays at `/(main)/(tabs)/account`. The existing `/(main)/account`
destination used by recorded tools displays the same Profile with Back support.
New `edit-profile`, `security`, and `settings` screens live under the existing
verified-account/onboarding protected stack, outside the five-tab bar. None has
mount-time navigation or changes to navigation options. Back/Cancel use existing
history, falling back to the Profile tab for a direct link.

The authoritative displayed name is `OnboardingState.full_name` from the shared
`OnboardingProvider`. Fallbacks reuse the existing Firebase display name, email
prefix, and finally "Your profile". Email/verification come from Firebase.
Missing photos use initials. There is no additional profile/account store.

Edit Profile uses `account.saveProfile`, the existing authenticated
`PUT /api/v1/onboarding/profile`, with the trimmed name and current driving licence
answer. The existing Firebase bearer token, X-Account-UID precondition, response
validation, and stale-account protection apply. Names must contain 1–120 trimmed
characters. Success is displayed only after a confirmed response; failures retain
the draft and allow another Save. Cancel does not make a request. A later account
load restores the server value.

The existing endpoint preserves profile/completion timestamps, vehicle IDs,
ownership, and active selection. A new PostgreSQL regression test verifies this
and rejects overlong edits without changing the saved state. No backend runtime
code, schema, migration, or endpoint was changed. The app profile name remains
separate from the Firebase-synchronized username; editing it does not call
Firebase updateProfile or restart onboarding.

Avatar previews
---------------

The editor reuses `useProfileOnboarding` and the existing native photo picker
adapter. Choose/replace/remove, cancellation, permission errors, and unavailable
native-module handling remain supported. Preview decoding errors fall back to
initials. Photo state belongs only to that editor, resets when it unmounts, and
is never included in an API payload or stored in PostgreSQL/Firebase. The UI
explicitly says previews are temporary and not uploaded, synced, or permanently
stored. Profile outside the editor shows initials until durable storage exists.

Firebase security and session handling
-------------------------------------

The Android Firebase snapshot now exposes only provider IDs from providerData,
not provider identities, credentials, passwords, or tokens. Existing snapshots
without provider metadata remain valid; the Security screen does not assume
password support when that information is unknown.

Password reset uses the existing resetPassword operation only when the account
has an email and a linked `password` provider, including Google/password-linked
accounts. Google-only/other-provider accounts get an explanation instead of a
nonfunctional button. Verification delivery/refresh reuse existing Firebase
operations when supported. The normal unverified account still goes through the
existing email-verification guard; Security does not bypass it. Errors use the
existing safe Firebase error formatter and actions prevent duplicate requests.

Normal Logout lives in Settings and calls the existing Firebase signOut method.
No explicit redirect races the auth event. Existing root guards remove protected
routes and the UID-keyed providers discard account/draft/preview state. Late
action feedback is ignored after unmount. Signing in again reloads the matching
PostgreSQL profile and vehicles. Logout makes no account/vehicle deletion request.
Onboarding's existing Logout remains available for account switching. The
username-save retry and profile-sync retry are preserved.

Settings and About
------------------

Settings includes real app/privacy information, account-sync status/retry, and
Logout. There are no notification, theme, or other decorative toggles. About
explains the separation between Firebase credentials, PostgreSQL profile/vehicle
records, temporary avatars, illustrative demo values, and recorded research data.
It distinguishes the available KIT analysis in AI Insights from unimplemented
live OBD connectivity; demo results remain explicitly illustrative.

Installed version is read only if the existing binary exposes the optional
ExpoApplication native capability. No expo-application dependency was added.
When unavailable, it is explicitly labeled unavailable; the existing Expo app
configuration version is shown separately and never presented as the installed
binary version.

Verification and remaining limitations
--------------------------------------

Mobile tests cover profile/fallback rendering, 0/1/multiple vehicle navigation,
confirmed edit/cancel/retry and restoration, missing fields, temporary photo
payload separation, provider-specific security, logout/account switching, and
real-router Edit/Security/Settings/Back navigation. Backend tests cover the reused
profile update's preservation guarantees. These use test accounts/services, not
live email delivery or uploaded photos.

On Android, reload the existing development app. Check Profile -> Edit Profile,
Save, Back, restart and name restoration; Cancel; photo selection/replacement/
removal and temporary-preview text; My Garage with empty/populated accounts;
Security password-reset delivery for a password account and the unsupported
explanation for Google-only accounts; Settings/privacy/version; Logout and login
with the same and a different account. Confirm Android Back, large font sizes,
keyboard scrolling and safe areas. No new native dependency or APK is required;
older binaries without the already-approved photo picker show its existing
unavailable message. The previously reported intermittent Garage maximum-depth
crash still needs physical-device verification; this phase does not claim to fix it.

No Phase 5/6, durable image storage, notifications, theme switching, ML, OBD,
analysis-history persistence, telemetry changes, or Garage storage changes are
implemented here.

Phase 4.6 file list
-------------------

Created:
- `src/app/(main)/edit-profile.tsx`
- `src/app/(main)/security.tsx`
- `src/app/(main)/settings.tsx`
- `src/components/profile/account-session-actions.tsx`
- `src/components/profile/action-feedback.tsx`
- `src/components/profile/app-information.tsx`
- `src/components/profile/edit-profile-form.tsx`
- `src/components/profile/profile-avatar.tsx`
- `src/components/profile/profile-screen.tsx`
- `src/components/profile/security-screen.tsx`
- `src/hooks/use-account-action.ts`
- `src/hooks/use-profile-back.ts`
- `src/lib/app-version.ts`
- `tests/app-version.test.ts`
- `tests/profile-session.test.tsx`
- `tests/profile-settings.test.tsx`
- `PROFILE_SETTINGS.md`

Modified:
- `src/api/auth.android.ts` and `src/api/auth.types.ts` (provider metadata only)
- `src/app/(main)/(tabs)/account.tsx` and `src/app/(main)/account.tsx`
- `tests/auth.android.test.ts`
- `tests/garage-navigation-runtime.test.tsx`
- `tests/onboarding-flow.test.tsx`
- `README.md`
- `../backend/tests/test_onboarding.py` (regression test only)

Final checks: 394 mobile tests passed across 28 suites; TypeScript and Expo lint
passed; 72 backend tests passed against the isolated `drivepulse_test` database;
Ruff check and format check passed for the changed backend test. The backend test
runner reported two existing TestClient/AnyIO deprecation warnings. Native email
delivery, installed-binary metadata and visual/device behavior still need the
Android checks above.
