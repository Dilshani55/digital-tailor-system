# Fabric calculation

How the system answers "how much fabric do I need?" for 36, 45 and 60 inch fabric. Code:
`backend/app/logic/nesting_algorithm.py`, `backend/app/logic/units.py`, route `POST /api/export/estimates/<id>`.

## The principle

The fabric length is **not** a formula such as "length + sleeve length". The real pattern pieces are laid on a
rectangle of the fabric's width, and the length they occupy is measured. If the pieces change, the answer changes.

## Method

1. **Pieces.** The stored, validated pieces are used with their **cutting lines** (seam allowance included) and
   their cut quantities (for example: front 1 on the fold, back 1 on the fold, sleeve 2).
2. **Widths.** 36 in = 91.44 cm, 45 in = 114.3 cm, 60 in = 152.4 cm (1 in = 2.54 cm exactly). The pieces are the
   same for every width; only the layout changes.
3. **Cutting mode.** *Folded*: the fabric is folded lengthwise, usable width is half, a piece cut on the fold lies
   against the fold and other pieces are cut through both layers. *Open*: full width, fold pieces are opened to
   their full shape. *Auto* calculates both and keeps the shorter purchase.
4. **Grain.** The fabric length is the grain direction. A piece may be turned by 180° but never by 90°.
5. **One-way fabric** (nap, pile, a print with a direction): with this option no piece is turned at all, so all
   pieces point the same way. The layout can only stay the same or get longer.
6. **Placing.** Bottom-Left-Fill on a 0.5 cm grid: each piece goes to the lowest, then left-most free position of
   its real outline (not its bounding box). Pieces stay at least 0.5 cm apart. Three placing orders are tried
   (largest area first, longest first, widest first) and the shortest layout is kept.
7. **Checks on the result**, with exact polygon tests: no two pieces overlap, every piece is inside the fabric,
   fold pieces touch the fold, the grain is kept, every piece is there in its quantity. A piece wider than the
   fabric gives "does not fit" for that width; it is never left out.
8. **Purchase length.** layout length + 3 % (shrinkage) + 10 cm (uneven ends), rounded up to the next 10 cm. These
   three numbers are project assumptions and are printed with the result.

## What is reported for each width

| Value | Meaning |
|---|---|
| Layout length (cm) | the length the laid-out pieces occupy |
| Need to buy (m and yd) | the purchase length; 1 yd = 0.9144 m |
| Pattern area (m² and yd²) | the area of the pieces themselves; 1 yd² = 0.83612736 m² |
| Fabric bought (m² and yd²) | width × purchase length |
| Fabric use (%) | pattern area ÷ (width × layout length) |
| Waste (%) | 100 − fabric use |

Metres and yards are **lengths** of a given width; square metres and square yards are **areas**. The app shows
both and explains the difference under the table.

## Example

Regular-fit woven blouse, round neck, short plain sleeve; bust 88, waist 70, hip 94 cm, garment length 65 cm
(reproduce with `backend/tools/generate_evidence.py`). Pattern area 0.813 m² (0.972 yd²).

| Width | Layout length | Need to buy | Fabric bought | Fabric use | Waste |
|---|---|---|---|---|---|
| 36 in (91.44 cm) | 143.2 cm | 1.6 m / 1.75 yd | 1.463 m² / 1.75 yd² | 62.1 % | 37.9 % |
| 45 in (114.3 cm) | 101.5 cm | 1.2 m / 1.31 yd | 1.372 m² / 1.64 yd² | 70.1 % | 29.9 % |
| 60 in (152.4 cm) | 72.9 cm | 0.9 m / 0.98 yd | 1.372 m² / 1.64 yd² | 73.2 % | 26.8 % |

**The widest fabric is not automatically the best.** The same blouse with a V neck and long sleeves:

| Width | Layout length | Need to buy | Fabric bought | Fabric use |
|---|---|---|---|---|
| 36 in | 184.0 cm | 2.0 m / 2.19 yd | 1.829 m² | 58.6 % |
| 45 in | 132.0 cm | 1.5 m / 1.64 yd | 1.714 m² | 65.4 % |
| 60 in | 117.0 cm | 1.4 m / 1.53 yd | 2.134 m² | 55.3 % |

Here 60 in fabric needs the shortest length but the most cloth by area and wastes the most; 45 in uses the cloth
best. The app shows the three widths side by side and does not pick one as "best": the price per metre decides.
On one-way fabric this long-sleeve layout grows to 193 cm on 36 in fabric.

## Limits

* The layout is a **heuristic**: a valid layout, usually not the shortest possible one. A skilled cutter may need
  less. Words such as "optimal" or "minimum" are not used.
* No pattern matching (stripes, checks), no fabric faults, no shrinkage measured for a real cloth.
* The numbers have not been compared with a tailor's estimate or with cloth really cut
  ([HUMAN_VALIDATION.md](HUMAN_VALIDATION.md) has the sheet for that).
