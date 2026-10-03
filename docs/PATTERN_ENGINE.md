# Pattern engine

Deterministic and parametric: the same measurements and design always give the same pattern. Nothing here is machine-learned. Code: `backend/app/logic/drafting/` (facade: `parametric_engine.py`, engine version 3.0). Geometry is calculated in **centimetres**; inches are a display unit (1 in = 2.54 cm exactly). x grows to the right from the centre line, y grows **downwards** from the shoulder line.

```
validated measurements ─► ease ─► drafting values ─► base block (front, back, sleeve) ─► validation
                                                               │
        confirmed design (garment, neckline, sleeve length/style)
                                                               ▼
        transformations (neckline, hem, sleeve) ─► seam allowance + notches ─► validation ─► final pattern
```

Related documents: the drafting rules and their source – [pattern-drafting-method.md](pattern-drafting-method.md); the measurements – [measurement-guide.md](measurement-guide.md); the fabric requirement – [fabric-calculation.md](fabric-calculation.md).

## Status of the method (read this before citing it)

The bodice and the sleeve follow one published draft: "Drafting the adult's bodice and sleeve pattern" in *Pattern Making and Grading*, study material for B.Sc. Fashion Technology, Kamaraj College (pp. 3–6; read on 2 Oct 2026). **It is not Winifred Aldrich's block**: Aldrich's steps could not be read and verified, so the name is not used. Every constant is registered in `assumptions.py` with its kind – `method` (a rule of the source), `figure` (read from the source's drawing), `design` (a style value that can be replaced), `ease`, `seam`, or `extension` (a project rule where the source gives none: hip-length garments, knit T-shirts, the check against the upper arm). **No pattern has been fit-tested**: validation here is geometric only.

## Which designs are drafted

Of the 72 combinations the form can express (2 garments x 4 necklines x 3 sleeve lengths x 3 sleeve styles), **19 are drafted**: a blouse with a round, V or square neck, sleeveless or with short / long regular or puff sleeves (15), and a T-shirt with a round or V neck and short / long regular sleeves (4). The scope is one file, `backend/config/garment_scope.json`, read by the API, the UI and the engine. The bell sleeve was removed from the scope on 3 Oct 2026. The other 53 (a collared neck, a sleeveless or puff-sleeve T-shirt, ...) are **refused with the reason** - by the form, by the API (`422 UNSUPPORTED_DESIGN`) and by the engine itself. Nothing is ever replaced by a similar design. Stretch-knit (negative ease) is refused too. `backend/tests/test_design_matrix.py` drafts all 19 for three body sizes and checks pieces, quantities, ease, darts, sleeve cap against armhole, sleeve length, seam allowance, grainline, fold line and notches, then lays each out on 36", 45" and 60" fabric.

## Stages

| Stage | File | What it does |
|---|---|---|
| Measurement schema | `logic/measurement_schema.py` + `backend/config/measurement_requirements.json` | 16 fields (11 body measurements, 5 optional design values), canonical cm, exact cm/in conversion per field, values must be finite and > 0, the design decides which are required (shared with the frontend), no defaults; soft warnings for unusual values |
| Block choice | `logic/block_selection.py` | blouse → woven bodice (darts); T-shirt → knit bodice (neckband, no darts) |
| Ease | `drafting/ease.py`, presets in `assumptions.py` | body + ease = garment size, for Close / Regular / Relaxed fit; woven and knit differ. Negative-ease stretch-knit is **rejected**, not approximated |
| Drafting values | `drafting/drafting_values.py` | every width, depth and level of the draft with the formula that produced it (`explain()` → "Why this size?"); infeasible combinations are rejected with field errors |
| Base block | `drafting/bodice.py`, `sleeve.py`, `base_block.py` | **front and back drafted separately** (front wider, lower narrower neck, deeper armhole curve, waist dart and side-seam bust dart; back with one waist dart); sleeve cap with different front and back curves, fitted to the measured armhole |
| Transformations | `drafting/transformations.py` | round, square and V necks; hem from the measured garment length (it must reach the waist line); sleeveless (armhole facings); short and long sleeves exactly the measured sleeve length, narrowing to the measured sleeve end; puff sleeve (spread to 1.5×, crown raised, gathered between the notches); knit neckband; fish darts below the waist |
| Seam allowance | `drafting/seam_allowance.py` | real offset geometry, one allowance per kind of edge, + notches |
| Validation | `drafting/validation.py` | see below |

## Armhole and sleeve cap

The engine measures the drafted curves (front armhole, back armhole, total; front and back cap) and reports them in `armhole_lengths` and `sleeve_cap`. The cap must exceed the armhole by an amount inside the accepted ease range (woven 0.5–4.5 cm, knit 0–3 cm, puff 4–30 cm of gathers). The method's cap height is kept when it fits; otherwise only the cap height is changed. Status: **PASS**, or **REVIEW** when the height changed by more than a quarter. A sleeve that cannot fit is an error with advice.

## Seam allowance

The drafted outline is the **sewing line**. The **cutting line** is that outline offset outward edge by edge. Ease changes the garment size; seam allowance does not.

| Edge | Woven | Knit |
|---|---|---|
| shoulder / side / sleeve seam | 1.5 cm | 1.0 cm |
| armhole and sleeve cap / neckline | 1.0 cm | 1.0 cm |
| hem / sleeve hem | 2.5 cm | 2.0 cm |
| neckband / facing strips | 1.0 cm | 0.7 cm |
| fold edge | 0 | 0 |

Single values can be replaced per request (`seam_allowances` in `POST /api/patterns/generate`): the sewing line stays, the cutting line moves. Adjacent offset edges are joined by mitres (limit 2× the allowance, otherwise bevelled); where a concave curve is tighter than the allowance the reversed offset edges are removed, so the cutting line never loops.

Each final piece carries: `outline` (sewing line), `cutting_line`, `segments` (curve control points), `dimensions` (the labelled lengths drawn on the block overview, each linked to its calculation), `notches` (armhole balance marks: back one, front two; the sleeve's marks at the same seam distances), `darts`, `grain_line`, `fold_line`, `cut_count`, `cut_on_fold`, `seam_allowances`, `edge_allowances`, `side`, `units`.

## Validation (a failure stops generation — no pattern is saved, no estimate, no PDF)

Per piece: finite coordinates · connected and closed outline · no self-intersection (sewing **and** cutting line) · positive/plausible size · required control points · darts inside the piece, symmetric, legs on the edge · cutting line encloses the sewing line · **measured** allowance never narrower than specified · grainline present · fold line when cut on fold · integer cut quantity ≥ 1 · piece name · notches on the sewing line.

Whole pattern: required pieces exist for the design · front/back shoulder seams equal · front/back side seams equal (the front's bust dart closed) · waist adds up to body + ease · **finished bust = body bust + ease** · sleeve cap against armhole inside the accepted range · bodice and sleeve notches at the same seam distance · sleeve hem below the cap · bust point inside the front piece · transformations recorded. Six sample designs pass 76–99 checks each (`backend/tools/generate_evidence.py`).

Not validated (limits of the method): how the garment fits a real body, drape, stretch behaviour of real knits, construction sequence.

## Nesting and fabric estimate (`logic/nesting_algorithm.py`)

Full description and a worked example: [fabric-calculation.md](fabric-calculation.md).

* Uses the **cutting-line polygons** (seam allowance included), rasterised on a 0.5 cm grid; Bottom-Left-Fill; three placing orders are tried and the shortest layout is kept; ≥ ~0.5 cm between pieces.
* Length of the cloth is the grain. Only 0° and 180° orientations are tried; on **one-way fabric** (nap, directional print) no piece is turned. Cut-on-fold pieces are pinned to the fold edge and never rotated.
* Standard widths: **36" = 91.44 cm, 45" = 114.3 cm, 60" = 152.4 cm**; all three are computed from the same stored pieces.
* *Folded* mode: usable width = bolt/2; *open* mode: full width, fold pieces mirrored to full size. `auto` computes both and keeps the shorter purchase.
* Exact polygon checks on the result: no overlap, inside the cloth, fold alignment, grain preserved, cut quantities met. Any piece wider than the cloth → `PIECE_DOES_NOT_FIT` (never dropped silently).
* Purchase length = layout + 3 % shrinkage + 10 cm cutting margin, rounded up to 10 cm. Reported in metres and yards, with the pattern area and the bought area in m² and yd², fabric use and waste.
* It is a **greedy heuristic** (an upper bound on fabric use, not a proven optimum). The widest fabric is not presented as the best one.

## Printable PDF (`logic/pdf_generator.py`)

Built **only from stored data** — the validated pieces saved with the pattern, the measurement snapshot and the drafting information saved at generation time; the pattern is never re-drafted for the PDF. It has two parts, which can also be exported separately (`part`: `all`, `overview`, `report`, `pattern`). The app creates the one-page **overview** unless the user chooses another part; the real-size pattern is never the default.

**Pattern overview (reduced scale, one page)** – the real front, back and sleeve outlines side by side at the same scale 1:n (the largest of 1:4 … 1:20 that fits; 1:7 for a medium blouse), so 1 cm on the page is n cm of the pattern when printed at 100 %. The main dimensions are written on the blocks with this customer's numbers and, for the widths, the calculation; shorter values (darts, curve lengths) are listed under each block. The page also shows the customer and design, the sleeve-cap check, the fabric to buy and the measurements entered. It is for reading, not a cutting template, and says so.

**Report (not to scale)** – starts with the overview page, then:

1. **Project summary** – customer, design/project name, pattern ID, date, the design image, the confirmed garment type / neckline / sleeve length / sleeve style with the AI prediction and whether the user confirmed or corrected it, fabric, fit and ease, the drafting method, and the 36"/45"/60" fabric summary.
2. **Measurements** – every value used, in the chosen unit and the other one, and the value exactly as entered.
3. **FRONT, BACK and SLEEVE block overviews**, each marked **NOT TO SCALE**: the block with numbered dimension lines and the list of those dimensions; the sleeve page carries the armhole / sleeve-cap report (PASS or REVIEW).
4. **"Why this size?"** – every calculated value with its formula and where the rule comes from.
5. **Pieces** – cut quantity, fold, per-edge seam allowances, cut size; sewing notes.
6. **Fabric requirement** for 36", 45" and 60": layout length, length to buy (m and yd), pattern area and bought area (m² and yd²), waste, fabric use, and the layout drawing of each width (not to scale).

**Cutting pattern (1:1)** - still produced when the API is asked for `part: "pattern"` or `"all"`, but **the app does not offer it** (decision of 4 Oct 2026: the app's PDF is drawn at a reduced scale only; it is not a real-size cutting template).

7. **Printing instructions** (100 % / Actual size, never fit to page) and a **5 cm calibration square**.
8. **The pattern at true size** on A4 tiles (printable area 19.0 × 27.7 cm, 1 cm overlap, crop marks, tile labels A1, A2 …). Each piece: cutting line, dashed sewing line, grainline, fold line, darts, notches, name, cut quantity, seam allowance, pattern ID. The calibration square is also on the pattern sheet.

Footer on every page: page x of N, pattern ID, customer, units/scale, creation time. Scale is verified in tests by reading the PDF's vector geometry (the calibration square is 141.73 pt), and `backend/tools/verify_pdf.py` checks any produced file.
