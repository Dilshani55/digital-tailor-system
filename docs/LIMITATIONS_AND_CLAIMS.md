# Limitations, thesis-safe claims and viva demonstration

## Known limitations (state these yourself before an examiner finds them)

**Pattern**
1. The pattern is **mathematically generated and geometry-validated only**. It has not been fit-tested on bodies, compared with a professional pattern-maker's block, or checked by a muslin. Fit quality is therefore *unknown*.
2. About 25 drafting constants (ease, shoulder slope, back-neck depth, waist-to-hip distance, sleeve fractions, allowance widths …) are **project assumptions**, registered in `backend/app/logic/drafting/assumptions.py`. None is traced to Aldrich's *Metric Pattern Cutting* (the book is not in the repository) — do not describe the method as "Aldrich-based" without verifying each equation against the book.
3. Height, bust-point position, waist-to-hip distance and elbow circumference are not measured; the engine uses fixed assumptions where a tailor would measure. Negative-ease stretch-knit drafting is not implemented (rejected with a message).
4. Scope is deliberately narrow: three garments, the necklines and sleeves in the scope table. Other necklines/sleeve styles/lengths are rejected, not approximated.
5. Pieces are simple (no collar, facing shapes are straight strips, no pockets/closures/lining); construction instructions are minimal.

**Fabric**
6. Nesting is a **greedy Bottom-Left-Fill heuristic** on a 0.5 cm grid — an upper bound on cloth, not an optimal marker. Plain fabric only (no print matching, nap, or stripes). Fabric shrinkage (3 %) and cutting margin (10 cm) are assumptions.
7. **No comparison with tailors or with a manual baseline exists**, so no fabric-saving percentage versus traditional practice can be claimed. "Utilisation" is the share of the laid fabric covered by pattern pieces.
8. The fabric knowledge base is an author-compiled, rule-based ranking; its properties are not cited to a published standard.

**AI**
9. The classifier is a small image-level model. On the deployed checkpoint the garment-type head is reasonable (macro-F1 ≈ 0.79) but neckline (≈ 0.42), sleeve length (≈ 0.60) and especially sleeve style (≈ 0.32) are weak, and "sleeveless" / "regular sleeve" — the classes the supported scope needs most — have almost no training or test examples (see [AI_EVIDENCE.md](AI_EVIDENCE.md)). This is exactly why the user must confirm the design.
10. The model predicts more classes (28) than the user can select (15). On the 60 real benchmark photos M13 predicts at least one class **outside** the selectable list for **49 of 60 (82 %)**, so manual confirmation is the normal path, not an exception. The future 15-class model is planned only ([FUTURE_15_CLASS_MODEL.md](FUTURE_15_CLASS_MODEL.md)): nine of its 15 classes still lack trusted training/validation/test examples, and it has **not** been trained.
11. Labels are mostly derived from Fashionpedia annotations and rules; only garment type has human-verified gold labels. The 60-image real-product benchmark is small (23–54 labelled items per head), so differences of a few points are within noise.
12. The dataset contains near-duplicate photos across splits (≈ 4–5 % of validation/test images have a near-twin in training). Reported test numbers on the full test split are therefore slightly optimistic; the acceptance gate also evaluates a "clean" test split without them.

**System**
13. Single-user prototype: no email verification, password reset, rate limiting or production deployment hardening (WSGI server, HTTPS). Google sign-in works only after a Google OAuth client id is configured.
14. Usability, accuracy and fabric-waste **user studies have not been run**; there is no participant data.

## SAFE thesis / viva claims

* An integrated prototype implements the full pipeline photo → AI suggestion → mandatory user confirmation → validated measurements → parametric pattern → seam allowances → automatic validation → polygon nesting → printable 1:1 PDF, verified by automated tests (see TESTING.md) and a real-browser end-to-end run.
* The AI is used only for **design suggestion**; pattern generation is deterministic and explainable, and every non-derived constant is listed and labelled as an assumption.
* The system **refuses instead of guessing**: unsupported combinations, contradictory garment length, incomplete/implausible measurements, invalid geometry and pieces wider than the fabric all produce explicit errors.
* Seam allowance is real offset geometry (woven and knit differ), with notches, grainlines, fold lines, darts and cut quantities on every piece; 66–90 automatic geometric checks pass for each of the six representative designs (evidence.json).
* Printing: the PDF is genuine 1:1 A4 tiles with overlap, crop marks and a 5 cm calibration square; scale was verified by reading the PDF vector data.
* Fabric estimates for 90, 114 and 150 cm cloth are produced from the actual cutting-line polygons, with exact overlap/bounds/fold/grain verification and a documented purchase allowance.
* Reported AI metrics are those in AI_EVIDENCE.md, computed by the scripts in `ai_training/`; a new model is deployed only if it beats the deployed one on the locked benchmark **and** a clean test split (acceptance gate); the newer experimental models did not, so the earlier checkpoint stays.
* Security and privacy measures: verified Google sign-in, hashed passwords, JWT with ownership checks, content-checked uploads, researcher-only pseudonymised study data.

## Claims that MUST NOT be made

* "Production-ready", "tailor-quality", "accurate fit", "guaranteed fit", "professionally validated", "100 % accurate" — for the pattern or the AI.
* "Aldrich-based / Aldrich-validated" drafting (unverified — see limitation 2).
* Any percentage fabric saving or waste reduction versus traditional/tailor estimation; "optimal" or "minimum" fabric.
* Any usability, satisfaction or accuracy result from users, tailors or a muslin test (none exist).
* Model accuracy beyond the numbers in AI_EVIDENCE.md; "zero data leakage" (image IDs are disjoint, but near-duplicates exist); a detector's mAP (the deployed model is a classifier, not an object detector); training on DeepFashion2 (the data is Fashionpedia).
* That the system supports other necklines/sleeve styles/garments than the scope table.
* That a 15-class model exists, has been trained, or is deployed (it is only planned; the deployed model is the original M13).

## Suggested viva demonstration (≈ 10 minutes)

1. **Show the scope table** (README) and say what is deliberately excluded.
2. **Sign in → Create pattern.** Upload a blouse photo; point out the AI's confidences and any low-confidence warning; **change one prediction** to show you stay in control. Try an out-of-scope choice (T-shirt + square neck) to show it is refused with a reason.
3. **Measurements.** Type an impossible bust (5 cm) to show the inline error; switch cm ↔ in; enter the valid set (bust 88, waist 70, hip 94, height 162, neck 36, shoulder 12, across-back 34, back-waist 40, armhole 20, length 65, bicep 28, sleeve 55, wrist 16).
4. **Fabric and fit.** Show the fabric explanations; choose Cotton Poplin (woven) — mention that a T-shirt automatically uses the knit block.
5. **Pattern preview.** Point at the solid cutting line vs dashed sewing line, notches, darts, fold and grain; open the validation panel ("Geometry validation passed", armhole vs sleeve-cap numbers).
6. **Fabric estimate.** Click 90, 114, 150 cm; show the layout drawing and the "how this was calculated" assumptions. Say plainly it is a heuristic, not optimal.
7. **PDF.** Create and download; open it; show the 5 cm calibration square, instructions and a tile page; hold a ruler to the square if printing.
8. **Evidence.** Show `docs/AI_EVIDENCE.md` (metrics, dataset audit, why the new models were *not* deployed) and the green test suites.
9. **Close with the limitations** (no fit test yet; assumptions registry; small dataset) and the future work: muslin trials with 3–5 tailors/testers, more sleeveless/regular-sleeve data, Aldrich verification.
