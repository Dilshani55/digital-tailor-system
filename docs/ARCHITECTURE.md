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
4. **Measurements** – `logic/measurement_schema.py`: 16 fields (11 body measurements, 5 optional design values), cm/in, the design decides which are required. Missing values are errors, never defaults; unusual values give warnings, not refusals.
5. **Generate** – `routes/patterns.py` → `ParametricEngine` → base block → transformations → seam allowance → validation. Failure ⇒ HTTP 422 and nothing saved. The stored `PatternResult` holds the pieces (with cutting lines and labelled dimensions), validation report, design spec, a snapshot of the measurements used, and the drafting information (method, every calculation, armhole and sleeve-cap lengths).
6. **Estimate** – `routes/export.py` → `estimate_fabric` (nesting). Refused when validation failed.
7. **PDF** – `PDFGenerator` from the stored pieces, layout, measurement snapshot and drafting information: the one-page overview at a reduced scale and the measurement report (the app never asks for the 1:1 part).
8. **Library** – `GET /api/patterns/{id}` returns everything needed to redraw the pattern and list its PDFs.
9. **Internal research API (not in the app)** – researcher-only endpoints (`/api/research/metrics`, `/api/research/fabric-comparisons`, CSV exports) for study data; the customer app only sends the optional ease-of-use rating.

The analyse step times the classifier inference and the generate step times the drafting; both are stored and used by the research records. If the checkpoint cannot be loaded, analyse answers 503 `MODEL_UNAVAILABLE` and `GET /api/images/model-status` says so; the manual design path is unaffected. The PDF prints the stored, validated pieces.

## Backend modules

| Module | Responsibility |
|---|---|
| `routes/*` | HTTP only: authentication, ownership checks, parse, call logic, shape the JSON. No drafting maths. |
| `logic/feature_schema.py` | taxonomy, engine support levels, **scope matrix**, provenance |
| `logic/measurement_schema.py` | the only path from user input to engine input |
| `logic/drafting/` | geometry primitives, ease, drafting values, bodice (front and back drafted separately), sleeve, base block, transformations, seam allowance, validation, and the registry of every constant with its source ([pattern-drafting-method.md](pattern-drafting-method.md)) |
| `logic/units.py` | exact cm / inch / metre / yard and area conversions |
| `logic/nesting_algorithm.py` | polygon nesting + `estimate_fabric` |
| `logic/pdf_generator.py` | PDF: one-page overview at a reduced scale, measurement report (a 1:1 tiled part exists in the API but is not used by the app) |
| `logic/fabric_recommendation.py` | generic descriptive catalogue and ID lookup |
| `logic/fabric_selection.py`, `published_fabrics.py`, `fabric_research.py`, `fabric_mcda.py` | drafting compatibility; published within-study sample data plus live user preferences; optional recorded expert profiles; crisp AHP/TOPSIS and saved provenance ([method](fabric-ranking-algorithm.md), [data](published-fabric-data.md)) |
| `logic/research_metrics.py` | study metrics computed from stored data only |
| `ai/garment_models.py` | the four garment models: loading, thresholds, suggestions, status |
| `ai/garment_detector.py`, `ai/preprocess.py` | garment box; upright / crop / square-pad shared with training |
| `backend/training/` | dataset preparation, training and evaluation of the four models (see its README) |

## Cross-cutting rules

* **Fail loudly, never substitute.** Unsupported design, contradictory garment length, missing or non-positive measurements, measurements that cannot be drafted, invalid geometry, a piece wider than the cloth: each is a structured 4xx with a reason, never a silently different result.
* **Security.** JWT (24 h), bcrypt, ownership checks on every stored object, Google sign-in only via a Google-verified ID token, CORS allow-list, secrets from the environment (random per-process if unset), image content verification, JSON-only errors without internals, study-wide research data restricted to `RESEARCHER_EMAILS` and pseudonymised.
* **Reproducibility of AI.** `backend/training/` holds dataset preparation, training and evaluation. Data and weights stay outside Git; the evaluation records each model file's SHA-256 ([AI_MODELS.md](AI_MODELS.md)).

## Frontend

The selectable classes, their drafting support and the draftable combinations come from `backend/config/garment_scope.json` (imported by `utils/designSchema.js`, loaded by `feature_schema.py`); the review screen disables options that cannot be drafted. `pages/Upload.jsx` is the wizard controller (7 gated steps, see `components/StepIndicator.jsx`); `components/PredictionReview.jsx` (AI review), `MeasurementFields.jsx` (grouped inputs with a how-to-measure card), `MeasureFigure.jsx` (front and back body guide that highlights the measurement being typed), `FabricRecommendation.jsx`, `PatternPreview.jsx` (SVG: tabs for all pieces / front / back / sleeve, cutting line and sewing line switches, notches, darts, fold, grain, numbered dimensions, the sleeve-cap report and "Why this size?"), `NestingLayout.jsx` (SVG marker); `pages/History.jsx` (library) and `PatternDetail.jsx` (saved pattern). `utils/designSchema.js` and `utils/measurementSchema.js` mirror the backend schemas (a backend test fails if the taxonomy drifts); `utils/friendlyError.js` turns API failures into plain-language messages.
