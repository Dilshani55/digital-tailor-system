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
