# Architecture

```
 React (Vite)                Flask REST API                 MongoDB
 ┌──────────────┐  JSON/JWT  ┌────────────────────────┐    ┌──────────────┐
 │ 7-step wizard│───────────►│ routes/  (thin)        │───►│ users, images │
 │ pattern view │            │ logic/   (all rules)   │    │ measurements  │
 │ library      │◄───────────│ ai/      (classifier)  │    │ sessions      │
 └──────────────┘  PDF blob  └──────────┬─────────────┘    │ patterns, PDFs│
                                        │                  │ research      │
                          checkpoint (.pt, not in Git)     └──────────────┘
```

## Data flow of one pattern

1. **Upload** – `routes/images.py` decodes and validates the file (real JPG/PNG/WEBP, ≤ 16 MB), stores it under a random name.
2. **Analyse** – `ai/garment_detector.py` finds the garment; `ai/garment_models.py` loads the four models from `backend/model/` once (thread-safe) and returns for each feature the top-1 label, top-3 and score, with `uncertain` set from that model's validation-chosen threshold (`backend/model/thresholds.json`). The picture every model sees is prepared by `ai/preprocess.py` (upright, cropped to the garment, padded to a square) - the same code the training uses.
3. **Confirm** – the user edits/accepts the selectable classes. `logic/feature_schema.py` validates the taxonomy, the sleeve consistency rule and the **project scope matrix**, and stores a `design_spec` with provenance (`ml_prediction_confirmed`, `user_corrected`, `manual_selection`). *Client-supplied features are ignored at generation time; only the stored confirmed design is used.*
4. **Measurements** – `logic/measurement_schema.py`: 13 fields, cm/in, ranges, relations. Missing values are errors, never defaults.
5. **Generate** – `routes/patterns.py` → `ParametricEngine` → base block → transformations → seam allowance → validation. Failure ⇒ HTTP 422 and nothing saved. The stored `PatternResult` holds the pieces (with cutting lines), validation report, design spec and a snapshot of the measurements used.
6. **Estimate** – `routes/export.py` → `estimate_fabric` (nesting). Refused when validation failed.
7. **PDF** – `PDFGenerator` from the stored layout width/mode and the measurement snapshot.
8. **Library** – `GET /api/patterns/{id}` returns everything needed to redraw the pattern and list its PDFs.
9. **Internal research API (not in the app)** – researcher-only endpoints (`/api/research/metrics`, `/api/research/fabric-comparisons`, CSV exports) for study data; the customer app only sends the optional ease-of-use rating.

The analyse step times the classifier inference and the generate step times the drafting; both are stored and used by the research records. If the checkpoint cannot be loaded, analyse answers 503 `MODEL_UNAVAILABLE` and `GET /api/images/model-status` says so; the manual design path is unaffected. The PDF prints the stored, validated pieces.

## Backend modules

| Module | Responsibility |
|---|---|
| `routes/*` | HTTP only: authentication, ownership checks, parse, call logic, shape the JSON. No drafting maths. |
| `logic/feature_schema.py` | taxonomy, engine support levels, **scope matrix**, provenance |
| `logic/measurement_schema.py` | the only path from user input to engine input |
| `logic/drafting/` | geometry primitives, ease, drafting values, bodice, sleeve, base block, transformations, seam allowance, validation, assumptions registry |
| `logic/nesting_algorithm.py` | polygon nesting + `estimate_fabric` |
| `logic/pdf_generator.py` | printable 1:1 tiled PDF |
| `logic/fabric_recommendation.py` | rule-based, explainable fabric ranking and catalogue |
| `logic/research_metrics.py` | study metrics computed from stored data only |
| `ai/garment_models.py` | the four garment models: loading, thresholds, suggestions, status |
| `ai/garment_detector.py`, `ai/preprocess.py` | garment box; upright / crop / square-pad shared with training |
| `backend/training/` | dataset preparation, training and evaluation of the four models (see its README) |

## Cross-cutting rules

* **Fail loudly, never substitute.** Unsupported design, contradictory garment length, missing or non-positive measurements, measurements that cannot be drafted, invalid geometry, a piece wider than the cloth: each is a structured 4xx with a reason, never a silently different result.
* **Security.** JWT (24 h), bcrypt, ownership checks on every stored object, Google sign-in only via a Google-verified ID token, CORS allow-list, secrets from the environment (random per-process if unset), image content verification, JSON-only errors without internals, study-wide research data restricted to `RESEARCHER_EMAILS` and pseudonymised.
* **Reproducibility of AI.** `backend/training/` holds dataset preparation, training and evaluation. Data and weights stay outside Git; the evaluation records each model file's SHA-256 ([AI_MODELS.md](AI_MODELS.md)).

## Frontend

The selectable classes, their drafting support and the draftable combinations come from `backend/config/garment_scope.json` (imported by `utils/designSchema.js`, loaded by `feature_schema.py`); the review screen disables options that cannot be drafted. `pages/Upload.jsx` is the wizard controller (7 gated steps, see `components/StepIndicator.jsx`); `components/PredictionReview.jsx` (AI review), `MeasureFigure.jsx` (measurement guide), `FabricRecommendation.jsx`, `PatternPreview.jsx` (SVG: cutting line, dashed sewing line, notches, darts, fold, grain), `NestingLayout.jsx` (SVG marker); `pages/History.jsx` (library) and `PatternDetail.jsx` (saved pattern). `utils/designSchema.js` and `utils/measurementSchema.js` mirror the backend schemas (a backend test fails if the taxonomy drifts); `utils/friendlyError.js` turns API failures into plain-language messages.
