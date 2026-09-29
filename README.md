# AI-Assisted Digital Tailor System

Final-year research project — **D N M Vitharana (28404)**, BSc (Hons) Software Engineering, NSBM Green University. Supervisor: Mr. Anton Jayakody.

A web system that turns a garment photo and a person's body measurements into a **printable, full-size (1:1) sewing pattern** for women's **blouses, T-shirts and crop-tops**, together with a fabric estimate.

## What it does

```
Garment photo ─► AI suggests the design ─► YOU review and confirm it ─► body measurements (validated)
      ─► fabric & fit ─► parametric pattern drafting (deterministic maths, not AI)
      ─► seam allowances + notches ─► automatic geometry validation
      ─► polygon nesting on 90 / 114 / 150 cm fabric ─► fabric quantity
      ─► printable 1:1 tiled A4 PDF ─► saved in your pattern library
```

* **AI part.** One image classifier (YOLOv8n-cls backbone, four output heads: garment type, neckline, sleeve length, sleeve style). Its answers are only *suggestions*; the user must confirm or correct them, and only the confirmed design reaches the pattern engine. Users choose from 15 active classes (3 / 5 / 3 / 4); if the model predicts something outside them the app says so and asks for manual confirmation — it never swaps in a similar class.
* **Pattern part.** Pure, deterministic geometry (`backend/app/logic/drafting/`). No second AI model invents the pattern. Every constant that is not derived from your measurements is listed in `assumptions.py` and marked as a *project assumption*.
* **Fabric part.** Fabric recommendation is rule-based and explains itself. The fabric quantity comes from laying the real cutting-line polygons on the cloth (Bottom-Left-Fill heuristic).
* **Evaluation part.** A traditional (e.g. tailor's) fabric estimate can be recorded for any saved pattern and compared with the system's estimate for the same fabric width; researchers see a descriptive summary. No study data has been collected yet.

### Supported designs (anything else is rejected with a clear message)

| Garment | Necklines | Sleeves | Construction |
|---|---|---|---|
| Blouse | round, V, square | regular short, regular long | woven bodice |
| T-shirt | round, V | regular short, regular long | knit bodice |
| Crop-top | round, V, square | sleeveless, regular short | woven or knit (chosen by fabric) |

### Honest status

The pattern is **mathematically generated and geometry-validated**. It has **not** been fit-tested on bodies or checked by a professional pattern-maker — make a test garment (muslin) before cutting good fabric. See [docs/LIMITATIONS_AND_CLAIMS.md](docs/LIMITATIONS_AND_CLAIMS.md) for exactly what can and cannot be claimed.

## Quick start (Windows, first time)

Requirements: **Python 3.10+** (developed on 3.14), **Node.js 18+**, **MongoDB** running on `localhost:27017`, and Google Chrome (only for the browser test).

```powershell
# 1. Backend
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt            # add: pip install -r requirements-dev.txt  for the PDF tests
copy .env.example .env                      # then edit .env: set SECRET_KEY and JWT_SECRET_KEY
python run.py                               # API on http://127.0.0.1:5000

# 2. Frontend (second terminal)
cd frontend
npm install
npm run dev                                 # http://localhost:3000
```

The trained classifier is **not stored in Git** (large file). Put the deployed checkpoint at
`backend/app/ai/models/garment_multitask_yolov8_best.pt` and the pretrained backbone at
`backend/app/ai/models/yolov8n-cls.pt`; the checksum of the deployed model is in [docs/AI_EVIDENCE.md](docs/AI_EVIDENCE.md).
Without them the app still works in "choose the design manually" mode.

Configuration (all optional except the two secrets) is described in `backend/.env.example`:
`SECRET_KEY`, `JWT_SECRET_KEY`, `MONGO_URI`, `CORS_ORIGINS`, `GOOGLE_CLIENT_ID` (enables Google sign-in), `RESEARCHER_EMAILS` (who may open the researcher dashboard).

## Tests

```powershell
cd backend;  venv\Scripts\python -m unittest discover -s tests -t .      # backend
cd frontend; npm test                                                    # frontend (vitest)
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
| `backend/tools/` | `generate_evidence.py` – reproducible pattern / nesting / PDF evidence |
| `frontend/src/` | React wizard, pattern preview, library, dashboards; `e2e/` Playwright test |
| `ai_training/` | dataset pipeline, training, evaluation, dataset audit, deployment acceptance gate |
| `docs/` | API, architecture, pattern engine, AI evidence, testing, limitations and claims |

## Documentation

[Current status](docs/CURRENT_PROJECT_STATUS.md) · [Proposal ↔ implementation](docs/THESIS_RECONCILIATION.md) · [Architecture](docs/ARCHITECTURE.md) · [Pattern engine](docs/PATTERN_ENGINE.md) · [API](docs/API.md) · [AI evidence](docs/AI_EVIDENCE.md) · [Testing](docs/TESTING.md) · [Limitations and thesis-safe claims](docs/LIMITATIONS_AND_CLAIMS.md) · [Future 15-class model (planned)](docs/FUTURE_15_CLASS_MODEL.md) · [AI development history](docs/ai_history/)
