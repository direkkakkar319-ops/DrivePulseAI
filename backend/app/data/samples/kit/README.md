# Packaged KIT research sample

The manifest allowlists `kit-20180320-normal`. Its gzip CSV contains only the
163 existing prepared rows from `KIT-2018-03-20_Seat_Leon_KA_KA_Normal`, test
split, segment 0. They yield 162 consecutive ten-second pairs. No readings,
features, scores or predictions were synthesized.

Source: Weber, Marc (2023). *Automotive OBD-II Dataset*. Karlsruhe Institute of
Technology. DOI: https://doi.org/10.35097/1130. Dataset license: **CC BY 4.0**,
https://creativecommons.org/licenses/by/4.0/. These dataset terms are separate
from the software license. Retain this attribution and describe transformations
when redistributing the asset. The original CSV is inside the repository's
publisher archive; its checksum and the prepared source checksum are recorded
in `manifest.json`.

Packaging filters the original prepared CSV by recording ID, preserves all cell
strings and row/column order, writes UTF-8 CSV with LF line endings, and compresses
with gzip level 9, an empty filename and mtime 0. This removes filename/time
variability from the gzip header. The manifest records the preparation script's
SHA-256; `kit-10s-window-recipe-v1` names that existing recipe, not a new training
or model version. No preprocessing was rerun when packaging.

The source's `Normal` suffix is recording context, not verified vehicle health.
KIT contains combustion-engine OBD measurements and no verified mechanical
fault labels. This recording was held out from fitting/calibration but already
participated in the historical test evaluation. It is a research example, not
a user's saved vehicle, live EV battery data, or a new independent evaluation.

## Backend deployment

`app.services.kit_samples.load_sample()` resolves this directory relative to its
own Python file, independently of the process working directory. Keep the entire
`app/data/samples/kit/` directory in the backend deployment. The documented Render
service root is `backend/`; these assets are inside that root. Loading needs only
the Python standard library, no repository-root dataset, ML artifact, database,
network access, or extra dependency.

Actual Render filesystem availability has not been verified. A future image or
wheel build must explicitly retain these non-Python package assets; this project
currently documents a source deployment with Uvicorn, not wheel packaging.
No public route or inference call is installed by this step.
