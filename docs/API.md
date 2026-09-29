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
| 422 | Valid request that cannot be processed: unsupported design (`UNSUPPORTED_DESIGN`), contradictory garment length (`DESIGN_MEASUREMENT_CONFLICT`), implausible measurements, failed pattern validation, a piece that does not fit the fabric (`PIECE_DOES_NOT_FIT`) |
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

* `GET /schema` – the 13 fields, canonical unit (cm), plausible ranges and rules.
* `POST /` – create a customer profile. Send numbers in one `unit` (`"cm"` default or `"in"`; inches are converted once with 2.54). Required to save: bust, waist, hip, height; **all 13 are required to draft a pattern**. Optional: `client_name`, `fabric_type` (`woven`/`knit`), `fit_preference` (`close`/`standard`/`loose`). Response includes `measurement_id`, `complete`, `missing_fields`.
* `GET /`, `GET /{id}`, `PUT /{id}` (partial update, merged and re-validated), `DELETE /{id}`.

Fields (cm): `bust_cm, waist_cm, hip_cm, height_cm, neck_cm, shoulder_cm, across_back_cm, back_waist_length_cm, armhole_depth_cm, garment_length_cm, bicep_cm, sleeve_cm (full arm), wrist_cm`.

## Images and AI `/api/images` 🔒

* `POST /upload` – multipart field `image` (JPG/PNG/WEBP, ≤ 16 MB). The **content** is decoded and checked; the stored name is random. → `image_id`.
* `POST /{image_id}/analyse` – runs the deployed 4-head classifier (M13, 3/10/6/9 outputs) → `garment_attributes.predictions.{garment_type,neckline_type,sleeve_length,sleeve_style}` each with the **genuine** `label`, `confidence`, `top_3`, `requires_user_confirmation`, plus model version/checksum. Every head also carries `supported_in_ui` and `suggested_label` (the label if it is one of the 15 selectable classes, otherwise `null` — a prediction is **never** replaced by a similar class). If any head predicted a class outside the selectable list the response has `unsupported_heads` and `unsupported_message` = *"The detected feature is outside the supported pattern scope. Please confirm the design manually."*; nothing is auto-confirmed.
  Failures are reported honestly and nothing is stored: model checkpoint missing/corrupt → `503 MODEL_UNAVAILABLE` ("choose the design manually"); unreadable photo → `422 IMAGE_NOT_ANALYSABLE`. The measured inference time is stored (`analysis_time_sec`).
* `GET /model-status` – `{available: true, model_type, model_version, checkpoint_sha256}` after a real load of the checkpoint, or `{available: false, message}` (no file paths).
* `POST /{image_id}/confirm-attributes` – body `{garment_type, neckline_type, sleeve_length, sleeve_style}`, each one of the 15 selectable classes. A model-only class (for example `boat-neck`, `elbow-length`, `bishop-sleeve`) is rejected with `400 OUTSIDE_SCOPE`. Stores the **user-confirmed** design (`design_spec`, with provenance ML-confirmed / user-corrected / manual). Only this confirmed design reaches the pattern engine.
* `GET /design-schema` – the 15 selectable classes (3 / 5 / 3 / 4) with per-value drafting support, the sizes of the untouched model taxonomy (`model_class_counts` 3/10/6/9) and the project scope matrix.
* `GET /`, `GET /{id}`, `DELETE /{id}`, `GET /view/{filename}`.

### Selectable classes (active taxonomy, 15)

garment_type: blouse, t-shirt, crop-top · neckline_type: round-neck, v-neck, square-neck, collared-neck, off-shoulder · sleeve_length: sleeveless, short-sleeve, long-sleeve · sleeve_style: none, regular-sleeve, puff-sleeve, bell-sleeve. `collared-neck`, `off-shoulder`, `puff-sleeve` and `bell-sleeve` can be selected and stored but the pattern engine cannot draft them yet (`422 UNSUPPORTED_DESIGN` at generation).

### Supported scope (what can actually be drafted)

| Garment | Necklines | Sleeves (style must be `regular-sleeve`; `none` when sleeveless) |
|---|---|---|
| blouse | round, v, square | short, long |
| t-shirt | round, v | short, long |
| crop-top | round, v, square | sleeveless, short |

Anything else returns `422 UNSUPPORTED_DESIGN` with an explanation; the system never substitutes another design.

## Patterns `/api/patterns` 🔒

* `POST /generate` – body `{measurement_id, image_id | "manual", fabric_id, confirmed_attributes?}`. Drafts the base block, applies the confirmed design, adds seam allowances and validates. Returns `pattern_id`, `base_block`, `final_pattern` (transformations), `pattern_pieces` (per piece: `segments` with Bézier control points, `outline` = sewing line, `cutting_line`, `notches`, `darts`, `grain_line`, `fold_line`, `cut_count`, `cut_on_fold`, `seam_allowances`, `units: "cm"`), `validation` (every check) and `validation_passed`. A pattern that fails validation is **not created** (422).
* `GET /` – list (each item has `measurement_id`, the customer profile it was drafted for); `GET /{id}` – full saved pattern (geometry, validation, estimate, PDFs). The measured drafting time is stored as `generation_time_sec`.

## Fabric `/api/fabric` 🔒

* `POST /recommend` – rule-based ranking with explanations for the confirmed design.
* `GET /catalog`, `GET /{fabric_id}` – Cotton Poplin, Linen Blend, Rayon, Cotton Jersey Knit, … (ids are lower-case hyphenated).

## Estimate and PDF `/api/export` 🔒

* `POST /yardage/{pattern_id}` – body `{fabric_width_cm: 90|114|150|any > 0, cutting_mode: "auto"|"folded"|"open"}` (defaults 114, `auto`). Refused (422) if the pattern failed validation. Returns layout length, exact and recommended purchase length (+3 % shrinkage, +10 cm margin, rounded up to 10 cm), utilisation/waste, `placed_pieces` (polygon positions), `validation_checks` (exact overlap, bounds, fold, grain, quantities), `assumptions`, `mode_comparison`.
* `POST /pdf/{pattern_id}` – builds the printable 1:1 A4-tiled PDF from the stored layout width/mode and the measurements the pattern was generated from. → `export_id`, `pages`.
* `GET /download/{export_id}` – the PDF. `GET /` list, `DELETE /{export_id}`.

## Research `/api/research` 🔒

* `POST /feedback` – `{pattern_id, feedback_score (whole number 1–5), feedback_comment (≤ 2000 chars)}`; only for your own pattern (403 otherwise). Stores the measured analysis and drafting times of that pattern.
* `POST /fabric-comparisons` – evaluation instrument: `{pattern_id, fabric_width_cm: 90|114|150, cutting_mode?: auto|folded|open, traditional_estimate_m: 0.1–20, estimate_source: tailor|manual_calculation|shop_rule_of_thumb|other, estimator_label? (≤ 40, a pseudonym), notes? (≤ 500)}`. The server **recomputes** the system estimate with the real nesting for the same width/mode (the stored pattern is not changed) and stores both numbers. → `system_purchase_m`, `system_layout_length_cm`, `difference_m` (= traditional − system), `relative_difference_percent`. Own patterns only; refused (422) for a pattern that failed validation.
* `GET /fabric-comparisons?pattern_id=` – your own comparisons; `DELETE /fabric-comparisons/{id}`.
* `GET /metrics` (researchers only) – measured values only (fields never measured are `null`), model metrics read from the evaluation file, `fabric_comparison` = descriptive summary of all entered comparisons (n, mean/median/SD of the difference, counts where the system is lower/higher/equal, by source) or `null` when none exist.
* `GET /export/csv`, `GET /export/fabric-comparisons.csv` (researchers only) – pseudonymised research records / comparison rows.
