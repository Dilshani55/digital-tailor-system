# Testing

## Fabric selection usability (4 October 2026)

The fabric step asks for property goals and explicitly chosen equal/individual priorities, then shows **Recommended materials** and **Other materials** as cards. All tied highest-ranked samples are recommended. Selecting another material keeps it in Other materials. The previous technical accordion list, algorithm badge and drafting-construction explanation are absent from the page. **View Details** shows material descriptions/properties, with measured evidence under **Measurement references** inside the dialog. Unsupported cards allow details but disable selection. Published samples cannot be selected until comparison succeeds. Actual preference edits invalidate their ranking and selection; opening the editor preserves them. Dialogs contain keyboard focus, close with Escape and return focus.

The focused frontend run passed **70 tests**: FabricRecommendation (21), Wizard (39), Library (10). Lint and the production build passed. Five browser checks passed using the actual React/Flask/MongoDB stack at isolated ports 3059/5159: blouse and T-shirt at 1440×1000 and 390×844, explicit equal versus individual priorities, recommendation/other grouping, plain material details, unchanged published evidence/weights, direct/alternative selection, keyboard operation, preference invalidation, refresh, generation and saved-library evidence; and the AI-image wizard through PDF download, digital verification of 10 A4 pages and saved-library reopening. Screenshots were inspected and both screen sizes passed a document-width check. Full suites were not rerun. These functional/layout checks are not research-participant usability results or independent textile/fit validation.

```powershell
# From frontend; browser checks require the real frontend/backend test servers.
npm.cmd run test -- src/__tests__/FabricRecommendation.test.jsx src/__tests__/Wizard.test.jsx src/__tests__/Library.test.jsx
npm.cmd run lint
npm.cmd run build
$env:E2E_BASE_URL = 'http://127.0.0.1:3059'
$env:E2E_API_URL = 'http://127.0.0.1:5159/api'
npm.cmd run e2e -- e2e/fabric-ranking.spec.js
npm.cmd run e2e -- e2e/wizard.spec.js --grep 'register ->'
```

## Separate drafts and saved customer measurements (4 October 2026)

Leaving Create pattern clears its automatic resume marker. Returning (including browser Back) starts a fresh form and lists account-specific Saved drafts with customer/project, step and saved time. Continue draft explicitly restores that workflow; refreshing an active workflow restores it automatically. Start new pattern preserves previous work under a separate draft ID, Save draft & exit waits for storage before navigation, Delete draft removes only that draft, and Finish removes only the finished draft. Blank forms are not saved. The previous account-keyed IndexedDB record is offered as a legacy draft without requiring a database version change.

When a selected saved customer's fields were cleared by changing the photo/design, entering Measurements refills their saved values and original units automatically. A restored blank customer draft is repaired the same way. A new edit cancels a pending refill and is preserved across refresh; data must still be validated/saved for the current design before generation. A successful measurement save refreshes the saved profile cache. Unsaved new-customer inputs still clear after earlier edits.

The focused frontend checks passed **105 tests**: Wizard (39), MeasurementValidation (29), PredictionReview (22), FabricRecommendation (15). Wizard's final 39-test run passed after correcting a new assertion to check the step's Pending status. Lint and production build passed. Three real-browser regressions passed on isolated React/Flask/MongoDB servers at 3059/5159: multiple drafts, account isolation, refresh, sidebar exit/browser Back, explicit resume/save/delete/Finish; legacy draft compatibility; and the complete AI-image workflow with a verified 10-page A4 PDF, replacement-photo invalidation, automatic customer measurement refill and saved-library reopening. The full test suites were not rerun; these are software checks, not participant validation.

```powershell
# From frontend, with test servers running for the browser checks
npm.cmd run test -- src/__tests__/Wizard.test.jsx src/__tests__/MeasurementValidation.test.jsx src/__tests__/PredictionReview.test.jsx src/__tests__/FabricRecommendation.test.jsx
npm.cmd run lint
npm.cmd run build
$env:E2E_BASE_URL = 'http://127.0.0.1:3059'
$env:E2E_API_URL = 'http://127.0.0.1:5159/api'
npm.cmd run e2e -- e2e/wizard-draft.spec.js e2e/wizard.spec.js --grep 'refresh keeps active|existing account draft|register -> upload'
```

## Wizard edits clear dependent steps (4 October 2026)

Actual edits now clear later draft inputs/results in order: customer details clear the uploaded photo onward; a replacement photo clears AI analysis and confirmation onward; edits to an already confirmed design clear measurements onward; measurement edits clear fabric choices onward; fabric/fit/priority edits clear the pattern onward; layout changes clear PDF and feedback. Reset controls return to their defaults. Navigation and restoration do not trigger resets, and saved server profiles/patterns are retained. A late confirmation response cannot re-confirm an obsolete design.

The focused frontend run passed **97 tests** across Wizard (31), MeasurementValidation (29), PredictionReview (22) and FabricRecommendation (15). Wizard's 31 tests also passed after refining the customer-contact regression. Lint and the production build passed. The new regressions cover immediate photo replacement, rejection of invalid replacement files, failed reanalysis, edits versus simply opening the design editor, customer-detail edits, dependent results and reset persistence after refresh.

Two real-browser checks passed on isolated React/Flask/MongoDB servers at ports 3059/5159: account-specific draft restoration/reset (`wizard-draft.spec.js`) and the complete AI-image wizard (`wizard.spec.js`, `register -> upload`), including a verified 10-page A4 PDF, photo replacement clearing all later steps across reload and reopening the original saved pattern from the library. The first full-flow attempt reached the reset checks but a new assertion incorrectly expected the feedback form to remain visible without a PDF; that assertion was corrected and the full-flow rerun passed. These checks exercise software behavior; they are not participant or textile validation. The complete test suites were not rerun for this change.

```powershell
# From frontend
npm.cmd run test -- src/__tests__/Wizard.test.jsx src/__tests__/MeasurementValidation.test.jsx src/__tests__/PredictionReview.test.jsx src/__tests__/FabricRecommendation.test.jsx
npm.cmd run lint
npm.cmd run build
# With isolated frontend/backend servers running
$env:E2E_BASE_URL = 'http://127.0.0.1:3059'
$env:E2E_API_URL = 'http://127.0.0.1:5159/api'
npm.cmd run e2e -- e2e/wizard.spec.js e2e/wizard-draft.spec.js --grep 'register -> upload|drafts survive'
```

## Wizard refresh checks (4 October 2026)

The wizard now saves a versioned account-specific draft in IndexedDB, including the original photo File. It waits for restoration before writing defaults. The focused frontend run passed **122 tests** across Wizard, MeasurementValidation, PredictionReview, FabricRecommendation, DesignSchema and IntegrityCleanup; lint and production build passed. The reload regressions cover earlier-step inputs, unconfirmed review edits, entered units, saved IDs, generated results, stale-result detection, explicit customer selection, failed storage and draft reset. Existing measurement tests now wait for draft restoration before interacting.

Two real-browser checks passed on the actual React/Flask/MongoDB stack at isolated test ports 3059/5159: `wizard-draft.spec.js` checks refresh, account switching, browser-local draft isolation, Start new pattern and Finish; the full AI-image wizard in `wizard.spec.js` now refreshes through photo selection, AI review, unsaved measurements, fabric ranking/selection, pattern, estimate, PDF and feedback. Its downloaded report passed digital PDF verification (10 A4 pages). These are software regressions, not collected research participant responses. The complete frontend/backend/browser suites were not rerun for this change.

```powershell
# From frontend
npm.cmd run test -- src/__tests__/Wizard.test.jsx src/__tests__/MeasurementValidation.test.jsx src/__tests__/PredictionReview.test.jsx src/__tests__/FabricRecommendation.test.jsx src/__tests__/DesignSchema.test.jsx src/__tests__/IntegrityCleanup.test.jsx
# With current frontend/backend running; override the two URLs for your test servers
$env:E2E_BASE_URL = 'http://127.0.0.1:3059'
$env:E2E_API_URL = 'http://127.0.0.1:5159/api'
npm.cmd run e2e -- e2e/wizard-draft.spec.js
npm.cmd run e2e -- e2e/wizard.spec.js --grep 'register -> upload'
```

## Fabric algorithm checks (4 October 2026)

The fabric workflow now uses published sample tables and live user goals/pairwise answers with crisp AHP/TOPSIS. The focused backend run passed **56 tests**, covering arithmetic, source-table anchors, user-input validation, catalogue integrity, saved pattern evidence and generation/ownership regressions. Fabric, wizard and library UI tests passed **44 tests**. Lint and production build passed; the `--published` CLI validated all 18 records. Synthetic fixtures remain test inputs and are not empirical validation. An earlier broader 53-test backend run additionally covered standard-width estimates and the design matrix.

```powershell
# From backend
venv\Scripts\python.exe -m unittest tests.test_fabric_mcda tests.test_fabric_recommendation tests.test_fabric_selection_and_widths.TestRecommendation tests.test_published_fabrics tests.test_measurement_validation.TestGenerateUsesValidatedMeasurements tests.test_pattern_list -q
# From frontend
npm.cmd run test -- src/__tests__/FabricRecommendation.test.jsx src/__tests__/Wizard.test.jsx src/__tests__/Library.test.jsx
npm.cmd run lint
npm.cmd run build
```

The two real-browser regressions in `e2e/fabric-ranking.spec.js` passed with the actual React, Flask and MongoDB stack: blouse and T-shirt manual design, measurements, explicit preferences, published-sample ranking, source/weights display, generation and reopening saved evidence. They use test-user answers, not collected participant responses. Initial attempts on port 5055 reached a stale server (old measurement range validation / unavailable model); fresh isolated ports 5157/3057 resolved that environment conflict. A further real AI-image wizard regression passed on the fresh stack: image analysis, confirmed design, published-sample preferences/ranking, pattern generation, three-width estimates, reduced-scale PDF download/verification, feedback and library reopening (1 test, 42.5 s; 10-page A4 report verified). The full browser suite was not run. See [method](fabric-ranking-algorithm.md) and [published data](published-fabric-data.md).

```powershell
# With the current backend/frontend running on isolated test ports
$env:E2E_API_URL = 'http://127.0.0.1:5157/api'
$env:E2E_BASE_URL = 'http://127.0.0.1:3057'
npm.cmd run e2e -- e2e/fabric-ranking.spec.js
npm.cmd run e2e -- e2e/wizard.spec.js --grep 'register -> upload'
# From the repository root; no web server needed
backend\venv\Scripts\python.exe backend\tools\fabric_research_data.py --published
```

## Historical suite counts (2 October 2026)

Counts below are from the runs of 2 Oct 2026 on the commit that contains this file. Tests that need local files that are not in Git (the trained models, benchmark photos) **skip with an explicit "SKIPPED: …" reason**; a skip is never counted as a pass. In these runs the model files were present and nothing was skipped.

| Suite | Command (from the folder shown) | Count | Notes |
|---|---|---|---|
| Backend | `backend`: `venv\Scripts\python -m unittest discover -s tests -t .` | 475 | Database access is mocked; no MongoDB needed. `pymupdf` (requirements-dev.txt) is needed for the PDF tests — without it they skip visibly. The tests of the real models skip when the files in `backend/model/` are absent. |
| Frontend | `frontend`: `npm test` | 165 | vitest + Testing Library, mocked API. |
| Lint | `frontend`: `npm run lint` | 0 errors, 0 warnings | ESLint 8: recommended + React + hooks rules (`frontend/.eslintrc.cjs`). |
| Production build | `frontend`: `npm run build` | – | must finish without errors. |
| End-to-end | `frontend`: `npm run e2e` | 10 (+ 5 repeated at phone width) | Real Chrome → Vite → Flask → MongoDB (test database) → real detector + the four real garment models → real PDF. See the list below. |

## What the backend tests cover

* **Pattern maths & geometry** – `test_base_block.py` (every formula of the drafting method from the measurements; the source's own sample as a reference test with a tolerance; front and back not identical; armhole curve lengths; sleeve cap against armhole, PASS / REVIEW; ease separate from seam allowance; notch distances; validator failure paths), `test_design_transformations.py` (necklines, hem rule, sleeves, API output), `test_seam_allowance.py` (offset geometry incl. per-edge allowances and the fold edge, supported designs × 3 body sizes, required pieces, construction-validation failures, scope matrix), `test_puff_sleeves.py`, `test_parametric.py`, `test_block_and_locked.py`.
* **Validation & contract** – `test_feature_contract.py` (the selectable classes 2 / 4 / 3 / 4 in exact order, the same file for backend and frontend, removed classes such as crop-top and off-shoulder rejected and never remapped), `test_measurement_validation.py` (the 16 fields and which design needs which; exact cm / inch conversion; warnings that never block; a profile of an earlier version is asked for the new fields and nothing is estimated; design values can be emptied again; the generate route returns and stores the calculation list, armhole and sleeve-cap lengths, method and display unit; per-edge seam allowances move only the cutting line; chained image → confirm → measurements → generate).
* **Nesting / estimate / PDF** – `test_nesting.py` (exact overlap, bounds, fold, grain, quantities, widths, folded and open, invariance of piece dimensions, too-wide piece, exact metre / yard / m² / yd² conversions, one-way fabric never shorter than two-way, best of three placing orders), `test_pdf_export.py` (A4 pages, page numbers, instructions, 5 cm calibration square, true 1:1 scale read from the PDF's vector data, tile coverage, the one-page overview with the real blocks drawn at a stated reduced scale 1:n and this pattern's own numbers (cm and inches, sleeveless without a sleeve panel), block overviews marked NOT TO SCALE, the calculation pages, overview-only, report-only and pattern-only export, routes: estimate blocked when validation failed, widths, stored layout reused).
* **AI models** – `test_garment_models.py` (picture preparation: upright, crop, square padding without stretching; thresholds: a score below the threshold or a model without a threshold is "uncertain"; sleeveless gives sleeve style `none` without asking the sleeve-design model; a missing model file leaves that feature to the user; status reports four different files; API analyse / model-status; the real model files on real benchmark photos), `test_garment_detector.py`, `test_analyse_garment_crop.py` (the models see the detector's crop; whole-photo fallback is reported).
* **Security & robustness** – `test_hardening.py` (Google sign-in cannot be forged, JSON errors, DB outage → 503, oversized upload → 413, disguised non-images rejected, secrets, CORS, researcher-only data, pseudonyms), `test_auth_routes.py` (register/login/profile/token/ownership).
* **Research integrity** – `test_integrity_cleanup.py`, `test_research.py` (no invented values; model results are read from the evaluation file or reported as not measured).
* **Evaluation instrument & honesty** - `test_fabric_comparison.py` (system value = real nesting for the same width, stored pattern unchanged, input validation, ownership, researcher-only pseudonymised CSV, descriptive summary / `null` when empty, feedback ownership and score validation, measured times recorded), `test_garment_models.py` (missing models -> 503 `MODEL_UNAVAILABLE` without paths, unreadable photo -> 422, `model-status`), `test_pattern_list.py` (pattern <-> customer link), `test_pdf_export.py` (PDF prints the stored pieces, drift detection, no internal error text).
* **Frontend honesty** - `HonestPages.test.jsx` (real activity instead of invented notifications, real pattern counts and no invented e-mails, working add-customer validation, measurements page on the shared schema, settings without invented server status, comparison UI, researcher summary / "Not measured"); `Wizard.test.jsx` (model-unavailable banner and 503 message).

## Other suites worth knowing

* `test_pattern_list.py` – the one saved-pattern list (customer name, design, PDFs with `file_available`), pattern delete (owner only, PDFs removed, customer kept, file names cannot escape the output folder), references to deleted records answer "missing".
* `test_design_matrix.py` – all 72 design combinations: the 19 supported ones for three body sizes (requested design drafted, pieces and quantities, ease, darts, sleeve cap against armhole, sleeve length, seam allowance, grainline, fold, notches) and their layout on 36" / 45" / 60"; the 53 others are refused by the engine.
* `test_auth_routes.py` – fixed key survives a restart, token from another key / tampered / expired answers 401, change password, operator reset tool.
* `Library.test.jsx`, `Wizard.test.jsx`, `MeasurementValidation.test.jsx`, `HonestPages.test.jsx` – library states, every wizard step opened directly, strict decimal parsing, values re-opened as entered, password form; grouped measurement fields, the front / back guide following the active field, calculated-value hints, warnings.
* `PatternPreview.test.jsx` – tabs per block, numbered dimensions linked to their calculation and highlighted on hover, sewing line / cutting line switches, the sleeve-cap report, "Why this size?", lengths in the chosen unit.

## End-to-end (real stack)

| Spec | What it proves in a real browser |
|---|---|
| `auth.spec.js` | a wrong password stays on the form; an invalid session signs out; change password; "forgot password" does not pretend to send an e-mail |
| `customer.spec.js` | customer created in the UI, pattern linked to it, saved pattern opens with its stored block dimensions, sleeve-cap result and calculation list, settings show the real model state |
| `library.spec.js` | dashboard, customers and library agree; "PDF pending"; create PDF; delete PDF only; delete pattern; a deleted customer does not break the pattern; a failed request is an error, not an empty library or a zero |
| `measurements.spec.js` (2 tests) | Measurements page: key-by-key typing, decimals, comma, cm / in without double conversion, save, reload, edit, zero / negative refused, large value not clamped. Wizard: steps 3–8 opened directly show their controls and no invented numbers; design chosen inside the measurement step; sleeve guide follows the value; incompatible fabric cleared with a reason; fit change invalidates the pattern |
| `analysis.spec.js` (2 tests) | the server really loaded four different model files (MobileNetV3-Large + three YOLOv8n-cls); on real photos every feature shows its own score; a feature is pre-selected exactly when its model's score reaches its threshold; no crop-top anywhere; manual confirmation; the genuine prediction is stored next to the user's choice |
| `pages.spec.js` | every page and sidebar link renders with no console error and no failed API call |
| `wizard.spec.js` (2 tests) | the full workflow to a downloaded PDF: grouped measurement fields with the body guide and calculated-value hints, Front / Back / Sleeve tabs with dimensions, sleeve-cap report, "Why this size?", sewing / cutting line switch, estimate in m, yd, m², yd² with the one-way option; the default PDF is the one-page reduced-scale overview, no real-size option is offered; the full report is then checked digitally (`verify_pdf.py`: A4, sections, no page claiming real size); out-of-scope design cannot be confirmed, saved or drafted |

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
venv\Scripts\python tools\verify_pdf.py path\to\sewing_pattern.pdf      # A4, sections, no page claiming real size (and the 5 cm square if a 1:1 part is present)
venv\Scripts\python tools\orphan_report.py --out ..\evidence\db_integrity   # records whose references no longer match; changes nothing
```

The browser test registers a user, signs in, uploads a real garment photo, lets the real models analyse it, edits and confirms the design, sees only the measurements that design needs (for a short-sleeve blouse: no height, neck or wrist), sees an inline error for a non-positive value, checks the unit toggle keeps typed values, saves the measurements, gets fabric recommendations, generates and validates the pattern, checks the SVG shows cutting lines and notches, estimates fabric for 36" / 45" / 60" (91.44 / 114.3 / 152.4 cm), creates and downloads the PDF (checks the `%PDF-` header and size), sends feedback, opens later steps freely and sees that a changed measurement marks the pattern, estimate and PDF as needing regeneration, and re-opens the saved pattern from the library. A second test proves an out-of-scope design (T-shirt + square neck) cannot be confirmed.

## Reproducible evidence

```powershell
cd backend
venv\Scripts\python tools\generate_evidence.py --out ..\evidence      # 6 designs: validation, nesting at 3 widths, tiled PDFs, page images
```

The AI results are reproduced with the three commands in [backend/training/README.md](../backend/training/README.md).
