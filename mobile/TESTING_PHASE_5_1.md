# Phase 5.1 — application testing and acceptance

Status: automated verification completed; **native E2E and physical Android
acceptance remain pending**. Phase 5.1 is not fully complete. Phase 5.2 builds are
postponed. No tool installation, native build, deployment, production-data
mutation, Firebase/Render configuration change, commit or push was performed.

## Coverage audit

The configured runner is Jest with `jest-expo/android` and React Native Testing
Library (`jest.config.js`). Android in Jest's output is a preset name, not proof
that a device/emulator ran. Native Firebase, file picker and HTTP boundaries are
mocked in these suites. Genuine stored KIT response excerpts are contract fixtures,
not new inference executions or an independent ML evaluation.

| Journey | Existing suites / evidence | Remaining native acceptance |
| --- | --- | --- |
| Email login/signup, verification, Google credentials, restoration, logout | auth.android, auth-flow, profile-session | Real SDK, mailbox, Android credential UI and process restart |
| User-bound backend sync, 401 refresh, failure/Retry | client, account-connectivity, profile-onboarding | Live Firebase tokens, network/TLS and deployed account API |
| One-time onboarding and recovery, switching accounts, empty completed Garage | onboarding-flow, onboarding-api, profile-session | Persisted PostgreSQL state after force-stop/re-login |
| Garage Add/Edit/Delete, active vehicle, errors, retries, ownership isolation | garage, vehicle-setup, vehicle-setup-ui, vehicle-dropdowns | Disposable account CRUD through real backend |
| Five tabs, Home/Profile → Garage, Back, onboarding guards | garage-navigation-runtime, tab-navigation, route-vehicle | Fabric/native scheduling, gesture and system Back behavior |
| Backend sample catalog, explicit sample analysis, CSV multipart | analysis-api, analysis-route, analysis-state, csv-picker | Real catalog/inference, Android providers/content URIs and native upload |
| Scores, threshold, intervals, telemetry units, segmentation, inspection | kit-visualization | SVG rasterization, TalkBack, touch, small screens and device performance |
| Empty history, demo separation, real data never persisted | history, home-dashboard, ai-insights, analysis-state, kit-visualization | End-user navigation and live account isolation |
| Profile/security/settings, local avatar previews | profile-settings, profile-photo, app-version | Native image picker/provider capabilities and real security email delivery |

Relevant backend integration documentation remains:
[Phase 4.1](ANALYSIS_INTEGRATION.md), [Phase 4.2](ANALYSIS_VISUALIZATION.md),
[backend API contract](../backend/docs/phase-3c-analysis-contract.md), and
[CSV compatibility](../backend/docs/phase-3b-csv-analysis.md).

### Focused coverage added

No duplicate broad screen suite was added. Nine tests extend existing suites:

- `analysis-state.test.tsx`: late document selection after account switch;
  obsolete picker completion after replacement; date change during CSV analysis;
  late catalog completion after logout even when the transport ignores abort.
- `analysis-api.test.ts`: upload deadline includes response JSON decoding;
  logout during 401 token refresh prevents a second request; logout cancels a
  pending JSON decoder and cleans up the Firebase subscription.
- `analysis-route.test.tsx`: actual route/controller/client handles sanitized
  upload 503 then Retry to real-result graphs; canceled upload completing after
  switching to demo cannot display stale charts.

The route tests use native React Native FormData and the real response validators;
only native services and transport are mocked. Test credentials are inert fixture
strings, not actual Firebase accounts/tokens. All returned model data comes from
existing representative fixtures. No model outputs were fabricated.

No confirmed application defect was reproduced by the new cases. No production
code change or bug fix was necessary. Physical-device defects remain unverified.

## Commands and actual verification

Run from `mobile/`, unless specified otherwise:

```bash
npm test -- --runInBand
./node_modules/.bin/tsc --noEmit --incremental false
npm run lint -- --no-cache
./node_modules/.bin/eslint tests/analysis-api.test.ts tests/analysis-route.test.tsx tests/analysis-state.test.tsx
npm test -- --runInBand tests/analysis-state.test.tsx tests/analysis-api.test.ts tests/analysis-route.test.tsx
# Additional broad scan, including legacy tests and generated .expo types:
./node_modules/.bin/eslint .
# From repository root:
git diff --check
```

Initial full-suite reverification: **452 passed, 31 suites**, zero failing tests,
40.231 seconds. Initial TypeScript and configured Expo lint passed.
The focused expanded suites passed **73 tests in three suites**.
Final full-suite run: **461 passed in 31 suites**, zero failed or skipped tests,
19.026 seconds. The first static pass caught a missing props type annotation in
one new test; it was corrected. TypeScript, configured Expo lint, changed-file
lint and Git whitespace checks passed after correction. The affected state suite
was rerun after the type-only correction (14 tests passed). No assertions were
removed or weakened.

The broader `eslint .` scan fails with **four errors and 24 warnings**. The four
existing `react/display-name` errors are in `account-connectivity.test.tsx:14`,
`auth-flow.test.tsx:45` and `:47`, and `tab-navigation.test.tsx:14`. Warnings include
legacy test imports/unused variables and a generated `.expo` disable directive.
These findings existed before the new tests and were not bypassed or modified.
Configured Expo lint and changed-file lint have a narrower scope.

No backend tests were required because backend files/behavior were untouched.
No real Firebase login, authenticated deployed analysis, live PostgreSQL mutation,
Render timing benchmark or device test was executed in this phase.

## E2E tooling feasibility

No Maestro/Detox configuration or mobile E2E script is present in the repository.
`adb`, `emulator`, `maestro` and `detox` are not on PATH. `ANDROID_HOME` and
`ANDROID_SDK_ROOT` are unset, and the checked conventional local SDK paths contain
no ADB executable. No local APK or module inventory was found to establish the
installed development client's capabilities. An Android device cannot be queried
without ADB; **device absence and installed binary compatibility are unknown**.
No emulator was started and no app was installed or rebuilt.

Maestro is a reasonable first native smoke-test option because it exercises the
React Native accessibility hierarchy without adding an app instrumentation SDK;
see [official React Native support](https://docs.maestro.dev/get-started/supported-platform/react-native).
It can use an already-installed compatible development client. Tool/SDK
installation needs separate approval, and a client without DocumentPicker cannot
complete CSV tests without a later authorized build. This Firebase-native app
requires its existing development client; do not substitute Expo Go.

### Minimal future E2E specification — NOT EXECUTED

Use package ID `com.drivepulseai.app` from `app.json`. Before converting this
specification into runnable Maestro flows, inspect the real device hierarchy to
confirm selectors, Expo launcher state and document-provider behavior. Do not
claim these specifications are validated YAML scripts.

Prerequisites:

1. Approved Maestro/ADB tooling, connected authorized device or existing emulator.
2. Existing compatible installed development client, confirmed native Firebase,
   SVG and DocumentPicker; reachable Metro if the client needs it.
3. Reachable main backend with configured secured ML integration; no deployment
   settings changed by tests.
4. Disposable accounts A and B, credentials supplied privately at run time, never
   committed. One account must be verified/completed; a separate fresh account is
   needed for first-time onboarding. No real user's vehicles may be edited.
5. Genuine supported KIT raw CSV staged in device Documents with known actual
   recording date, and small invalid/oversized files for rejection checks. The
   prepared windows file is not the supported raw upload format.
6. Preserve account data unless explicitly disposable and approved for cleanup;
   no clear-app-data or database reset as an automatic test step.

| Flow | Actions and stable app assertions | Expected result |
| --- | --- | --- |
| E1 Auth/guards | Invalid login, valid A login, separately unverified account; inspect protected navigation | Failure stays on auth; unverified stays in verification; verified completed A enters Home |
| E2 Onboarding/Garage | Fresh account profile/first vehicle; return login; Home → Garage; Profile → My Garage | Completion occurs after successful server response; returning user skips onboarding; no redirect loop |
| E3 Vehicle CRUD | Add/edit a test vehicle, set active, cancel delete; approved delete only for test-created vehicle | Real persistence and Home selection agree; canceled deletion sends no mutation; empty completed Garage stays onboarded |
| E4 Sample/results | Open Prerecorded KIT sample, select backend option, Analyze KIT sample; wait within documented 240-second client deadline | `kit-analysis-summary`, `kit-scores-visualization`, `kit-telemetry-visualization` appear; genuine model/recording, counts, intervals and threshold agree |
| E5 CSV | Select CSV file, choose known file via actual Android provider, enter Recording date, Upload and analyze CSV | `file` and explicit date accepted; temporary uploaded result, graphs and honest source metadata; no History entry |
| E6 Charts | Scroll to graphs, change signal/segment, Next anomaly score reading, page controls when present; inspect intervals | Actual values/units and target windows agree; gaps aren't joined; comparison graph explicitly unavailable |
| E7 Recovery/isolation | Offline/error then Retry; cancel pending analysis, select demo, restore network | Safe error, explicit retry only, no late graph; demo remains illustrative |
| E8 Logout/account B | Logout through Settings; system Back; login B; revisit Insights/Garage | Protected data not accessible after logout; A's selected file/result/vehicle never appears in B's state |

Use existing accessibility labels/test IDs rather than screen coordinates where
possible. Native document-provider steps must be adapted to the actual Android
provider; do not pretend Jest picker mocks verify the system picker.

## Physical Android acceptance checklist — ALL PENDING

Record date, app commit/version, binary build date/module availability, Android
version/device, backend URL, account labels A/B, result and redacted evidence.
Use PASS/FAIL/BLOCKED for each row; leave credentials/tokens out of screenshots
and reports. No box below is an executed-test claim.

- [ ] Login: correct/incorrect password; safe network errors; passwords hidden.
- [ ] Signup with a disposable account; actual email verification gates access;
      resend/check verification works. Password reset/provider support if applicable.
- [ ] Cold start/session restore; signed-out and unverified users cannot reach
      protected tabs using Back or existing deep links.
- [ ] Fresh account completes Profile → First Vehicle → Home only after server
      success. Restart/re-login never repeats completed onboarding.
- [ ] Incomplete onboarding resumes correctly after restart or a failed save.
- [ ] Garage zero/one/multiple vehicles; Add/Edit, active selection, failed save
      Retry, delete confirmation/cancel. Delete only disposable test-created data.
- [ ] Deleting the last test vehicle does not reset onboarding; Home remains valid.
- [ ] Home/Profile → My Garage, five tabs and Android Back work without update loops.
- [ ] Home shows the real active vehicle; History has no fabricated demo entries.
- [ ] Catalog loads from backend; selection alone does not run inference.
- [ ] Sample analysis loading, cancel and Retry; actual result model/summary shown.
      For the existing unchanged reference sample/model: 163 windows, 162 pairs,
      threshold about 8.083881 and two flagged pairs. Verify against actual response,
      not assumed fixed UI values; known first score about 3.435044.
- [ ] CSV picker opens; cancellation and replacement preserve intended selection;
      check a provider with a content URI, unavailable permission/file and bad file.
- [ ] Correct raw KIT file plus YYYY-MM-DD date uploads; invalid/empty/oversized or
      incompatible CSV produces a safe error. No arbitrary OBD/EV format claims.
- [ ] Anomaly score/threshold graph uses target-window timing; real interval bounds
      are [31660,31670) and [31770,31780) for the unchanged reference result.
- [ ] Telemetry signal selection, units, partial missingness, zeros, segment selection,
      point taps/Previous/Next reading and graph pages work.
- [ ] Large response scrolling is smooth enough on the actual device; no crash,
      broken layout or unbounded memory growth during repeated source changes.
- [ ] Actual-versus-predicted view is honestly unavailable; novelty is not health,
      fault probability, model accuracy or confirmed mechanical failure.
- [ ] Toggle demo during/after real analysis; no real graphs are relabeled as demo,
      no demo values appear in real results, History or Garage.
- [ ] Network disabled/slow, backend unavailable, interrupted upload, file removed,
      error/Retry and timeout feedback. Never change service settings to force this.
- [ ] Cancel/logout/account switch during request or picker: late results/files
      cannot reappear. Account B loads its own profile/vehicles.
- [ ] Logout returns to auth; system Back cannot reopen protected account data.
- [ ] Narrow screen, increased font/display size, keyboard, orientation policy,
      safe areas and long labels remain usable.
- [ ] TalkBack labels/focus order, visible buttons, graph reading controls and
      error announcements are understandable; color is not the sole flag cue.
- [ ] Repeated app background/foreground and process restart preserve auth and
      server onboarding while transient analysis is not presented as saved History.

## Remaining gate

Native E2E: **not executed**. Manual Android acceptance: **not executed**.
Automated coverage cannot establish native picker permissions, token/TLS behavior
on a phone, Fabric/SVG rendering, accessibility quality or device performance.
Approval for tooling/access and compatible existing binary/device are required to
close those gaps. Do not generate a Phase 5.2 build to bypass this testing gate.
