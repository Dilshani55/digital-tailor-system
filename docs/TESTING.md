# Testing

Counts below are from the runs recorded in the final evidence report (see the last section for how to reproduce them). Tests that need local files that are not in Git (the trained checkpoint, the dataset manifests) **skip with an explicit "SKIPPED: …" reason**; a skip is never counted as a pass.

| Suite | Command (from the folder shown) | Count | Notes |
|---|---|---|---|
| Backend | `backend`: `venv\Scripts\python -m unittest discover -s tests -t .` | 354 | Database access is mocked; no MongoDB needed. `pymupdf` (requirements-dev.txt) is needed for the PDF tests — without it they skip visibly. |
| Frontend | `frontend`: `npm test` | 121 | vitest + Testing Library, mocked API. |
| Production build | `frontend`: `npm run build` | – | must finish without errors. |
| AI pipeline | repo root: `$env:PYTHONPATH="."; backend\venv\Scripts\python -m unittest discover -s ai_training/tests` | 134 | manifests, labels, leakage helpers, taxonomy parity, gate logic, the future 15-class pipeline (masking, readiness, human decisions, training guard, isolation from production); the checkpoint test skips if the `.pt` file is absent. |
| End-to-end | `frontend`: `npm run e2e` | 6 | Real Chrome → Vite → Flask → MongoDB → real M13 classifier → PDF: full workflow; out-of-scope design refusal; supported M13 predictions pre-selected; unsupported M13 predictions flagged with manual confirmation (real benchmark photos); every page and sidebar link renders with no console/API errors; customer -> linked pattern -> traditional-vs-system fabric comparison (system value equals the real nesting result) -> researcher summary. See below. |

## What the backend tests cover

* **Pattern maths & geometry** – `test_base_block.py` (ease, drafting values, curves, sleeve-cap solving, validator failure paths), `test_design_transformations.py` (necklines, hem rule, sleeves, API output), `test_seam_allowance.py` (offset geometry incl. per-edge allowances and the fold edge, all 15 supported designs × 3 body sizes, required pieces, construction-validation failures, scope matrix), `test_parametric.py`, `test_block_and_locked.py`.
* **Validation & contract** – `test_feature_contract.py` (taxonomy parity with `classes.json`, model heads and the frontend), `test_measurement_validation.py` (units, ranges, relations, chained image → confirm → measurements → generate).
* **Nesting / estimate / PDF** – `test_nesting.py` (exact overlap, bounds, fold, grain, quantities, widths 90/114/150, folded and open, invariance of piece dimensions, too-wide piece), `test_pdf_export.py` (A4 pages, page numbers, instructions, 5 cm calibration square, true 1:1 scale read from the PDF's vector data, tile coverage, routes: estimate blocked when validation failed, widths, stored layout reused).
* **M13 inference & taxonomy** – `test_m13_inference.py` (real checkpoint: SHA-256 unchanged, heads 3/10/6/9, direct inference on benchmark photos, supported/unsupported flags, API analyse, manual confirmation keeps the genuine prediction), `test_feature_contract.py` (15 active classes in exact order, subset of the model taxonomy, removed classes never remapped).
* **Security & robustness** – `test_hardening.py` (Google sign-in cannot be forged, JSON errors, DB outage → 503, oversized upload → 413, disguised non-images rejected, secrets, CORS, researcher-only data, pseudonyms), `test_auth_routes.py` (register/login/profile/token/ownership).
* **Research integrity** – `test_integrity_cleanup.py`, `test_research.py`, `test_multitask_integration.py` (no invented values; classifier metadata from the checkpoint).
* **Evaluation instrument & honesty (added 30 Sep 2026)** - `test_fabric_comparison.py` (system value = real nesting for the same width, stored pattern unchanged, input validation, ownership, researcher-only pseudonymised CSV, descriptive summary / `null` when empty, feedback ownership and score validation, measured times recorded), `test_m13_inference.py` (missing model -> 503 `MODEL_UNAVAILABLE` without paths, unreadable photo -> 422, `model-status`), `test_pattern_list.py` (pattern <-> customer link), `test_pdf_export.py` (PDF prints the stored pieces, drift detection, no internal error text).
* **Frontend honesty** - `HonestPages.test.jsx` (real activity instead of invented notifications, real pattern counts and no invented e-mails, working add-customer validation, measurements page on the shared schema with shoulder *length*, settings without invented server status, comparison UI, researcher summary / "Not measured"); `Wizard.test.jsx` (model-unavailable banner and 503 message).

## End-to-end (real stack)

Use isolated ports and a separate database so your own data and running servers are untouched:

```powershell
# terminal 1 – backend
cd backend
$env:PORT="5055"; $env:MONGO_URI="mongodb://localhost:27017/digital_tailor_e2e"
$env:SECRET_KEY="e2e-secret"; $env:JWT_SECRET_KEY="e2e-jwt-secret"; $env:CORS_ORIGINS="http://127.0.0.1:3055"
venv\Scripts\python run.py
# terminal 2 – frontend
cd frontend
$env:VITE_API_URL="http://127.0.0.1:5055/api"; npx vite --port 3055 --host 127.0.0.1 --strictPort
# terminal 3 – the test (optionally E2E_SHOT_DIR=… for screenshots, E2E_VIEWPORT=390x844 for phone size)
cd frontend
$env:E2E_API_URL="http://127.0.0.1:5055/api"; npm run e2e
```

The browser test registers a user, signs in, uploads a real garment photo, lets the real classifier analyse it, edits and confirms the design, sees an inline error for an out-of-range measurement, saves valid measurements, gets fabric recommendations, generates and validates the pattern, checks the SVG shows cutting lines and notches, estimates fabric for 90 / 114 / 150 cm, creates and downloads the PDF (checks the `%PDF-` header and size), sends feedback and re-opens the saved pattern from the library. A second test proves an out-of-scope design (T-shirt + square neck) cannot be confirmed.

## Reproducible evidence

```powershell
cd backend
venv\Scripts\python tools\generate_evidence.py --out ..\evidence      # 6 designs: validation, nesting at 3 widths, tiled PDFs, page images
cd ..
$env:PYTHONPATH="."; backend\venv\Scripts\python ai_training\scripts\audit_dataset.py    # dataset audit (needs the local dataset)
```
