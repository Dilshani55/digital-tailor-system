# Testing

Counts below are from the runs of 1 Oct 2026 on the commit that contains this file. Tests that need local files that are not in Git (the trained checkpoint, the dataset manifests) **skip with an explicit "SKIPPED: …" reason**; a skip is never counted as a pass.

| Suite | Command (from the folder shown) | Count | Notes |
|---|---|---|---|
| Backend | `backend`: `venv\Scripts\python -m unittest discover -s tests -t .` | 441 | Database access is mocked; no MongoDB needed. `pymupdf` (requirements-dev.txt) is needed for the PDF tests — without it they skip visibly. |
| Frontend | `frontend`: `npm test` | 155 | vitest + Testing Library, mocked API. |
| Lint | `frontend`: `npm run lint` | 0 errors, 0 warnings | ESLint 8: recommended + React + hooks rules (`frontend/.eslintrc.cjs`). |
| Production build | `frontend`: `npm run build` | – | must finish without errors. |
| AI pipeline | repo root: `$env:PYTHONPATH="."; backend\venv\Scripts\python -m unittest discover -s ai_training/tests` | 162 | manifests, labels, leakage helpers, taxonomy parity, gate logic, the M42 pipeline (acceptance gate fixed before training, audit helpers, manifest fixes, review decisions, review tool); checkpoint tests skip if the `.pt` file is absent. |
| End-to-end | `frontend`: `npm run e2e` | 10 | Real Chrome → Vite → Flask → MongoDB (test database) → real detector + M40 classifier → real PDF. See the list below. |

## What the backend tests cover

* **Pattern maths & geometry** – `test_base_block.py` (ease, drafting values, curves, sleeve-cap solving, validator failure paths), `test_design_transformations.py` (necklines, hem rule, sleeves, API output), `test_seam_allowance.py` (offset geometry incl. per-edge allowances and the fold edge, all 15 supported designs × 3 body sizes, required pieces, construction-validation failures, scope matrix), `test_parametric.py`, `test_block_and_locked.py`.
* **Validation & contract** – `test_feature_contract.py` (taxonomy parity with `classes.json`, model heads and the frontend), `test_measurement_validation.py` (units, ranges, relations, chained image → confirm → measurements → generate).
* **Nesting / estimate / PDF** – `test_nesting.py` (exact overlap, bounds, fold, grain, quantities, widths, folded and open, invariance of piece dimensions, too-wide piece), `test_pdf_export.py` (A4 pages, page numbers, instructions, 5 cm calibration square, true 1:1 scale read from the PDF's vector data, tile coverage, routes: estimate blocked when validation failed, widths, stored layout reused).
* **M13 inference & taxonomy** – `test_m13_inference.py` (real checkpoint: SHA-256 unchanged, heads 3/10/6/9, direct inference on benchmark photos, supported/unsupported flags, API analyse, manual confirmation keeps the genuine prediction), `test_feature_contract.py` (15 active classes in exact order, subset of the model taxonomy, removed classes never remapped).
* **Security & robustness** – `test_hardening.py` (Google sign-in cannot be forged, JSON errors, DB outage → 503, oversized upload → 413, disguised non-images rejected, secrets, CORS, researcher-only data, pseudonyms), `test_auth_routes.py` (register/login/profile/token/ownership).
* **Research integrity** – `test_integrity_cleanup.py`, `test_research.py`, `test_multitask_integration.py` (no invented values; classifier metadata from the checkpoint).
* **Evaluation instrument & honesty (added 30 Sep 2026)** - `test_fabric_comparison.py` (system value = real nesting for the same width, stored pattern unchanged, input validation, ownership, researcher-only pseudonymised CSV, descriptive summary / `null` when empty, feedback ownership and score validation, measured times recorded), `test_m13_inference.py` (missing model -> 503 `MODEL_UNAVAILABLE` without paths, unreadable photo -> 422, `model-status`), `test_pattern_list.py` (pattern <-> customer link), `test_pdf_export.py` (PDF prints the stored pieces, drift detection, no internal error text).
* **Frontend honesty** - `HonestPages.test.jsx` (real activity instead of invented notifications, real pattern counts and no invented e-mails, working add-customer validation, measurements page on the shared schema with shoulder *length*, settings without invented server status, comparison UI, researcher summary / "Not measured"); `Wizard.test.jsx` (model-unavailable banner and 503 message).

## What was added on 1 Oct 2026

* `test_pattern_list.py` – the one saved-pattern list (customer name, design, PDFs with `file_available`), pattern delete (owner only, PDFs removed, customer kept, file names cannot escape the output folder), references to deleted records answer "missing".
* `test_design_matrix.py` – all 180 design combinations: the 34 supported ones for three body sizes and each allowed fabric construction (requested design drafted, pieces and quantities, ease, darts, sleeve cap against armhole, sleeve length, seam allowance, grainline, fold, notches) and their layout on 36" / 45" / 60"; the 146 others are refused by the engine.
* `test_auth_routes.py` – fixed key survives a restart, token from another key / tampered / expired answers 401, change password, operator reset tool.
* `Library.test.jsx`, `Wizard.test.jsx`, `MeasurementValidation.test.jsx`, `HonestPages.test.jsx` – library states, every wizard step opened directly, strict decimal parsing, values re-opened as entered, password form.
* `ai_training/tests/test_m42_pipeline.py` – see the table.

## End-to-end (real stack)

| Spec | What it proves in a real browser |
|---|---|
| `auth.spec.js` | a wrong password stays on the form; an invalid session signs out; change password; "forgot password" does not pretend to send an e-mail |
| `customer.spec.js` | customer created in the UI, pattern linked to it, saved pattern opens, settings show the real model state |
| `library.spec.js` | dashboard, customers and library agree; "PDF pending"; create PDF; delete PDF only; delete pattern; a deleted customer does not break the pattern; a failed request is an error, not an empty library or a zero |
| `measurements.spec.js` (2 tests) | Measurements page: key-by-key typing, decimals, comma, cm / in without double conversion, save, reload, edit, zero / negative refused, large value not clamped. Wizard: steps 3–8 opened directly show their controls and no invented numbers; design chosen inside the measurement step; sleeve guide follows the value; incompatible fabric cleared with a reason; fit change invalidates the pattern |
| `analysis.spec.js` (2 tests) | real classifier on real photos: separate scores, uncertain features not pre-selected, manual confirmation |
| `pages.spec.js` | every page and sidebar link renders with no console error and no failed API call |
| `wizard.spec.js` (2 tests) | the full workflow to a downloaded PDF, which is then checked digitally (`verify_pdf.py`: A4, 5.00 × 5.00 cm square, sections); out-of-scope design cannot be confirmed, saved or drafted |

`measurements.spec.js`, `library.spec.js` and `wizard.spec.js` also run at phone width: `$env:E2E_VIEWPORT="390x844"`.

Use isolated ports and a separate database so your own data and running servers are untouched:

```powershell
# terminal 1 – backend
cd backend
$env:PORT="5055"; $env:MONGO_URI="mongodb://localhost:27017/digital_tailor_e2e"
$env:SECRET_KEY="e2e-secret-e2e-secret-e2e-secret-0001"; $env:JWT_SECRET_KEY="e2e-jwt-secret-e2e-jwt-secret-000001"; $env:CORS_ORIGINS="http://127.0.0.1:3055"
$env:UPLOAD_FOLDER="$env:TEMP\dt_e2e_uploads"; $env:OUTPUT_FOLDER="$env:TEMP\dt_e2e_outputs"      # keep test photos and PDFs out of your own folders
venv\Scripts\python run.py
# terminal 2 – frontend
cd frontend
$env:VITE_API_URL="http://127.0.0.1:5055/api"; npx vite --port 3055 --host 127.0.0.1 --strictPort
# terminal 3 – the test (optionally E2E_SHOT_DIR=… for screenshots, E2E_VIEWPORT=390x844 for phone size)
cd frontend
$env:E2E_API_URL="http://127.0.0.1:5055/api"; npm run e2e
```

The test database `digital_tailor_e2e` is separate from the real `digital_tailor_db`; the tests only register new
accounts in it.

## Checks on real data and files (read-only)

```powershell
cd backend
venv\Scripts\python tools\verify_pdf.py path\to\sewing_pattern.pdf      # A4, 5.00 cm calibration square, sections (reads the PDF's vector data)
venv\Scripts\python tools\orphan_report.py --out ..\evidence\db_integrity   # records whose references no longer match; changes nothing
```

The browser test registers a user, signs in, uploads a real garment photo, lets the real classifier analyse it, edits and confirms the design, sees only the measurements that design needs (no wrist/height for a short-sleeve blouse), sees an inline error for a non-positive value, checks the unit toggle keeps typed values, saves the measurements, gets fabric recommendations, generates and validates the pattern, checks the SVG shows cutting lines and notches, estimates fabric for 36" / 45" / 60" (91.44 / 114.3 / 152.4 cm), creates and downloads the PDF (checks the `%PDF-` header and size), sends feedback, opens later steps freely and sees that a changed measurement marks the pattern, estimate and PDF as needing regeneration, and re-opens the saved pattern from the library. A second test proves an out-of-scope design (T-shirt + square neck) cannot be confirmed.

## Reproducible evidence

```powershell
cd backend
venv\Scripts\python tools\generate_evidence.py --out ..\evidence      # 6 designs: validation, nesting at 3 widths, tiled PDFs, page images
cd ..
$env:PYTHONPATH="."; backend\venv\Scripts\python ai_training\scripts\audit_dataset.py    # dataset audit (needs the local dataset)
```
