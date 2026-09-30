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
2. **Analyse** – `ai/multitask_classifier.py` loads the deployed M13 checkpoint once (thread-safe; outputs 3/10/6/9 classes, unchanged), returns for each of 4 heads the top-1 label, top-3 and confidence. `feature_schema.annotate_predictions` then adds scope flags **without altering any prediction**: a label outside the 15 selectable classes gets `suggested_label = null` and the user must choose manually. Low-confidence heads are flagged too.
3. **Confirm** – the user edits/accepts one of the 15 selectable classes (`UI_TAXONOMY`; the model taxonomy is `MODEL_TAXONOMY`, never remapped). `logic/feature_schema.py` validates the taxonomy, the sleeve consistency rule and the **project scope matrix**, and stores a `design_spec` with provenance (`ml_prediction_confirmed`, `user_corrected`, `manual_selection`). *Client-supplied features are ignored at generation time; only the stored confirmed design is used.*
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
| `ai/multitask_classifier.py` | model definition + inference + checkpoint checksum/version |
| `ai/yolo_detector.py` | legacy computer-vision fallback for `detected_features` (never gives a confidence) |

## Cross-cutting rules

* **Fail loudly, never substitute.** Unsupported design, contradictory garment length, implausible measurements, invalid geometry, a piece wider than the cloth: each is a structured 4xx with a reason, never a silently different result.
* **Security.** JWT (24 h), bcrypt, ownership checks on every stored object, Google sign-in only via a Google-verified ID token, CORS allow-list, secrets from the environment (random per-process if unset), image content verification, JSON-only errors without internals, study-wide research data restricted to `RESEARCHER_EMAILS` and pseudonymised.
* **Reproducibility of AI.** `ai_training/` holds the pipeline (manifests → training → evaluation → dataset audit → acceptance gate). Data and checkpoints stay outside Git; their SHA-256 checksums are recorded in [AI_EVIDENCE.md](AI_EVIDENCE.md).

## Frontend

The 15 selectable classes, their drafting support and the draftable combinations come from `config/garment_scope.json` (imported by `utils/designSchema.js`, loaded by `feature_schema.py`); the review screen disables options that cannot be drafted. `pages/Upload.jsx` is the wizard controller (7 gated steps, see `components/StepIndicator.jsx`); `components/PredictionReview.jsx` (AI review), `MeasurementGuide.jsx`, `FabricRecommendation.jsx`, `PatternPreview.jsx` (SVG: cutting line, dashed sewing line, notches, darts, fold, grain), `NestingLayout.jsx` (SVG marker); `pages/History.jsx` (library) and `PatternDetail.jsx` (saved pattern). `utils/designSchema.js` and `utils/measurementSchema.js` mirror the backend schemas (a backend test fails if the taxonomy drifts); `utils/friendlyError.js` turns API failures into plain-language messages.
