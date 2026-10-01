# AI-Assisted Digital Tailor System

Final-year research project — **D N M Vitharana (28404)**, BSc (Hons) Software Engineering, NSBM Green University. Supervisor: Mr. Anton Jayakody.

A web system that turns a garment photo and a person's body measurements into a **printable, full-size (1:1) sewing pattern** for women's **blouses, T-shirts and crop-tops**, together with a fabric estimate.

## What it does

```
Garment photo ─► AI suggests the design ─► YOU review and confirm it ─► body measurements (validated)
      ─► fabric & fit ─► parametric pattern drafting (deterministic maths, not AI)
      ─► seam allowances + notches ─► automatic geometry validation
      ─► polygon nesting on 36" / 45" / 60" (91.44 / 114.3 / 152.4 cm) fabric ─► fabric quantity
      ─► printable 1:1 tiled A4 PDF ─► saved in your pattern library
```

* **AI part.** A garment detector finds the top in the photo, then one image classifier (YOLOv8n-cls backbone, four output heads: garment type, neckline, sleeve length, sleeve style) looks at that area. Today only **sleeve length** is filled in automatically when the model is confident; the other three features are shown as "please select". Its answers are only *suggestions*; the user must confirm or correct them, and only the confirmed design reaches the pattern engine. Users choose from 15 active classes (3 / 5 / 3 / 4); if the model predicts something outside them the app says so and asks for manual confirmation — it never swaps in a similar class.
* **Pattern part.** Pure, deterministic geometry (`backend/app/logic/drafting/`). No second AI model invents the pattern. Every constant that is not derived from your measurements is listed in `assumptions.py` and marked as a *project assumption*.
* **Fabric part.** Fabric recommendation is rule-based and explains itself. The fabric quantity comes from laying the real cutting-line polygons on the cloth (Bottom-Left-Fill heuristic).
* **What it is not.** The system does not ask for or predict a tailor's estimate: the fabric requirement is calculated from the real pattern pieces. Study-wide research endpoints exist only as an internal, researcher-only API (not in the app).
* **One source of truth.** The 15 selectable classes, what the engine can draft and the allowed combinations are in [`config/garment_scope.json`](config/garment_scope.json), read by both the backend and the frontend.

### Supported designs (anything else is rejected with a clear message)

| Garment | Necklines | Sleeve lengths | Sleeve styles | Construction |
|---|---|---|---|---|
| Blouse | round, V, square | short, long | regular, puff, bell | woven bodice |
| T-shirt | round, V | short, long | regular | knit bodice |
| Crop-top | round, V, square | sleeveless (style *none*), short | none / regular, puff, bell | woven or knit (chosen by fabric) |

Collared and off-shoulder necklines are part of the AI taxonomy but have **no pattern geometry yet**: the app shows
such a prediction and asks for a supported choice. The matrix lives in [`config/garment_scope.json`](config/garment_scope.json).

### Honest status

The pattern is **mathematically generated and geometry-validated**. It has **not** been fit-tested on bodies or checked by a professional pattern-maker — make a test garment (muslin) before cutting good fabric. See [docs/LIMITATIONS_AND_CLAIMS.md](docs/LIMITATIONS_AND_CLAIMS.md) for exactly what can and cannot be claimed.

## Quick start (Windows)

Requirements: **Python 3.10+** (developed on 3.14), **Node.js 18+**, **MongoDB** running on `localhost:27017`, and Google Chrome (only for the browser tests).

```powershell
# terminal 1 - the API, http://127.0.0.1:5000  (always runs with the project's own backend\venv)
powershell -ExecutionPolicy Bypass -File start_backend.ps1

# terminal 2 - the web app, http://localhost:3000
powershell -ExecutionPolicy Bypass -File start_frontend.ps1
```

The first run creates `backend\venv`, installs the requirements and creates `backend\.env` with two random secret
keys (sign-in tokens then stay valid when the server restarts). Doing the same by hand:

```powershell
cd backend
python -m venv venv
venv\Scripts\python -m pip install -r requirements.txt     # add -r requirements-dev.txt for the PDF tests
copy .env.example .env                                      # then set SECRET_KEY and JWT_SECRET_KEY in .env
venv\Scripts\python run.py
cd ..\frontend; npm install; npm run dev
```

Start the API with `backend\venv\Scripts\python`, not a system-wide `python`: the versions in `requirements.txt` are
the tested ones, and `run.py` prints which interpreter and which database it is using.

The trained classifiers are **not stored in Git** (large files). Put the current model (M40, 3/5/3/4 classes) at
`backend/app/ai/models/garment_multitask_m40_15class.pt` (its validation-selected thresholds file is tracked next to it) and the
pretrained backbone at `backend/app/ai/models/yolov8n-cls.pt`. The garment detector goes at `backend/app/ai/models/garment_detector_v1.pt` (without it the classifier looks at the whole photo). The previous model (M13) at
`backend/app/ai/models/garment_multitask_yolov8_best.pt` is the automatic fallback and the rollback: set the environment variable
`GARMENT_MODEL_PATH` to choose a specific checkpoint. Checksums, test results and the honest accuracy figures are in
[docs/AI_EVIDENCE.md](docs/AI_EVIDENCE.md) (§7). Without any checkpoint the app still works in "choose the design manually" mode.

Configuration (all optional except the two secrets) is described in `backend/.env.example`:
`SECRET_KEY`, `JWT_SECRET_KEY`, `MONGO_URI`, `CORS_ORIGINS`, `GOOGLE_CLIENT_ID` (enables Google sign-in), `RESEARCHER_EMAILS` (who may open the researcher dashboard).

## Tests

```powershell
cd backend;  venv\Scripts\python -m unittest discover -s tests -t .      # backend
cd frontend; npm test                                                    # frontend (vitest)
cd frontend; npm run lint                                                # ESLint, zero warnings allowed
cd frontend; npm run build                                               # production build
# repository root:
$env:PYTHONPATH="."; backend\venv\Scripts\python -m unittest discover -s ai_training/tests   # AI pipeline
cd frontend; npm run e2e                                                 # real browser + backend + MongoDB
```

Details, current counts and the E2E set-up are in [docs/TESTING.md](docs/TESTING.md).

## Repository map

| Path | Contents |
|---|---|
| `backend/app/ai/` | classifier inference (`multitask_classifier.py`), legacy CV fallback |
| `backend/app/logic/` | feature schema (scope), measurement schema, `drafting/` engine (blocks, transformations, seam allowance, validation), fabric recommendation, nesting, PDF |
| `backend/app/routes/`, `models/` | REST API and MongoDB models |
| `backend/tools/` | `generate_evidence.py` (pattern / nesting / PDF evidence), `verify_pdf.py` (digital check of a produced PDF: A4, 5 cm square), `orphan_report.py` (read-only database reference report), `reset_password.py` (operator password reset) |
| `frontend/src/` | React wizard, pattern preview, library, dashboards; `e2e/` Playwright test |
| `ai_training/` | dataset pipeline, training, evaluation, dataset audit (`scripts/v2/audit_datasets.py`), acceptance gate fixed before training (`config/m42_acceptance.json`), label review screen (`tools/review_labels.py`) |
| `docs/` | API, architecture, pattern engine, AI evidence, testing, limitations and claims |

## Documentation

[Current status](docs/CURRENT_PROJECT_STATUS.md) · [AI data audit and acceptance targets](docs/AI_DATA_AUDIT.md) · [Human validation sheets](docs/HUMAN_VALIDATION.md) · [Proposal ↔ implementation](docs/THESIS_RECONCILIATION.md) · [Architecture](docs/ARCHITECTURE.md) · [Pattern engine](docs/PATTERN_ENGINE.md) · [API](docs/API.md) · [AI evidence](docs/AI_EVIDENCE.md) · [Testing](docs/TESTING.md) · [Limitations and thesis-safe claims](docs/LIMITATIONS_AND_CLAIMS.md) · [Future 15-class model (planned)](docs/FUTURE_15_CLASS_MODEL.md) · [AI development history](docs/ai_history/)
