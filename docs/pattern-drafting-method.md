# Pattern drafting method

How the system turns measurements into the front bodice, the back bodice and the sleeve. Code:
`backend/app/logic/drafting/`. Every number in this document is in the code's registry
(`drafting/assumptions.py`) and is shown to the user in the pattern's **"Why this size?"** list.

## 1. Which method, and why this one

**Source used:** *Pattern Making and Grading* – study material for B.Sc. Fashion Technology (Semester I,
2022-2023), Kamaraj College, Department of Fashion Technology, section "Drafting the adult's bodice and sleeve
pattern", pp. 3–6.
<https://kamarajwomenscollege.ac.in/wp-content/uploads/Allied-1-Pattern-Making-and-Grading.pdf> (read on
2 October 2026). The source works in inches; the code converts with 1 in = 2.54 cm exactly.

**Why not Aldrich.** The project proposal names Winifred Aldrich's *Metric Pattern Cutting*. That book is not in
the repository and its drafting steps could not be read and checked online, so **nothing in this system is called
Aldrich's block**. Claiming it would be a reference that was never verified.

**One system only.** The bodice and the sleeve come from the same source and the same draft. Rules from other
drafting systems are not mixed in. Where the source is silent, the rule is a **project extension** and is labelled
as such (section 6).

**The handwritten tailoring notes.** The project owner's five pages of notes describe the same kind of draft:
neck width 2¾ in for a 34 in bust (= bust ÷ 12), back neck 1 in deep, shoulder ÷ 2, shoulder sloping 1 in,
bust / waist / hip ÷ 4, a sleeve block, and fabric widths of 36, 45 and 60 in. They were used as a practical
cross-check, not as the reference. Where the source and the notes differ, the source is followed:

| Point | Notes | Source (used) |
|---|---|---|
| Front and back width | the same quarter for both | the front quarter is ½ in wider and the back quarter ½ in narrower |
| Front armhole | same curve as the back | hollowed more than the back (½ in and ⅜ in inside the construction line) |
| Armhole depth | not given as a rule | bust ÷ 4 − 1 in (− ½ in for a bust under 30 in) |
| Shoulder slope 1 in, back neck 1 in | fixed numbers | the same numbers, but kept as **design values** that can be replaced (section 5) |

## 2. Kinds of numbers

Every constant has one of these kinds. The kind is printed next to each row of "Why this size?".

| Kind | Meaning | Example |
|---|---|---|
| measurement | typed by the user | bust 88 cm |
| method | a rule of the source | neck width = bust ÷ 12 |
| figure | read from the source's drawing, not stated in its text | the front is 1 in longer than the back |
| design | a style value with a default; the user may enter another | back neck depth 1 in, shoulder drop 1 in |
| ease | room added to a body measurement | bust + 3½ in (regular fit) |
| seam | seam allowance, outside the sewing line | side seam 1.5 cm |
| extension | a project rule where the source gives none | hip shaping below the waist |

## 3. Formulas (woven blouse)

`B` bust, `W` waist, `H` hip, `S` shoulder to shoulder, `BWL` back neck to waist, all body measurements in cm.
`e` = ease of the chosen fit (section 4). 1 in = 2.54 cm.

### Back bodice

| Value | Formula | Kind |
|---|---|---|
| Back width at the bust line | (B + e_bust) ÷ 4 − 1.27 | method |
| Back neck width (centre to neck point) | B ÷ 12 | method |
| Back neck depth | 2.54 (or the entered value) | design |
| Centre back to shoulder tip | S ÷ 2 | measurement |
| Shoulder drop | 2.54 (`shoulder_drop_cm` in the registry) | design |
| Armhole depth | B ÷ 4 − 2.54; for B < 76.2: B ÷ 4 − 1.27 (or the entered value) | method |
| Waist level | BWL + 1.27 | method |
| Back waist width (finished) | W ÷ 4 − 0.635 + waist ease per quarter | method |
| Back waist dart | 2.54 wide, at the middle of the waist edge, point 2.54 below the underarm line | method |
| Back armhole | straight for the first third from the shoulder tip, then a quarter curve to the underarm | method |

### Front bodice (not a copy of the back)

| Value | Formula | Kind |
|---|---|---|
| Front width at the bust line | (B + e_bust) ÷ 4 + 1.27 | method |
| Front neck width | back neck width − 0.635 | method |
| Front neck depth | B ÷ 12 + 0.635 (or the entered value) | method |
| Front neck point raised | 0.95 for B > 78.74 | method |
| Centre front to shoulder tip | S ÷ 2 − 0.635 | method |
| Front waist width (finished) | W ÷ 4 + 0.635 + waist ease per quarter | method |
| Bust point level | shoulder to bust point + 0.635 | method |
| Bust point from the centre front | half the measured distance between bust points; when not measured: B ÷ 10 | method |
| Front waist dart | 3.81 wide, under the bust point, point 1.9 below it | method |
| Front armhole | hollowed 1.27 at one third and 0.95 at two thirds of the construction line | method |
| Extra front length | 2.54, taken up by a side-seam bust dart (3.81 below the bust level, point 3.81 from the bust point) | figure |

The front is therefore wider than the back, has a lower and narrower neck, a deeper armhole curve and two darts.

### Sleeve (drafted from the same draft, then checked against the armhole)

| Value | Formula | Kind |
|---|---|---|
| Sleeve width at the underarm | 2 × (B ÷ 4 − 3.81) | method |
| Cap height | a quarter of the sleeve width | method |
| Cap curve | through points off the crown–underarm diagonal: back +1.27, +0.635, −0.635; front +1.27, 0, −1.59 (so the front of the cap is scooped more than the back) | method |
| Sleeve length | the entered sleeve length | measurement |
| Notches | back: one; front: two | method |

## 4. Ease is separate from seam allowance

**Ease** changes the size of the garment. **Seam allowance** is only cloth outside the sewing line.

| Fit (woven) | Bust | Waist (per quarter) | Hip | Upper arm |
|---|---|---|---|---|
| Close | +7.62 (3 in) | +0.635 | +7.62 | +7.62 |
| Regular | +8.89 (3½ in) | +0.635 | +10.16 | +7.62 |
| Relaxed | +12.7 (5 in) | +1.27 | +12.7 | +10.16 |

The source (p. 3) gives ranges: bust 3–5 in (its sample uses 3½), waist ¼–½ in per quarter, hip 3–5 in, upper
arm 3–4 in. Which value of each range belongs to which fit is a project choice. Knit T-shirt presets (project values; the source does not cover knits): bust 4 / 6 / 9 cm, hip 4 / 6 / 9,
upper arm 3 / 4 / 6. Sleeve end: + 4 cm (woven), + 2 cm (knit).

Seam allowances (cm), one value per kind of edge, in `SEAM_ALLOWANCES`:

| Edge | Woven | Knit |
|---|---|---|
| shoulder, side, sleeve seam | 1.5 | 1.0 |
| armhole and sleeve cap, neckline | 1.0 | 1.0 |
| hem, sleeve hem | 2.5 | 2.0 |
| strips (facing, neckband) | 1.0 | 0.7 |
| fold edge | 0 | 0 |

The armhole, side and sleeve values lie inside the ranges the source gives (armhole ⅜–½ in, side ½–1 in, sleeve
hem 1 in); shoulder, neckline and hem are project sewing choices. A research user can replace single values per
request (`seam_allowances` in `POST /api/patterns/generate`); the sewing line does not move, only the cutting line.

## 5. Design values are not fixed

Back neck depth, front neck depth, neckline width, armhole depth and the distance between bust points have a
value calculated by the method. The user can type another value on the measurement page; left empty, the
calculated value is used and shown as "Calculated value".

The 1 in shoulder drop is the source's default, not a universal truth: sloping or square shoulders need another
drop. It is one named value in the registry (`shoulder_drop_cm`, kind "design"), listed in "Why this size?" as a
standard value. It is **not yet a field on the measurement page**; changing it means changing the registry.

## 6. Project extensions (where the source gives no rule)

| Extension | Rule | Why |
|---|---|---|
| Garment longer than the waist | side seam from the waist to the hip line at the measured waist-to-hip depth; front + back = (H + ease) ÷ 2; then straight to the hem | the source's block stops at the waist |
| Fish darts | a waist dart continues below the waist with half its upper length | a dart cannot end open at the waist of a longer garment |
| Large waist | a dart is reduced (to zero if needed) when the waist is as wide as the block | the source's fixed darts assume a waist much smaller than the bust |
| Knit T-shirt | same construction lines, no darts, no front neck raise, no extra front length, equal front and back | the source drafts a fitted woven bodice only |
| Sleeve width | max(method width, upper arm + ease) | the source derives the sleeve from the bust only |
| Sleeve end | measured arm at the sleeve end + ease | so short and long sleeves follow the arm |
| Cap height | changed only when the method's cap does not fit the armhole (section 7) | so the sleeve can always be sewn in |
| Sleeve notches | at the same seam distance from the underarm as the bodice notches | so the marks really meet |
| V neck, square neck, puff and bell sleeves, facings, neckband | project design values (listed in the registry) | style changes applied to the block |

## 7. Armhole and sleeve cap

The armhole is not estimated from a formula. The engine measures the drafted curves:

* front armhole curve, back armhole curve and their total, along the sewing line;
* front and back sleeve-cap curves and their total.

The sleeve cap must be longer than the armhole by an amount inside the accepted **cap ease** range: woven
0.5–4.5 cm, knit 0–3 cm (a puff sleeve: 4–30 cm of gathers). If the method's cap already fits, it is kept. If not,
only the cap height is changed until it fits, and the report says so. The result is **PASS**, or **REVIEW** when the
height had to be changed by more than a quarter; a sleeve that cannot fit at all is an error with advice (for example a deeper
armhole), never a silently wrong pattern.

Example (regular fit; bust 88, waist 70, hip 94, shoulder to shoulder 37, back neck to waist 40, upper arm 28,
short sleeve 24 cm):

| | cm |
|---|---|
| Front armhole curve | 22.20 |
| Back armhole curve | 18.59 |
| Total armhole | 40.79 |
| Sleeve cap seam (method cap height 9.1) | 42.07 |
| Difference (cap ease) | 1.28 – inside 0.5 to 4.5 – **PASS** |

The source's own sample (bust 34 in) is a regression test: neck width 2.83 in, armhole depth 7½ in, sleeve
14 × 3½ in (`test_base_block.py`, golden test with a tolerance).

## 8. What is checked automatically, and what is not

Checked for every pattern (a failure stops generation): closed outlines without self-intersection, darts inside the
piece, equal front and back shoulder seams, equal side seams, finished bust and waist equal to body + ease, sleeve
cap against armhole, notch distances, cutting line outside the sewing line by the stated allowance, grain line,
fold line, cut quantities.

**Not checked:** how the garment fits a body. No toile (test garment) has been sewn from these patterns. The
values read from the source's figure, every project extension, and the ease presets are unverified by a fitting.
The pattern must be tried in cheap cloth before good fabric is cut.
