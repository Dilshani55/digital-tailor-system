# Milestone log

Each milestone records what changed, the commit and the tests that were actually run.

## Milestone 0 — validated baseline (30 Sep 2026)

* Branch `wip/final-pattern-engine`, HEAD `c49ce5f`, working tree clean; pushed to `origin/wip/final-pattern-engine`
  (was 4 commits ahead). `origin/main` is an ancestor of the branch (34 commits behind, fast-forward possible).
* Production classifier: `backend/app/ai/models/garment_multitask_yolov8_best.pt`,
  SHA-256 `3b69a470ed5d039844056135ad27c700a865b82196ef85dc6a5e9f53c84f0339` (M13, heads 3/10/6/9; the app
  limits choices to the 15 active classes). Backup: `backend/app/ai/models/archive_m13_checkpoint/`.
* API health: isolated backend (port 5055, database `digital_tailor_e2e`) answered `GET /` with 200; MongoDB on
  `localhost:27017`.
* Tests on this HEAD: backend 354 passed · AI pipeline 134 passed · frontend 121 passed · production build OK ·
  real-stack Playwright E2E 6 passed.
* Lint: `npm run lint` cannot run — the repository has no ESLint configuration.
* Hardware: CPU only (22 logical cores, 16 GB RAM, Intel Arc graphics without CUDA).

## Milestone 1 — scope and taxonomy

* One canonical file `config/garment_scope.json`: the 15 selectable classes (3/5/3/4, fixed order), their
  drafting support, and the draftable combinations *including which sleeve styles each sleeve length allows*.
  `backend/app/logic/feature_schema.py` loads it; `frontend/src/utils/designSchema.js` imports it (no hand-copied list).
* Review screen: options that cannot be drafted with the other selections are disabled with the reason; an
  AI prediction that cannot be drafted is shown but not pre-selected ("AI suggested …, but this pattern cannot be
  drafted"); confirm is blocked until the design is draftable; each low-confidence head shows
  "Low confidence — please confirm this feature".
* Removed from the customer app: Research Metrics page and navigation entry, traditional-vs-system fabric
  comparison UI. The researcher-only backend API and the internal docs remain.
* Tests: backend 355 passed · frontend 118 passed (6 tests of the removed UI replaced by 2 removal tests and 3
  scope tests) · E2E 6 passed · build OK.

## Milestone 2 — AI data audit

* Re-ran `build_15class_manifests.py` (identical counts to the earlier report; verdict NOT_READY) and a new
  per-class audit against the raw Fashionpedia annotations: see [AI_DATA_AUDIT.md](AI_DATA_AUDIT.md).
* Weak-class recovery: explicit puff/bell/square/off-shoulder evidence on tops is already used; 15 new explicit
  sleeveless candidates listed (not enough for the targets); collared-neck/regular-sleeve need human review.
* 45 review contact sheets + CSVs generated from the 1,413-item queue (local data).
* Tests: AI pipeline 139 passed.

## Milestone 3 — classifier decision: baseline retained

* No training run: 5 classes have no locked-benchmark example and 3 have no trusted validation/test example,
  so the acceptance gate cannot be passed honestly; earlier experiments on the same data failed the gate.
* Production checkpoint unchanged (SHA-256 `3b69a470…0339`, backup identical).

## Milestone 4 — pattern engine: puff and bell sleeves

* New transformations with real geometry (`drafting/sleeve.py`): puff (gathered cap, band for short sleeves) and
  bell (fitted cap, flared curved hem); new constants registered in `assumptions.py`; validation adds
  "puff cap gathering vs armhole", "puff cap flat below notches" and "bell sleeve flares"; sleeve band is a
  required piece for short puff sleeves.
* Scope (config/garment_scope.json) now equals the specified minimum: blouse short/long × regular/puff/bell,
  T-shirt short/long × regular, crop-top sleeveless/none and short × regular/puff/bell. Collared and off-shoulder
  remain AI-only (no geometry).
* Every scope combination drafts and validates for three body sizes (woven and knit where applicable).
* Tests: backend 360 passed (+5 new, 7 adapted from "puff/bell unsupported" to still-unsupported designs) ·
  frontend 118 passed (3 adapted).

## Milestone 5 — fabric recommendation and 36" / 45" / 60" requirement

* `logic/fabric_selection.py`: rule-based, design-aware recommendation (compatibility by drafting block, sleeve
  style, neckline, fit, weight, drape level, opacity; every score explained); 2–4 recommended, other compatible
  fabrics selectable, incompatible ones listed with the reason. Generation rejects an incompatible fabric and
  drafts with the selected fabric's construction.
* Standard widths are now 36/45/60 inches (91.44 / 114.3 / 152.4 cm); `POST /api/export/estimates/{id}` returns all
  three from the stored pieces (base length, allowance, purchase, utilisation, waste, layout, "does not fit" rows).
* Wizard: fabric step shows recommended / other compatible / not suitable; estimate step shows the width
  comparison table and the selected layout.
* Real-stack E2E (blouse, medium): 36" 1.6 m, 45" 1.1 m, 60" 0.9 m.
* Tests: backend 371 passed · frontend 120 passed · E2E 6 passed.

## Milestone 6 — complete printable customer PDF

* The PDF is built from stored data only; the re-draft at PDF time was removed. Drafting metadata (block, ease,
  construction notes) and an optional project name are saved with the pattern at generation.
* New pages: project summary (customer, contact, project, pattern ID, dates, embedded design image, confirmed
  features with AI prediction/confidence and corrections, fabric, fit/ease, width summary), printing page with the
  5 cm square, measurement page (used cm + as entered + DERIVED/ASSUMPTION drafting values), pieces + notes,
  36"/45"/60" requirement with three layouts; piece labels add cut size, pattern ID and key points; footer carries
  page, pattern ID, customer, units/scale, timestamp.
* Real-stack E2E: the downloaded PDF (19 pages) contains the customer, the real M13 provenance, the embedded upload
  and the three widths.
* Tests: backend 371 passed (PDF: never re-drafted, complete content incl. embedded image, entered values, footer).
