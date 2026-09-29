# Pattern engine

Deterministic and parametric: the same measurements and design always give the same pattern. Nothing here is machine-learned. Code: `backend/app/logic/drafting/` (facade: `parametric_engine.py`). Units are **centimetres**; x grows to the right from the centre line, y grows **downwards** from the neck/shoulder-point level.

```
validated measurements ─► ease profile ─► drafting values ─► base block ─► validation
                                                               │
        confirmed design (garment, neckline, sleeve length/style)
                                                               ▼
        transformations (neckline, hem, sleeve) ─► seam allowance + notches ─► validation ─► final pattern
```

## Status of the method (read this before citing it)

The structure follows conventional metric bodice/sleeve drafting (fitted bodice with waist darts, a sleeve cap constructed to fit the armhole, ease added to body measurements). **No equation has been traced to, or verified against, Winifred Aldrich's *Metric Pattern Cutting*** — the book is not in this repository — so the code does **not** call itself Aldrich-based. Every constant that is not derived from the person's measurements is registered in `assumptions.py` as a `project_assumption` (about 25 values, e.g. shoulder slope 18°, back-neck depth 2 cm, waist-to-hip 20 cm, ease values). Those assumptions have **not** been validated by fitting trials.

## Stages

| Stage | File | What it does |
|---|---|---|
| Measurement schema | `logic/measurement_schema.py` | 13 measurements, canonical cm, cm/in conversion (2.54), plausible ranges, cross-field rules, no defaults |
| Block choice | `logic/block_selection.py` | blouse → woven; T-shirt → knit; crop-top → woven or knit by fabric |
| Ease | `drafting/ease.py`, `logic/ease_rules.py` | body + ease = garment size. Woven bust/waist/hip +10/+8/+10; knit +6/+4/+6; fit delta close −2, loose +3. Negative-ease stretch-knit is **rejected**, not approximated |
| Drafting values | `drafting/drafting_values.py` | quarter widths `(measurement + ease)/4`, neck half-width `neck/6`, waist level `back-neck depth + back waist length`, suppression `q_bust − q_waist`; infeasible combinations are rejected with field errors |
| Base block | `drafting/bodice.py`, `sleeve.py`, `base_block.py` | front/back half bodices (Bézier armhole, side seam through waist and hip, waist darts for woven), set-in sleeve whose **cap height is solved** by bisection so that cap seam = armhole seam + target cap ease |
| Transformations | `drafting/transformations.py` | round neck (curve), square neck (straight edges), V neck (to a centre-front point); hem from the measured garment length with the rule *crop hem ≥ 2 cm above the waist, blouse/T-shirt hem ≥ waist* (a contradiction is an error); sleeveless (armhole facings), short 40 %, long 100 % of the full-arm length; knit neckband; fish darts for long woven garments |
| Seam allowance | `drafting/seam_allowance.py` | **real offset geometry** (below) + notches |
| Validation | `drafting/validation.py` | see below |

## Seam allowance

The drafted outline is the **sewing line**. The **cutting line** is that outline offset outward edge by edge:

| Edge | Woven | Knit |
|---|---|---|
| side / shoulder / armhole / sleeve seams | 1.5 cm | 1.0 cm |
| neckline | 1.0 cm | 1.0 cm |
| hem | 2.5 cm | 2.0 cm |
| neckband / facing strips | 1.0 cm | 0.7 cm |
| fold edge | 0 | 0 |

Adjacent offset edges are joined by mitres (limit 2× the allowance, otherwise bevelled). Where a concave curve is tighter than the allowance (the back-neck point) the reversed offset edges are removed — the standard offset-curve clean-up — so the cutting line never loops. The values are project sewing-practice choices, not measured quantities.

Each final piece carries: `outline` (sewing line), `cutting_line`, `segments` (Bézier control points), `notches` (armhole balance marks: front 1, back 2; waist; sleeve crown, front 1, back 2), `darts`, `grain_line`, `fold_line`, `cut_count`, `cut_on_fold`, `seam_allowances`, `side` (front/back), `units`.

## Validation (a failure stops generation — no pattern is saved, no estimate, no PDF)

Per piece: finite coordinates · connected and closed outline · no self-intersection (sewing **and** cutting line) · positive/plausible size · required control points · darts inside the piece, symmetric, legs on the edge · cutting line encloses the sewing line · **measured** allowance never narrower than specified (≥ 85 % of edges exactly at the specified value) · grainline present · fold line when cut on fold · integer cut quantity ≥ 1 · piece name · notches lie on the sewing line and are present (front ≥ 1, back ≥ 2, sleeve ≥ 3).

Whole pattern: required pieces exist for the design (front, back, sleeve or armhole facing, neckband for a T-shirt) · front/back shoulder seams equal (±0.05 cm) · front/back side seams equal · waist circumference adds up to the eased waist · **finished bust = body bust + ease** · sleeve cap vs armhole ease within 0–5 cm and equal to the solved target · sleeve hem below the cap · bust point inside the front piece · transformations recorded.

Not validated (limits of the method): how the garment fits a real body, drape, stretch behaviour of real knits, construction sequence.

## Nesting and fabric estimate (`logic/nesting_algorithm.py`)

* Uses the **cutting-line polygons** (seam allowance included), rasterised on a 0.5 cm grid; Bottom-Left-Fill in descending area order; ≥ ~0.5 cm between pieces.
* Length of the cloth is the y-axis (grain). Only 0° and 180° orientations are tried — a 90° turn would break the grain. Cut-on-fold pieces are pinned to the fold edge and never rotated.
* *Folded* mode: usable width = bolt/2, one placement yields a full fold piece or a pair; *open* mode: full width, fold pieces mirrored to full size. `auto` computes both and keeps the shorter purchase.
* Exact polygon checks on the result: no overlap, inside the cloth, fold alignment, grain preserved, cut quantities met. Any piece wider than the cloth → `PIECE_DOES_NOT_FIT` (never dropped silently).
* Purchase length = layout + 3 % shrinkage + 10 cm cutting margin, rounded up to 10 cm. Utilisation = useful piece area ÷ (bolt width × layout length).
* It is a **greedy heuristic** (an upper bound on fabric use, not a proven optimum) and treats the cloth as plain (no print, nap or pattern matching).

## Printable PDF (`logic/pdf_generator.py`)

Cover with printing instructions (100 % / Actual size) and a **5 cm calibration square**; measurements, fabric estimate and piece table; cutting layout (fit to page, marked not-to-scale); then the pattern at **true 1:1** on A4 tiles (printable area 19.0 × 27.7 cm, 1 cm overlap, corner crop marks, tile labels A1, A2 …, neighbour hints, page numbers; blank tiles omitted). Verified in tests by reading the PDF's vector geometry (a 10 × 15 cm piece is drawn 283.46 × 425.20 pt; the calibration square is 141.73 pt).
