# Recorded Nissan Leaf MVP — Step 2A

Purpose: document the functional mobile replay, its provenance, and the Step 3 API boundary.

## Current architecture

Overview (`/(main)/(tabs)/home`), Telemetry (`/(main)/(tabs)/telemetry`) and Insights
(`/(main)/(tabs)/insights`) are the only visible bottom tabs. Header Account opens
`/(main)/account`; Recorded Replay is `/(main)/replay`; interval details use
`/(main)/recorded-insight/[id]?clipId=...`. Existing dashboard redirects still enter
Overview. Older vehicle, sensor, insight and report routes remain available with
explicit simulated-data labels; they are not used by the recorded-data screens.
The old grouped account URL is preserved. No authentication routes were removed.

- `src/types/recorded-telemetry.ts`: JSON interfaces, nullable readings, loading/error states.
- `src/api/recorded-telemetry-provider.ts`: `listClips()` / `getClip(id)` data boundary.
- `src/demo/recorded/clips.json`: central real-data export; only the provider imports it.
- `src/lib/recorded-replay.ts`: input validation, frozen threshold comparison, replay transitions.
- `src/store/recordedReplayStore.tsx`: shared selection/playback, request race protection,
  lifecycle pause and retry. Mounted within the existing verified Firebase account guard.
- `src/components/recorded/ui.tsx`: light neutral layout, one green accent, units and score meaning.
- `src/components/recorded/telemetry-chart.tsx`: existing react-native-svg dependency,
  timestamp-positioned lines and persistent-interval shading. Missing readings break lines.
- `src/components/recorded/screens.tsx`: screen composition. Route files are thin wrappers.
- `scripts/export-recorded-clips.py`: bounded reproducible source-aligned fixture export.
- `tests/recorded-*.test.*`: real fixture integrity, replay behavior and presentation tests.

Firebase login/signup, verification, session restoration and native configuration are
unchanged. Account retains sign-out, username-save retry and profile-sync retry. The
existing profile sync may report a backend error, but recorded replay does not require
PostgreSQL or a network connection. No new dependency or native build configuration was added.

## Real fixture provenance

| Clip | Trip | Inclusive source rows | Samples | Duration | Flagged rows | Persistent intervals |
|---|---:|---|---:|---:|---:|---:|
| leaf-typical | 153 | 1637821–1638031 | 211 | 52.5 s | 0 | 0 |
| leaf-unusual | 167 | 1759260–1759464 | 205 | 51.001 s | 132 | 2 |

Both are validation recordings from `Dataset_NissanLeaf-2021_2022.csv`, preparation
`1d6fc5b045ee25d0`, experiment `0c777345c64dfeba`. The exporter reads saved scores,
saved persistent intervals and preparation metadata/ledger; checks source-row identity,
values, one trip/segment, ordering and quality flags; then writes only mobile JSON.
It does not load a model, refit anything, or modify ML artifacts. The export contains
artifact checksums and original source checksum. The 416 observations occupy about 102 KB.

Preserved fields are original UTC timestamps, source rows, V, °C, SOC %, saved scores,
quality flags and interval metadata. Playback offsets and row flags are derived from
those exact timestamps and the frozen rule `score_samples < -0.6676090615628322`.
Scores are not probabilities. Pack 1 temperature is a logged sensor measurement.
No confirmed fault, health score, severity, RUL or maintenance advice is displayed.

## Playback semantics

Select a clip to reset to its first sample, paused. Play visits every subsequent sample
using the difference between its recorded offset and the previous sample's offset.
Pause holds the current observation; restarting resets to the first sample and pauses.
Resume waits the next full recorded interval. A delayed JS timer stretches wall-clock
playback rather than skipping rows or alert boundaries. The visible elapsed time is the
current sample's recorded offset. App backgrounding pauses playback.

Overview and Telemetry share the same current sample; Telemetry charts only the history
up to that position. Insights lists the full selected clip's saved persistent intervals,
explicitly labelled as a full-recording review. Details show full clip context and the
selected interval's observed ranges. Detail navigation does not alter playback selection.
Typical rows and persistent intervals remain distinct; brief flags are visible in replay.
No persistent intervals is not proof of battery health. Loading, empty, error, retry and
nullable-value states are explicit.

## Step 3 API contract (proposed, not implemented)

Use the existing API base URL and Firebase bearer-token conventions when implementing:

| Request | JSON response |
|---|---|
| `GET /replay/clips` | `ReplayClipMetadata[]` (no samples or interval arrays) |
| `GET /replay/clips/{clip_id}` | `ReplayClip` |

`ReplayClip` extends metadata with `samples: TelemetrySample[]` and
`persistent_intervals: PersistentInterval[]`. Names use snake_case exactly as the TS
interfaces; do not translate between backend and UI names. `schema_version` is 1.
Metadata includes clip/title, source dataset, vehicle `{description, recording_source}`,
run IDs, trip/split/segment, UTC start/end, duration in milliseconds, sample count,
threshold and provenance hashes. Each sample contains source_row, original_timestamp_utc,
playback_offset_ms, voltage_v, temperature_c, soc_percent, score_samples, unusual and
quality_flags. Nullable measurements/scores use JSON null; unavailable classification is
also null. Each persistent interval has an ID, source-row bounds, UTC bounds, duration,
row count and score_min/score_max. Use saved boundaries, not newly grouped mobile alerts.

Preserve full original timestamp strings. Do not round measurements or scores in JSON;
round only for presentation. Send chronological samples, all in one trip/segment,
with no gap above one second for these reviewed clips. Server must return 404 for an
unknown clip. Authentication errors must not be replaced with invented data.

Implement a new provider adapter with the same two methods and inject it into
`RecordedReplayProvider`. Use existing authenticated HTTP behavior; the current adapter
never calls nonexistent endpoints. One small response per clip is sufficient; playback
remains on-device. No database or live inference is needed to serve saved results.
Do not ship the full Parquet datasets in the mobile bundle.

## Run and reproduce

From `mobile/`, use the existing Android development build:

```sh
npm start
npx tsc --noEmit
npm run lint
npm test -- --runInBand
npx expo export --platform android --output-dir /tmp/drivepulse-step2a-export
```

New routes require regenerating local Expo typed routes (normally automatic on `npm start`).
The phone must use the native development build; Expo Go cannot load native Firebase.
No new native dependencies were introduced in Step 2A.

Optional fixture reproduction from repository root, using the existing Python environment:

```sh
.venv/bin/python -B mobile/scripts/export-recorded-clips.py
```

Python/Pandas/PyArrow are export-time dependencies only, never mobile runtime dependencies.

## Remaining work

Step 2B: review spacing, chart legibility, small screens, larger fonts, Android safe-area
insets, TalkBack reading order and consistent account styling on the physical phone.
Controls have at least 48 px targets; chart ranges have accessible descriptions.

Step 3: serve the exact two contracts above from verified saved results and replace the
local provider; handle authenticated loading, retry and local-network connectivity.

Device acceptance: log in, select both clips, play/pause/restart, switch tabs during
playback, inspect an interval, background/resume, change clips, log out and confirm
protected routes cannot reopen. Unit tests and a JS bundle do not prove Android runtime
or native navigation behavior; physical-device verification is still required.

## Step 2A verification

- TypeScript: passed with regenerated Expo route declarations.
- ESLint: passed with zero errors/warnings.
- Jest: 8 suites, 79 tests passed, including existing Firebase tests.
- Android JavaScript/Hermes export: passed; no native build or physical-phone test performed.
- Python exporter: Ruff passed; independent export produced identical bytes.
- Fixture SHA-256: `cf13e6c9dc94c6e72fefac990c49f5793922dabe6972de5f0b22489fd1f5f883`.
- No model loading/scoring/training, backend implementation, or credential/configuration changes.

## Step 2B visual system

The recorded-data screens use a compact token set in `src/components/recorded/theme.ts`:
neutral canvas and surfaces, one restrained green accent, an amber unusual-pattern state,
five spacing steps, three corner radii, a small typography scale and 48 px minimum touch
targets. Overview presents vehicle identity, replay state, scan-friendly battery metrics
and the current anomaly observation in reading order. Replay uses radio-style clip cards,
an accessible progress indicator and a clear completion state.

Telemetry keeps original timestamps and measurements. Charts now include responsive SVG
view boxes, channel-specific axis precision, current-position lines and markers, unusual
sample markers, persistent-interval shading, readable UTC endpoints and TalkBack chart
summaries. Insights distinguishes flagged samples from persistent intervals and maintains
the full-recording review language. Interval details pair the highlighted full-recording
context with timing, row and provenance metadata. Account uses the same surfaces,
typography, status treatment and touch sizes without changing Firebase behavior.

Physical Android checks remain necessary for device-specific font rendering, TalkBack
order, landscape behavior, system navigation-bar contrast and final spacing on the demo
phone. No recorded values, saved scores, replay timing, provider contract or ML artifact
changed in Step 2B.
