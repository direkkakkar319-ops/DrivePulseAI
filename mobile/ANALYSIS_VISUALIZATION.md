# Phase 4.2 — KIT analysis visualization

## Status and scope

Phase 4.2 extends the existing Phase 4.1 Insights screen. It uses validated,
transient main-backend results; no API, authentication, inference, deadline,
History, Garage, navigation or persistence behavior was changed. Demo cards stay
illustrative and separate from the real result visualizations.

No package was added. The existing `react-native-svg` **15.15.4** supplies the
small line plots; this is the version recommended by the
[Expo SDK 57 reference](https://docs.expo.dev/versions/v57.0.0/sdk/svg/).
There is no new native module or Phase 4.2-specific rebuild requirement. The
Phase 4.1 DocumentPicker requirement still applies to older development clients.
No Android build or deployment was performed.

## Components and backend contract

| UI | Existing backend fields | Interpretation |
| --- | --- | --- |
| Overview | source_type, sample/source recording ID/date, window_count, window_seconds, summary, model | Genuine response received; counts and score summaries; temporary, not saved |
| Novelty plot | score_series[].window, pair_id, anomaly_score, threshold, is_novel | Score is attached to the following/target window, not its input window |
| Selected-pair explanation | predictions[].current_window, next_window, top_signal_deviations | Returned normalized errors, ordered by backend; dimensionless, not causal feature importance |
| Flagged intervals | flagged_intervals including pair_ids and peak_anomaly_score | Original half-open [start, end) windows; no new merging or fault classification |
| Telemetry plot | telemetry[].window, medians, missing_fractions; signals name/display_name/unit | Observed ten-second medians, not raw readings, forecasts or live vehicle data |
| Interpretation | explanation fields, time_basis, contribution_definition, limitations | Backend definitions and limitations, without invented model metrics |

- `src/lib/kit-visualization.ts`: display-only maps, identity grouping, source-clock
  formatting, finite-value formatting and discontinuity-aware line runs.
- `src/components/insights/kit-line-chart.tsx`: responsive SVG line plot, threshold,
  flagged-window shading, inspection and bounded page navigation.
- `src/components/insights/kit-analysis-visualization.tsx`: segment/signal selection,
  score/telemetry sections, pair deviations, interval paging and model details.
- `kit-analysis-feedback.tsx` retains loading/error/Retry behavior and expands the
  ready overview. `ai-insights-screen.tsx` adds the two real-result sections.
- Existing runtime validation in `lib/kit-analysis.ts` now also rejects backwards
  or duplicate window positions within a segment and reordered target predictions.
  Malformed responses remain errors; they do not become plotted success states.

## Graph mapping and interaction

The x-axis uses backend source-clock seconds, formatted HH:MM:SS; timezone is
unknown. No UTC conversion, date inference or interpolation occurs. Segment
selection groups by recording ID, recording date, split and segment ID. Backend
order is preserved. Lines break at temporal gaps, missing values and identity
changes. Each plot has its own segment selector; correlate them by selecting the
same segment and source-clock range.

A plot displays at most **48 original points per page**. All pages remain
available; no downsampling, arbitrary truncation or fabricated points occur.
Y-axis bounds are local to the displayed page and include the score threshold.
Axes, physical units, source-clock range and legends are visible. Values are
formatted for display only; the underlying response precision is unchanged.

Tap near a point to inspect it, or use the accessible Previous/Next reading
buttons. Inspection includes exact window or pair ID, source-clock interval,
value and flag. Score inspection also identifies input/target windows and the
three returned largest normalized signal deviations. Entirely missing required
signals are rejected by the backend/contract; partial missingness is shown as a
fraction of readings, and omitted sparse fractions mean zero missingness. Valid
zero medians remain visible measurements, never missing-value placeholders.

Red markers and shaded bands indicate genuine flagged target windows. The score
plot draws the returned threshold as a dashed line; flags are not recomputed by
this view. Interval details retain backend recording/segment/date, bounds, peak
and traceable pair IDs, with at most 12 interval cards per page.

## Actual versus predicted: unavailable

The current `PairAnalysis` response has normalized_signal_errors but **does not
expose forecast medians or signed, unnormalized residuals**. Telemetry includes
observed medians only. A labeled unavailable state explains why a comparison graph
cannot be drawn. Predictions cannot be reconstructed from normalized absolute
errors. No synthetic forecast series was created.

A later, explicitly approved backend enhancement could return per-pair forecast
medians keyed by the fitted signal names, physical units, and the target-window
reference. The existing target telemetry already supplies the observed medians.
That would require corresponding TypeScript/runtime contract validation and tests;
it is not part of this phase. Accuracy, calibrated confidence, vehicle-health,
EV battery diagnosis and fault-classification metrics are also unavailable.

## Lifecycle and privacy

Ready results alone mount the visualizations. Loading, errors, source/date changes,
explicit cancellation, account changes and logout remove them through the existing
controller. Request cancellation remains best effort; it does not promise to stop
backend computation already underway. Retry uses the existing request path.
Results, point selections and graph state are not persisted or associated with
Garage vehicles. Demo mode does not display real-analysis plots or relabel demo
values as predictions. Uploaded recording dates remain caller-supplied/unverified.
KIT is combustion-engine research telemetry; novelty flags do not confirm faults.

## Verification performed

From `mobile/`:

```bash
npm test -- --runInBand
./node_modules/.bin/tsc --noEmit --incremental false
npm run lint -- --no-cache
./node_modules/.bin/eslint src/lib/kit-visualization.ts src/lib/kit-analysis.ts src/components/insights/kit-line-chart.tsx src/components/insights/kit-analysis-visualization.tsx src/components/insights/kit-analysis-feedback.tsx src/components/insights/ai-insights-screen.tsx tests/kit-visualization.test.tsx
```

- **452 tests passed in 31 suites**, including 20 new visualization tests.
- TypeScript, configured Expo lint, changed-file lint and `git diff --check` passed.
- Genuine first-pair/flagged-pair stored response excerpts test mapping and real
  interval/ranking rendering; HTTP/native Firebase boundaries remain mocked.
- Dedicated load tests use repeated real medians with explicitly synthetic test
  identities/times solely to test 1000-point pagination, not to claim model results.
- Additional tests cover gap breaks, source-clock resets, partial missingness,
  valid zeros, numerical extremes, units, signal/segment selection, taps and
  accessible navigation, interval paging, unsupported forecasts, CSV contract,
  Retry/cancellation, demo separation, logout and account switching.
- Existing Phase 4.1 API, native multipart, 401 refresh, stale response and navigation
  regression suites passed unchanged. Unrelated local EAS/account-client files
  were preserved. Backend and ML code were untouched.

## Android acceptance still required

Physical-device rendering, SVG native module execution, small-screen/large-font
layout, scrolling performance and touch inspection were not verified here. No
connected device or authenticated production session was used. No new native
build, production request or deployment was initiated by Phase 4.2.

1. Use the existing compatible development client and Phase 4.1 Metro command.
2. Log in with a verified Firebase account; run a real KIT sample analysis.
3. Check counts, model/limitations, score threshold, red target windows and two
   backend-returned intervals for the current packaged recording. These counts
   are regression expectations, not hardcoded UI results.
4. Page through all readings, tap points, use reading buttons, change telemetry
   signals and segments, and inspect missing fractions and units.
5. Repeat using a supported raw KIT CSV with its explicit date; verify caller-
   supplied source metadata. Native DocumentPicker must exist in that binary.
6. Test loading/cancel/Retry and source/demo/account changes; old plots must disappear.
7. Check Android Back, TalkBack, large fonts, narrow screens and smooth scrolling.

No backend compatibility blocker was found for the implemented views. Actual-
versus-predicted charts require the separately documented response enhancement.
