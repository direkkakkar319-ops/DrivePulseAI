Local demo vehicle catalog and one-time onboarding behavior.

`src/config/demo-vehicle-catalog.ts` is the reusable typed source. Onboarding and
Garage Add/Edit use the same form without calling any external catalog API. The
previous optional NHTSA adapter/hook remain unused by application screens; their
standalone tests are retained. No API key, dependency or backend schema is added.

The following are deliberately bounded historical calendar-year demo subsets,
not complete global model-year catalogs or predictions of future production:

| Manufacturer | Model | Demo years | Scope |
| --- | --- | --- | --- |
| Mahindra | Thar | 2020–2024 | 2020-generation three-door Thar, not original 2010 Thar or Thar ROXX |
| Mahindra | XUV700 | 2021–2024 | Historical launch/production coverage |
| Hyundai | Creta | 2020–2024 | 2020-generation onward; earlier generations use manual fallback |
| Hyundai | i20 | 2020–2024 | Third-generation i20; earlier generations use manual fallback |
| Ferrari | 296 GTB | 2022–2024 | Delivery-era subset, not the 2021 unveiling year |
| Ferrari | Roma | 2020–2024 | Coupe, not Roma Spider |

2024 is a conservative demo cutoff, not an assertion that every model stopped
production then. Calendar manufacturing years and market-specific model years
can differ. Every entry carries source URLs; extending coverage requires research.

Primary evidence:

- [Mahindra October 2020 Thar launch](https://www.mahindra.com/news-room/press-release/en/mahindra-commemorates-its-75-th-anniversary-launches-the-all-new-thar-at-attractive-prices)
  documents the 2020 generation and petrol/diesel engines. Its
  [2023–24 annual report](https://www.mahindra.com/sites/default/files/2024-06/MM-Annual-Report-2023-24.pdf)
  provides historical reporting at the demo cutoff.
- [XUV700 August 2021 launch](https://www.mahindra.com/sites/default/files/resources/investor-reports/FY22/Announcements/XUV700-Launch-14-08-2021.pdf)
  and [July 2024 production/anniversary announcement](https://auto.mahindra.com/on/demandware.static/-/Sites-amc-Library/default/dw535a8403/X700/Press-release/pdfs/Press-Note-Fast-Forward-to-The-Big-League.pdf).
- [Hyundai official manual coverage](https://org2.hyundai.com/in/en/connect-to-service/hyundai-service/owners-manual)
  lists Creta from September 2020 to January 2024 and the subsequent manual,
  and i20 from November 2020 to October 2023 and the subsequent manual.
  These calendar subsets do not certify specific trims in every market.
- [Ferrari 2022 shipment presentation](https://cdn.ferrari.com/cms/network/media/pdf/2023_02_02%20-%20Ferrari%20-%20FY%202022%20Results%20Presentation.pdf)
  supports the 296 GTB delivery start. Its
  [2024 annual report](https://www.sec.gov/Archives/edgar/data/1648416/000164841625000027/race-20241231.htm)
  documents continuing 296 GTB availability and Roma phase-out during 2024.
- [Ferrari FY2020 results](https://www.sec.gov/Archives/edgar/data/1648416/000164841621000007/fnvfy2020resultspr.htm)
  confirm Roma deliveries began in Q4 2020. Its
  [Roma technical release](https://cdn.ferrari.com/cms/network/media/pdf/cs_ferrari_roma_full_gbr.pdf)
  specifies petrol. The
  [2024 government 296 GTB specification](https://lto.gov.ph/wp-content/uploads/2024/08/MC-VDM-2024-2774.pdf)
  identifies gasoline; Ferrari annual reporting identifies the V6 hybrid.

Verified configurations are offered as choices, never silently assigned: Thar and
XUV700 use ICE petrol/diesel; Roma uses ICE petrol; 296 GTB uses petrol-electric
hybrid. Hyundai entries intentionally do not certify all historical trim/fuel
combinations, so their controls expose general compatible choices and ask users
to confirm their actual vehicle. Manual vehicles retain ICE petrol/diesel/CNG,
hybrid petrol-electric/diesel-electric, and EV with no combustion fuel.

Changing manufacturer clears model and year; changing model clears year. An
incompatible previously chosen configuration is cleared rather than guessed.
The form also checks selected demo years/configurations on submission.

Manual entry is available through Other / Not Listed. Its year selector uses the
existing 1886-through-next-calendar-year validation policy, explicitly without a
claim of catalog verification. Saved values outside the demo list remain visible
and can be resaved unchanged, including nickname-only edits. A saved year outside
a matching demo entry is preserved, but not added as a verified dropdown year.

One-time onboarding uses the existing PostgreSQL `user_onboarding` row per Firebase
UID: `profile_completed_at` selects profile setup and `completed_at` selects first
vehicle setup or Home. The account provider reloads server state after
restoration/login and remounts by UID. No new local completion flag is introduced.
Deleting all vehicles keeps completion; the first-vehicle endpoint cannot
restart a completed journey. The first save and completion remain atomic.

The former normal-screen Reload account button invoked `account.reload()`, which
GETs `/api/v1/onboarding`, sets loading, and lets the parent gate remount/resume
the server-approved step. It was not Skip and could discard the current form
draft. It is now absent from normal onboarding. Retry appears only after account
load/save failure: first-vehicle Retry reloads server state; Garage form Retry
resubmits the same draft. Logout remains available during onboarding. Neither
loading failure nor Retry permits access before server milestones are confirmed.
