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
