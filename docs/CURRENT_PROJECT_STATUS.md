# Current project status (2 Oct 2026)

Verified against the code and the test runs on branch `main` (not against older reports). Categories:
**Complete** (implemented and tested) · **Partial** · **Pending human validation** (needs people, cannot be done by
code) · **Research risk** (works, but the evidence behind a research claim is weak or absent) · **Proposal
mismatch** (see [THESIS_RECONCILIATION.md](THESIS_RECONCILIATION.md)).

| Component | Status | Evidence / note |
|---|---|---|
| Authentication (JWT, bcrypt, Google ID-token verification, ownership checks) | Complete | `test_auth_routes.py`, `test_hardening.py`, E2E `auth.spec.js`; every sign-in problem answers 401 so the app signs out cleanly |
| Sessions survive a backend restart | Complete | keys in `backend/.env`, loaded at start; proven by restarting a server and reusing the token |
| Change password (current password required) | Complete | `POST /api/auth/change-password`, Settings page |
| Forgotten-password reset | Limitation (by design) | no e-mail service: the app says so; the operator uses `backend/tools/reset_password.py` |
| Customer / measurement profiles | Complete | `HonestPages.test.jsx`, E2E `customer.spec.js` |
| Dashboard, Customers and Pattern library show the same saved patterns | Complete (fixed) | the library listed only PDFs; it now lists every saved pattern with "PDF ready / PDF pending / PDF file missing"; `test_pattern_list.py`, `Library.test.jsx`, E2E `library.spec.js` |
| Delete a pattern (owner only; its PDFs go with it; customer and measurements stay) / delete one PDF (pattern stays) | Complete (added) | `test_pattern_list.py`, E2E `library.spec.js` |
| Records whose references were deleted | Complete (added) | treated as "missing", never a crash; read-only report `backend/tools/orphan_report.py` |
| Measurement entry (design-dependent fields, cm / in, exact conversion, values kept as typed) | Complete (fixed) | a decimal comma was silently dropped ("90,5" became 905); `MeasurementValidation.test.jsx`, E2E `measurements.spec.js` (desktop and phone width) |
| Wizard: every step can be opened and shows its own controls; validation only on save / generate / export; stale results invalidated | Complete (changed) | `Wizard.test.jsx`, E2E `measurements.spec.js`, `wizard.spec.js` |
| Image upload (content-checked, size-limited, random names) | Complete | `test_hardening.py` |
| AI: garment detector + four separate models (garment type MobileNetV3-Large; neckline, sleeve length, sleeve design YOLOv8n-cls) | Complete (replaced the single M40 model on 2 Oct 2026) | [AI_MODELS.md](AI_MODELS.md); `test_garment_models.py`, `test_garment_detector.py`, `test_analyse_garment_crop.py`, E2E `analysis.spec.js` |
| AI accuracy | Research risk — 90 % for every feature NOT reached | test set, app's crop, accuracy / macro-F1: garment type 0.89 / 0.89 (82 photos), sleeve length 0.88 / 0.87, neckline 0.71 / 0.60, sleeve design 0.61 / 0.46. Filled in automatically: garment type (90 % correct on 98 % of test photos), sleeve length (88 % on almost all), neckline (91 % on 43 %). Sleeve design is always "please select" |
| AI label review (725 photos: collared neck, regular sleeve) | Done by one reviewer; second reviewer pending | answered in about 24 minutes; some label noise ([HUMAN_VALIDATION.md](HUMAN_VALIDATION.md) §5) |
| Crop top | Removed (decision of 1 Oct 2026) | two garments: blouse and T-shirt; a sleeveless design is a sleeveless blouse |
| Base block, transformations, seam allowance, geometry validation | Complete | `test_base_block.py`, `test_design_transformations.py`, `test_seam_allowance.py` |
| All 96 design combinations: 25 drafted, 71 refused, none substituted | Complete | the engine itself enforces the scope; `test_design_matrix.py` |
| Drafting method traceability (Aldrich) | Research risk / proposal mismatch | about 25 constants are documented project assumptions; not verified against Aldrich |
| Fit validity | Pending human validation | no muslin / body fit trial; sheet in [HUMAN_VALIDATION.md](HUMAN_VALIDATION.md) |
| Fabric recommendation (rule-based, explained) | Complete | `FabricRecommendation.test.jsx`, `test_fabric_selection_and_widths.py` |
| Nesting + fabric requirement for 36" / 45" / 60" (heuristic, exact checks) | Complete | `test_nesting.py`, `test_design_matrix.py`; heuristic, not a minimum |
| Printable 1:1 tiled PDF | Complete | `test_pdf_export.py`; `backend/tools/verify_pdf.py` checks a produced file (A4, 5.00 cm square, sections) and runs inside the browser test |
| Printed scale on a real printer | Pending human validation | sheet in [HUMAN_VALIDATION.md](HUMAN_VALIDATION.md) |
| Fabric consumption against a tailor / cloth really used | Pending human validation | no estimates collected |
| Usability study | Pending human validation | in-app rating exists; no participants |
| Research dashboard (researcher-only, pseudonymised) | Complete | measured values only |
| Lint | Complete (added) | ESLint config; `npm run lint` passes with zero warnings |
| Dependencies | Partial | `npm audit`: 6 findings left that need major upgrades (vite, vitest, react-router) |
| Running the backend reproducibly | Complete (added) | `start_backend.ps1` uses `backend\venv` |
| Size-prediction ML model, darts / seams detection, collars, negative ease, chat assistant | Proposal mismatch (not built) | documented; listed as future work |

## Test status (runs on 2 Oct 2026, on the commit that contains this file)

| Suite | Result |
|---|---|
| Backend unittest | 422 passed, 0 skipped |
| Frontend vitest | 150 passed |
| ESLint | 0 errors, 0 warnings |
| Production build | succeeds |
| Real-stack Playwright (real Chrome, Flask, MongoDB test database, detector + four models, PDF) | 10 passed; 5 of them also at phone width |

## Still needed (cannot be done by code alone)

1. More labelled photos for sleeve design (bell, puff, regular) and for square and collared necks; a second reviewer for a sample of the 725 reviewed photos; a labelled set of real phone photos.
2. Print check with a ruler on the 5 cm square.
3. At least one muslin fit trial, or state fit as untested.
4. Traditional fabric estimates from tailors for a few designs.
5. A small usability session with consenting participants.
6. Either verify the drafting equations against Aldrich or do not claim it.

Record sheets for 1–5: [HUMAN_VALIDATION.md](HUMAN_VALIDATION.md).
