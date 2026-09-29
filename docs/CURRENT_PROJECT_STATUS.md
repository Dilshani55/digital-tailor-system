# Current project status (30 Sep 2026)

Verified against the code, the test runs and the evidence files on branch `wip/final-pattern-engine`
(not against older reports). Categories: **Complete** (implemented and tested) · **Partial** ·
**Missing** · **Research risk** (works, but the evidence behind a research claim is weak or absent) ·
**Proposal mismatch** (see [THESIS_RECONCILIATION.md](THESIS_RECONCILIATION.md)).

| Component | Status | Evidence / note |
|---|---|---|
| Authentication (JWT, bcrypt, Google ID-token verification, ownership checks) | Complete | `test_auth_routes.py`, `test_hardening.py` |
| Customer / measurement profiles | Complete | profiles are the customers; patterns now carry `measurement_id`; add-customer form fixed |
| Measurement validation (13 fields, cm/in, ranges, cross-field rules) | Complete | `test_measurement_validation.py`, `MeasurementValidation.test.jsx`, `HonestPages.test.jsx` |
| Image upload (content-checked, size-limited, random names) | Complete | `test_hardening.py` |
| AI classifier inference (M13, SHA-256 `3b69a470…`) | Complete | checksum verified 30 Sep 2026; `test_m13_inference.py` |
| AI unavailable / unreadable photo handling | Complete (added) | 503 `MODEL_UNAVAILABLE`, 422 `IMAGE_NOT_ANALYSABLE`, `GET /api/images/model-status`, wizard banner |
| Prediction review / mandatory confirmation, 15-class active taxonomy | Complete | `PredictionReview.test.jsx`, `test_feature_contract.py`, E2E `analysis.spec.js` |
| AI accuracy | Research risk | garment type macro-F1 ≈ 0.79; neckline ≈ 0.42, sleeve length ≈ 0.60, sleeve style ≈ 0.32; scope classes (sleeveless, regular sleeve) barely represented; 3 experiments failed the acceptance gate — more labelled data needed, not more training runs |
| Base block, transformations, seam allowance, geometry validation | Complete | `test_base_block.py`, `test_design_transformations.py`, `test_seam_allowance.py`, `evidence/evidence.json` |
| Drafting method traceability (Aldrich) | Research risk / proposal mismatch | ~25 constants are documented project assumptions; not verified against Aldrich |
| Fit validity | Missing (research) | no muslin / body fit trial |
| Fabric recommendation (rule-based, explained) | Complete | `FabricRecommendation.test.jsx`; now labelled rule-based |
| Nesting + fabric requirement (BLF heuristic, exact checks) | Complete | `test_nesting.py`; heuristic, not optimal |
| Printable 1:1 tiled PDF | Complete | `test_pdf_export.py` (vector-scale check); now prints the stored validated pieces |
| Traditional-vs-system fabric comparison (proposal evaluation module) | Complete as instrument (added) | `test_fabric_comparison.py`, E2E `evaluation.spec.js` |
| Fabric-waste reduction result | Missing (research) | no tailor estimates collected yet |
| Usability study | Missing (research) | in-app rating exists; no participants |
| Processing-time measurement | Complete (added) | analysis and drafting times stored per image/pattern |
| Research dashboard (researcher-only, pseudonymised) | Complete | measured values only; "Not measured" otherwise |
| Database indexes | Complete (added) | per-user / per-pattern compound indexes verified on MongoDB |
| Frontend honesty (no invented values) | Complete (fixed) | invented notifications, customer counts/e-mails, DB status removed |
| Size-prediction ML model, darts/seams detection, collars, negative ease, chat assistant | Proposal mismatch (not built) | documented; must be removed from claims or listed as future work |
| Lint | Not configured | `npm run lint` has no ESLint config in the repository |

## Test status (runs on 30 Sep 2026)

| Suite | Result |
|---|---|
| Backend unittest | 354 passed |
| AI pipeline unittest | 134 passed |
| Frontend vitest | 121 passed |
| Production build | succeeds (bundle-size warning only) |
| Real-stack Playwright E2E | 6 passed (real Chrome, Flask, MongoDB, M13 classifier, PDF) |

## What is still needed for the thesis (cannot be done by code alone)

1. Collect traditional fabric estimates from 3–5 tailors for the designs (the instrument is ready).
2. A small usability session with consenting participants (the rating is ready).
3. At least one muslin fit trial, or state fit as untested.
4. Either verify the drafting equations against Aldrich or drop the Aldrich claim.
5. More human-labelled sleeveless / regular-sleeve / neckline images if the classifier is to be improved.
