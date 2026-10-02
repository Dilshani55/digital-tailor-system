# REST API

Base URL (development): `http://127.0.0.1:5000/api`. All bodies are JSON except the image upload (multipart).
Protected routes need `Authorization: Bearer <token>` (token from login, valid 24 h).

## Errors (every route)

Errors are always JSON and never contain stack traces or file paths:

```json
{ "error": "Plain-language message", "error_code": "MACHINE_READABLE_CODE", "field_errors": { "bust_cm": [{ "code": "OUT_OF_RANGE", "message": "…" }] } }
```

| Status | Meaning |
|---|---|
| 400 | Invalid or missing input (`field_errors` lists each bad field) |
| 401 / 403 | Not signed in / not your data |
| 404 | Item not found |
| 409 | The confirmed design sent by the client differs from the saved one (`CONFIRMED_DESIGN_MISMATCH`) |
| 413 | Upload larger than 16 MB |
| 422 | Valid request that cannot be processed: unsupported design (`UNSUPPORTED_DESIGN`), contradictory garment length (`DESIGN_MEASUREMENT_CONFLICT`), missing measurements the design needs (`MEASUREMENTS_INCOMPLETE`), measurements that cannot be drafted into a valid block (`MEASUREMENTS_NOT_DRAFTABLE`), failed pattern validation, a piece that does not fit the fabric (`PIECE_DOES_NOT_FIT`) |
| 503 | Database unavailable (`DATABASE_UNAVAILABLE`), AI model unavailable (`MODEL_UNAVAILABLE`) or Google sign-in not configured |
| 500 | Unexpected server error (generic message only; details go to the server log) |

## Auth `/api/auth`

| Method & path | Body | Result |
|---|---|---|
| `POST /register` | `full_name`, `email`, `password` (≥ 8 characters) | 201, `user_id` |
| `POST /login` | `email`, `password` | 200, `token`, `user` |
| `POST /google-login` | `credential` (Google ID token) | 200 `token`, `user`. **Verified with Google** (audience must equal `GOOGLE_CLIENT_ID`, `email_verified`). 503 if `GOOGLE_CLIENT_ID` is not set. |
| `GET /profile` 🔒 | – | current user |

## Measurements `/api/measurements` 🔒

* `GET /schema` – the 16 fields (each with its group, kind `measurement` / `design`, the view of the body guide, how to measure and a common mistake), canonical unit (cm), the inch factor (2.54) and the requirement rules (which fields a design needs; `backend/config/measurement_requirements.json`).
* `POST /` – create a customer profile. Send numbers with a `unit` (`"cm"` default or `"in"`) and optionally `units` ({field: unit}) when values were typed in different units; inches are converted once, exactly (× 2.54). Every value must be a finite number > 0 (decimals fine); there are **no plausibility ranges** and values are never clamped. With `design` (the confirmed {garment_type, neckline_type, sleeve_length, sleeve_style}) exactly the measurements that design needs are required (e.g. sleeveless: no sleeve fields; a bell sleeve: no sleeve end; design values: never); without `design` nothing is required. Optional: `client_name`, `fabric_type` (`woven`/`knit`), `fit_preference` (`close`/`standard`/`loose` = Close / Regular / Relaxed fit). Response includes `measurement_id`, `entered_fields` and `warnings` – `[{field, code, message}]` for values that look like a typing or unit mistake (`UNUSUAL_VALUE`, `CHECK_PROPORTION`); a warning never blocks saving.
* `GET /`, `GET /{id}`, `PUT /{id}` (partial update, merged and re-validated; `clear: [design keys]` empties design values again so that the calculated value is used – a body measurement cannot be cleared, `INVALID_CLEAR`), `DELETE /{id}`.

Body measurements (cm): `bust_cm, waist_cm, hip_cm, shoulder_width_cm (shoulder tip to shoulder tip), back_waist_length_cm, shoulder_to_bust_cm, waist_to_hip_cm, garment_length_cm, bicep_cm (upper arm), sleeve_cm (shoulder tip to where the sleeve ends), sleeve_end_cm (around the arm where the sleeve ends)`.
Design values (optional; empty = calculated by the drafting method): `neck_width_cm, front_neck_depth_cm, back_neck_depth_cm, armhole_depth_cm, bust_point_distance_cm`.
Fields of earlier versions (`neck_cm, height_cm, shoulder_cm, across_back_cm, wrist_cm`) are still stored and returned but never required and not used for drafting; for a long sleeve an old `wrist_cm` stands in for a missing `sleeve_end_cm`. Details: [measurement-guide.md](measurement-guide.md).

## Images and AI `/api/images` 🔒

* `POST /upload` – the camera's EXIF rotation is applied before the photo is stored and analysed.
* `POST /upload` – multipart field `image` (JPG/PNG/WEBP, ≤ 16 MB). The **content** is decoded and checked; the stored name is random. → `image_id`.
* `POST /{image_id}/analyse` – finds the garment with the detector, then asks the four garment models (garment type: MobileNetV3-Large; neckline, sleeve length, sleeve style: YOLOv8n-cls) → `garment_attributes.predictions.{garment_type,neckline_type,sleeve_length,sleeve_style}`, each with the **genuine** `label`, `confidence`, `top_3`, `threshold_used`, plus a fingerprint of the model files. Every feature carries `uncertain` (true when the score is below that model's validation-chosen threshold, or the model has no threshold): the UI shows the guess but does **not** pre-select it. For a sleeveless garment `sleeve_style` is `none` with `derived_from: "sleeve_length"` (the sleeve-design model is not asked). A feature whose model file is missing is left out (`heads_without_a_model`). `garment_region` says whether the garment crop or the whole photo was analysed. Nothing is auto-confirmed.
  Failures are reported honestly and nothing is stored: model checkpoint missing/corrupt → `503 MODEL_UNAVAILABLE` ("choose the design manually"); unreadable photo → `422 IMAGE_NOT_ANALYSABLE`. The measured inference time is stored (`analysis_time_sec`).
* `GET /model-status` – `{available, complete, model_type, model_version, checkpoint_sha256, models: {feature: {available, architecture, sha256, answers_automatically}}}` after really loading the model files, or `{available: false, message}` (no file paths).
* `POST /{image_id}/confirm-attributes` – body `{garment_type, neckline_type, sleeve_length, sleeve_style}`, each one of the selectable classes; any other value (for example `crop-top`, `off-shoulder`, `boat-neck`) is rejected with `400 INVALID_DESIGN_ATTRIBUTES`. Stores the **user-confirmed** design (`design_spec`, with provenance ML-confirmed / user-corrected / manual). Only this confirmed design reaches the pattern engine.
* `GET /design-schema` – the selectable classes (2 / 4 / 3 / 4) with per-value drafting support and the project scope matrix.
* `GET /`, `GET /{id}`, `DELETE /{id}`, `GET /view/{filename}`.

### Selectable classes

garment_type: blouse, t-shirt · neckline_type: round-neck, v-neck, square-neck, collared-neck · sleeve_length: sleeveless, short-sleeve, long-sleeve · sleeve_style: none (only with sleeveless), regular-sleeve, puff-sleeve, bell-sleeve. `collared-neck` can be selected and stored but the pattern engine cannot draft it (`422 UNSUPPORTED_DESIGN` at generation). One file defines all of this for the backend and the frontend: `backend/config/garment_scope.json`.

### Supported scope (what can actually be drafted: 25 of the 96 combinations)

| Garment | Necklines | Sleeve length → sleeve styles |
|---|---|---|
| blouse | round, v, square | sleeveless → none · short → regular, puff, bell · long → regular, puff, bell |
| t-shirt | round, v | short → regular · long → regular |

Anything else returns `422 UNSUPPORTED_DESIGN` with an explanation; the system never substitutes another design.

## Patterns `/api/patterns` 🔒

* `POST /generate` – body `{measurement_id, image_id | "manual", fabric_id, confirmed_attributes?, display_unit?: "cm"|"in", seam_allowances?: {edge kind: cm}}`. `seam_allowances` (a research setting) replaces single allowances – edge kinds `shoulder, side, armhole, neckline, sleeve_seam, sleeve_hem, hem, strip`; an invalid value answers `422 INVALID_SEAM_ALLOWANCE`. `display_unit` is stored with the pattern and used by the PDF; geometry is always in cm. The selected fabric must be compatible with the garment (`422 FABRIC_NOT_COMPATIBLE`) and its construction (woven/knit) decides the drafting block. Optional `project_name` (≤ 80 characters) is stored and printed in the PDF. Drafts the base block, applies the confirmed design, adds seam allowances and validates. Returns `pattern_id`, `base_block`, `final_pattern` (transformations), `pattern_pieces` (per piece: `segments` with Bézier control points, `outline` = sewing line, `cutting_line`, `notches`, `darts`, `grain_line`, `fold_line`, `cut_count`, `cut_on_fold`, `seam_allowances`, `units: "cm"`), `validation` (every check) and `validation_passed`. A pattern that fails validation is **not created** (422).
  Also returned, and stored with the pattern: `drafting_method` (name, source, note), `units`, `ease` (what was added to the body for the chosen fit), `derived_measurements`, `why_this_size` (every calculated value: `{id, label, value_cm, formula, source, piece}`), `armhole_lengths` (`front_armhole_curve_cm`, `back_armhole_curve_cm`, `total_armhole_cm`), `sleeve_cap` (`bodice_armhole_seam_cm`, `sleeve_cap_seam_cm`, `difference_cm`, `allowed_cm`, `status`: `PASS` / `REVIEW` / `NOT APPLICABLE`, `note`), `seam_allowances_cm`, and `warnings` (measurement warnings and `SLEEVE_CAP_REVIEW`). Each piece has `dimensions` – the labelled lengths of the block overview.
* `GET /` – every saved pattern of the user. This one list is what the dashboard, the customers page and the pattern library count and show. Each item has `measurement_id` and `customer_name` (both `null` if the customer profile was deleted), the confirmed `neckline_type` / `sleeve_length` / `sleeve_style`, `validation_passed`, and `exports` – its PDFs, newest first, each `{export_id, filename, exported_at, file_available}`. An empty `exports` means "PDF pending": the pattern is still listed.
* `GET /{id}` – full saved pattern (geometry, validation, estimate, PDFs) with the stored `drafting_method`, `why_this_size`, `armhole_lengths`, `sleeve_cap`, `ease`, `seam_allowances_cm` and `warnings` (`null` for a pattern saved before these existed – they are not recalculated). The measured drafting time is stored as `generation_time_sec`.
* `DELETE /{id}` – deletes the saved pattern **and its PDFs** (records and file). The customer, their measurements and the design photo are kept. Someone else's pattern answers `404 PATTERN_NOT_FOUND`, the same as a missing one.

## Fabric `/api/fabric` 🔒

* `POST /recommend` – **rule-based** recommendation (not machine-learned). Send `{confirmed_attributes: {garment_type, neckline_type, sleeve_length, sleeve_style}, fit_preference}`: every catalogue fabric comes back with `compatible` (the drafting-block rule: T-shirt → knit only, blouse → woven only), `incompatible_reason`, `recommendation_score` with `score_reasons` (each rule and its delta), `warnings` (e.g. sheer → lining needed), `gsm_range` (from the catalogue text), and `recommended` for the 2–4 best compatible fabrics (`recommended_ids`). No price, stock or availability exists or is returned. The legacy feature-string request is still accepted.
* `GET /catalog`, `GET /{fabric_id}` – Cotton Poplin, Linen Blend, Rayon, Cotton Jersey Knit, … (ids are lower-case hyphenated).

## Estimate and PDF `/api/export` 🔒

* `POST /yardage/{pattern_id}` – body `{fabric_width_cm: any width > 0 (the app uses 91.44, 114.3, 152.4), cutting_mode: "auto"|"folded"|"open"}` (defaults 114.3 = 45 in, `auto`). Refused (422) if the pattern failed validation. Returns layout length, exact and recommended purchase length (+3 % shrinkage, +10 cm margin, rounded up to 10 cm), utilisation/waste, `placed_pieces` (polygon positions), `validation_checks` (exact overlap, bounds, fold, grain, quantities), `assumptions`, `mode_comparison`.
* `POST /estimates/{pattern_id}` – fabric requirement for the three standard widths **36" (91.44 cm), 45" (114.3 cm), 60" (152.4 cm)** from the stored validated pieces, body `{selected_width_cm?, cutting_mode?, one_way?}` (`one_way: true` for fabric with a nap or a directional print: no piece is turned). Each row: width in inches and cm, `fits`, `base_layout_length_cm`, `purchasing_allowance_cm`, `recommended_purchase_m` and `recommended_purchase_yd`, `pattern_area_m2` / `pattern_area_yd2`, `purchase_area_m2` / `purchase_area_yd2`, `utilisation_percent`, `waste_percent`, `one_way_fabric`, `placement_order`, `placed_pieces` (layout), `validation_checks`, `warnings`; a width where a piece cannot be placed is `fits: false` with the reason and no numbers. The selected width (default: shortest purchase) becomes the saved estimate used by the PDF; all three rows are stored as `width_estimates`. 422 `PATTERN_VALIDATION_FAILED` for a pattern that failed validation.
* `POST /pdf/{pattern_id}` – body `{part?: "all"|"overview"|"report"|"pattern", unit?: "cm"|"in"}`: `overview` = one page with the real front, back and sleeve drawn side by side at a reduced scale 1:n and their measurements written on them (what the app creates by default; `overview_scale` in the response is n); `report` = the overview plus the measurement report (block pages marked NOT TO SCALE, calculations, fabric table); `pattern` = the 1:1 cutting pattern; `all` = report and cutting pattern (the API's default). Builds the PDF from **stored data only** (validated pieces, measurement snapshot, drafting metadata, customer, design image, AI provenance, 36"/45"/60" estimates); the pattern is not re-drafted. → `export_id`, `pages`.
* `GET /download/{export_id}` – the PDF. `GET /` list. `DELETE /{export_id}` removes **one PDF only**; the pattern is kept (its file is removed with the last PDF record that uses it). A PDF whose pattern no longer exists answers `404 EXPORT_PATTERN_MISSING`.

Records can be deleted independently, so a reference may point at a record that is gone. Routes treat that as "missing" (never a 500). `backend\venv\Scripts\python backend\tools\orphan_report.py` prints a **read-only** report of such records with a dry-run plan; it changes nothing.

## Research `/api/research` 🔒

* `POST /feedback` – `{pattern_id, feedback_score (whole number 1–5), feedback_comment (≤ 2000 chars)}`; only for your own pattern (403 otherwise). Stores the measured analysis and drafting times of that pattern.
* `POST /fabric-comparisons` – evaluation instrument: `{pattern_id, fabric_width_cm: 91.44|114.3|152.4, cutting_mode?: auto|folded|open, traditional_estimate_m: 0.1–20, estimate_source: tailor|manual_calculation|shop_rule_of_thumb|other, estimator_label? (≤ 40, a pseudonym), notes? (≤ 500)}`. The server **recomputes** the system estimate with the real nesting for the same width/mode (the stored pattern is not changed) and stores both numbers. → `system_purchase_m`, `system_layout_length_cm`, `difference_m` (= traditional − system), `relative_difference_percent`. Own patterns only; refused (422) for a pattern that failed validation.
* `GET /fabric-comparisons?pattern_id=` – your own comparisons; `DELETE /fabric-comparisons/{id}`.
* `GET /metrics` (researchers only) – measured values only (fields never measured are `null`), model metrics read from the evaluation file, `fabric_comparison` = descriptive summary of all entered comparisons (n, mean/median/SD of the difference, counts where the system is lower/higher/equal, by source) or `null` when none exist.
* `GET /export/csv`, `GET /export/fabric-comparisons.csv` (researchers only) – pseudonymised research records / comparison rows.
