# AI-Assisted Digital Tailor System

Final-year research project — **D N M Vitharana (28404)**, BSc (Hons) Software Engineering, NSBM Green University. Supervisor: Mr. Anton Jayakody.

A web system that turns a garment photo and a person's body measurements into a **sewing pattern with all its measurements** (a PDF drawn at a reduced scale) for women's **blouses and T-shirts**, together with a fabric estimate.

## What it does

```
Garment photo ─► AI suggests the design ─► YOU review and confirm it ─► body measurements (validated)
      ─► fabric & fit ─► parametric pattern drafting (deterministic maths, not AI)
      ─► seam allowances + notches ─► automatic geometry validation
      ─► polygon nesting on 36" / 45" / 60" (91.44 / 114.3 / 152.4 cm) fabric ─► fabric quantity
      ─► PDF: the blocks at a reduced scale with their measurements ─► saved in your pattern library
```

* **AI part.** A garment detector (YOLOv8n) finds the top in the photo, then **four separate models** look at that area: garment type (MobileNetV3-Large: blouse / T-shirt), neckline (YOLOv8n-cls: round / V / square / collared), sleeve length (YOLOv8n-cls: sleeveless / short / long) and sleeve design (YOLOv8n-cls: regular / puff). A suggestion is filled in automatically only when that model's score reaches a threshold chosen on validation photos; otherwise the feature is shown as "please select". The answers are only *suggestions*: the user must confirm or correct them, and only the confirmed design reaches the pattern engine. Measured results and limits: [docs/AI_MODELS.md](docs/AI_MODELS.md).
* **Pattern part.** Pure, deterministic geometry (`backend/app/logic/drafting/`). No second AI model invents the pattern. The front, the back and the sleeve are drafted separately from one published draft (a B.Sc. Fashion Technology course text – **not** Aldrich's block; see [docs/pattern-drafting-method.md](docs/pattern-drafting-method.md)). Every constant is listed in `assumptions.py` with its kind (rule of the source, design value, ease, seam allowance, or project extension), and the pattern shows a "Why this size?" list of every calculation.
* **Measurements.** 11 body measurements and 5 optional design values, in cm or inches, with a front / back body guide and a how-to-measure note for each ([docs/measurement-guide.md](docs/measurement-guide.md)).
* **Fabric part.** Fabric recommendation is rule-based and explains itself. The fabric quantity comes from laying the real cutting-line polygons on the cloth (Bottom-Left-Fill heuristic), reported as a length to buy (m and yd) and as areas (m² and yd²) for each width ([docs/fabric-calculation.md](docs/fabric-calculation.md)).
* **What it is not.** The system does not ask for or predict a tailor's estimate: the fabric requirement is calculated from the real pattern pieces. Study-wide research endpoints exist only as an internal, researcher-only API (not in the app).
* **One source of truth.** The selectable classes, what the engine can draft and the allowed combinations are in [`backend/config/garment_scope.json`](backend/config/garment_scope.json), read by both the backend and the frontend.

### Supported designs (anything else is rejected with a clear message)

| Garment | Necklines | Sleeve length → sleeve styles | Construction |
|---|---|---|---|
| Blouse | round, V, square | sleeveless → none · short → regular, puff · long → regular, puff | woven bodice (darts) |
| T-shirt | round, V | short → regular · long → regular | knit bodice (neckband, no darts) |

That is 19 of the 72 combinations the form can express (the bell sleeve was removed from the scope on 3 Oct 2026). A collared neck is recognised by the AI and can be selected,
but has **no pattern geometry yet**: generation refuses it with the reason. The matrix lives in
[`backend/config/garment_scope.json`](backend/config/garment_scope.json).

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

The trained models are **not stored in Git** (large files; the datasets' licences do not allow redistribution).
They are five local files in `backend/model/`:

| File | Model |
|---|---|
| `garment_detector.pt` | YOLOv8n detector that finds the garment (without it the models look at the whole photo) |
| `garment_mobilenetv3.pt` | garment type |
| `neckline_yolov8.pt` | neckline |
| `sleeve_length_yolov8.pt` | sleeve length |
| `sleeve_design_yolov8.pt` | sleeve design |

`thresholds.json` next to them (tracked in Git) holds the validation-chosen scores. How to train and evaluate them:
[backend/training/README.md](backend/training/README.md). A feature whose model file is missing is simply chosen by
hand; without any model file the app still works in "choose the design manually" mode.

Configuration (all optional except the two secrets) is described in `backend/.env.example`:
`SECRET_KEY`, `JWT_SECRET_KEY`, `MONGO_URI`, `CORS_ORIGINS`, `GOOGLE_CLIENT_ID` (enables Google sign-in), `RESEARCHER_EMAILS` (who may open the researcher dashboard).

## Tests

```powershell
cd backend;  venv\Scripts\python -m unittest discover -s tests -t .      # backend
cd frontend; npm test                                                    # frontend (vitest)
cd frontend; npm run lint                                                # ESLint, zero warnings allowed
cd frontend; npm run build                                               # production build
cd frontend; npm run e2e                                                 # real browser + backend + MongoDB
```

Details, current counts and the E2E set-up are in [docs/TESTING.md](docs/TESTING.md).

## Repository map

| Path | Contents |
|---|---|
| `backend/app/ai/` | garment detector, the four garment models (`garment_models.py`), shared picture preparation |
| `backend/app/logic/` | feature schema (scope), measurement schema, `drafting/` engine (blocks, transformations, seam allowance, validation), fabric recommendation, nesting, PDF |
| `backend/app/routes/`, `models/` | REST API and MongoDB models |
| `backend/config/` | the scope and measurement rules shared by the backend and the frontend |
| `backend/model/` | the trained weights (local files) and `thresholds.json` |
| `backend/training/` | dataset preparation, training and evaluation of the four models |
| `backend/tools/` | `generate_evidence.py` (pattern / nesting / PDF evidence), `verify_pdf.py` (digital check of a produced PDF: A4 pages and sections), `orphan_report.py` (read-only database reference report), `reset_password.py` (operator password reset) |
| `backend/tests/` | backend unit tests |
| `frontend/src/` | React wizard, pattern preview, library, dashboards; `frontend/e2e/` Playwright tests |
| `docs/` | API, architecture, pattern engine, AI models, testing, limitations and claims |

## Documentation

[Current status](docs/CURRENT_PROJECT_STATUS.md) · [AI models: data, results, limits](docs/AI_MODELS.md) · [Training the models](backend/training/README.md) · [Human validation sheets](docs/HUMAN_VALIDATION.md) · [Proposal ↔ implementation](docs/THESIS_RECONCILIATION.md) · [Architecture](docs/ARCHITECTURE.md) · [Pattern engine](docs/PATTERN_ENGINE.md) · [Drafting method](docs/pattern-drafting-method.md) · [Measurement guide](docs/measurement-guide.md) · [Fabric calculation](docs/fabric-calculation.md) · [API](docs/API.md) · [Testing](docs/TESTING.md) · [Limitations and thesis-safe claims](docs/LIMITATIONS_AND_CLAIMS.md)
