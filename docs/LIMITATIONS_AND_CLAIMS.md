# Limitations, thesis-safe claims and viva demonstration

## Known limitations (state these yourself before an examiner finds them)

**Pattern**
1. The pattern is **mathematically generated and geometry-validated only**. It has not been fit-tested on bodies, compared with a professional pattern-maker's block, or checked by a muslin. Fit quality is therefore *unknown*.
2. About 30 drafting constants (ease, shoulder slope, back-neck depth, waist-to-hip distance, sleeve fractions, allowance widths …) are **project assumptions**, registered in `backend/app/logic/drafting/assumptions.py`. None is traced to Aldrich's *Metric Pattern Cutting* (the book is not in the repository) — do not describe the method as "Aldrich-based" without verifying each equation against the book.
3. Height, bust-point position (bust height, apex-to-apex), waist-to-hip distance and elbow circumference are not measured (considered on 30 Sep 2026 and deliberately not added: the bust point stays a registered assumption and is labelled as derived); the engine uses fixed assumptions where a tailor would measure. Negative-ease stretch-knit drafting is not implemented (rejected with a message).
4. Scope is deliberately narrow: three garments, the necklines and sleeves in the scope table. Other necklines/sleeve styles/lengths (incl. collared and off-shoulder) are rejected, not approximated. Puff and bell sleeves are geometry-validated (gathering range, flat lower cap, flare, perpendicular hem) but their spread, crown rise and flare amounts are project assumptions that have not been sewn.
5. Pieces are simple (no collar, facing shapes are straight strips, no pockets/closures/lining); construction instructions are minimal.

**Fabric**
6. Nesting is a **greedy Bottom-Left-Fill heuristic** on a 0.5 cm grid — an upper bound on cloth, not an optimal marker. Plain fabric only (no print matching, nap, or stripes). Fabric shrinkage (3 %) and cutting margin (10 cm) are assumptions.
7. **No comparison with tailors or with a manual baseline has been collected yet**, so no fabric-saving percentage versus traditional practice can be claimed. An internal, researcher-only API for such a comparison exists (not in the customer app), but it holds no study data. Even with data, "the system recommends less" does not show the amount is enough - that needs a real cut. "Utilisation" is the share of the laid fabric covered by pattern pieces.
8. The fabric knowledge base is an author-compiled, rule-based ranking; its properties are not cited to a published standard.

**AI**
9. The classifier (M40) is a small image-level model that sees the garment area found by a garment detector. On the independent test set with that crop it reaches accuracy / macro-F1 of 0.76 / 0.76 for garment type (n = 126), 0.66 / 0.50 for neckline, 0.84 / 0.82 for sleeve length and 0.93 / 0.62 for sleeve style (dominated by one class). **Only sleeve length is filled in automatically** (92 % correct when it answers, on 80 % of photos); garment type, neckline and sleeve style are always "please select". The 90 % target is not reached (see [AI_EVIDENCE.md](AI_EVIDENCE.md), [AI_DETECTOR.md](AI_DETECTOR.md)). This is why the confirmed design, not the prediction, drives the pattern.
10. Two of the 15 selectable classes - **regular sleeve and collared neck - have no trusted label in any dataset**, so the model cannot recognise them and they cannot be tested; bell sleeve (13 test photos), square neck (24) and off-shoulder (42) rest on very few examples. A 725-photo human review queue and a fixed acceptance gate for the next model are prepared ([AI_DATA_AUDIT.md](AI_DATA_AUDIT.md)); the review has not been done and no new model has been trained. The detector crops the correct top in 79 % (street photos) to 90 % (shop photos) of test photos; otherwise the whole photo is classified.
11. Labels come from dataset annotations (Fashionpedia attributes, DeepFashion2 categories, DeepFashion-MultiModal shape labels); only garment type has human-verified labels (126 test photos), and most garment-type training labels are **proxies** (shop category, navel rule). No labelled set of real user phone photos exists, so behaviour on such photos is not measured. Differences of a few points between models on the small heads are within noise.
12. The 1 Oct 2026 audit found 36 test photos with a near-identical training photo (perceptual hash) in the data the M40 / M41 results were computed on, so those reported numbers are slightly optimistic; the manifests for the next model remove them. It also found 4,481 tank tops labelled "t-shirt" in the M41 experiment's proxy labels (not in M40's training data).

**System**
13. Prototype security: no e-mail service, so **no "forgot password" reset** (a signed-in user changes the password with the current one; otherwise the server operator resets it with `backend/tools/reset_password.py`), no e-mail verification, no rate limiting, no production deployment hardening (WSGI server, HTTPS). Changing a password does not sign out other devices before their 24-hour session ends. Google sign-in works only after a Google OAuth client id is configured. `npm audit` still reports 6 findings that need major upgrades of the development tools (vite 5, vitest 1) and of react-router 6; they concern the development server, the test UI and server-side rendering, none of which runs in the built app.
14. Usability, accuracy and fabric-waste **user studies have not been run**; there is no participant data. The in-app instruments (1-5 usability rating, traditional-vs-system fabric comparison, measured analysis/drafting times) are ready for such a study.
15. The proposal promised items that were not built: a supervised size-prediction model, YOLO detection of darts/seams/landmarks, collars, negative-ease stretch knits and a chat assistant. See [THESIS_RECONCILIATION.md](THESIS_RECONCILIATION.md).

## AI accuracy — what may and may not be said (updated with M40)

* **May say:** a 3/5/3/4 classifier was trained on licensed, trusted data (DeepFashion2 sleeve categories + Fashionpedia attributes) and evaluated on independent, near-duplicate-filtered test sets; it clearly improves on the earlier model (especially on whole photos); the app shows each feature's score, marks unreliable features "uncertain — please select", and always requires user confirmation.
* **Must not say:** that it reaches 90 %. Measured (forced answer): garment type 77 % on crops / 67 % on whole photos, neckline 73 % / 51 % (majority-class baseline 67 %), sleeve length 86 % / 79 %, sleeve design 91–95 % but dominated by one class (macro-F1 0.51–0.73, bell-sleeve never recognised). Only sleeve length, when the model chooses to answer, is ~90–95 % correct on two of four test sets. Collared-neck and regular-sleeve cannot be recognised at all (no trusted examples). See [AI_EVIDENCE.md §7](AI_EVIDENCE.md).

## SAFE thesis / viva claims

* An integrated prototype implements the full pipeline photo → AI suggestion → mandatory user confirmation → validated measurements → parametric pattern → seam allowances → automatic validation → polygon nesting → printable 1:1 PDF, verified by automated tests (see TESTING.md) and a real-browser end-to-end run.
* The AI is used only for **design suggestion**; pattern generation is deterministic and explainable, and every non-derived constant is listed and labelled as an assumption.
* The system **refuses instead of guessing**: unsupported combinations, contradictory garment length, missing (for the design) or non-positive measurements, measurements that cannot be drafted, invalid geometry and pieces wider than the fabric all produce explicit errors.
* Seam allowance is real offset geometry (woven and knit differ), with notches, grainlines, fold lines, darts and cut quantities on every piece; 66–90 automatic geometric checks pass for each of the six representative designs (evidence.json).
* Printing: the PDF is genuine 1:1 A4 tiles with overlap, crop marks and a 5 cm calibration square; scale was verified by reading the PDF vector data.
* Fabric estimates for 36", 45" and 60" cloth (91.44, 114.3, 152.4 cm) are produced from the actual cutting-line polygons, with exact overlap/bounds/fold/grain verification and a documented purchase allowance.
* Reported AI metrics are those in AI_EVIDENCE.md, computed by the scripts in `ai_training/`; a new model is deployed only if it beats the deployed one on the locked benchmark **and** a clean test split (acceptance gate); the newer experimental models did not, so the earlier checkpoint stays.
* Security and privacy measures: verified Google sign-in, hashed passwords, JWT with ownership checks, content-checked uploads, researcher-only pseudonymised study data, no internal error details in API responses.
* The system is honest about the AI being unavailable (HTTP 503, "choose the design manually"), and the manual path drafts the same pattern.
* An internal, researcher-only API can record traditional fabric estimates next to the system estimate for the same width (descriptive statistics, pseudonymised export) — it is not part of the customer app, and **no results exist until data is collected**.

## Claims that MUST NOT be made

* "Production-ready", "tailor-quality", "accurate fit", "guaranteed fit", "professionally validated", "100 % accurate" — for the pattern or the AI.
* "Aldrich-based / Aldrich-validated" drafting (unverified — see limitation 2).
* Any percentage fabric saving or waste reduction versus traditional/tailor estimation; "optimal" or "minimum" fabric.
* Any usability, satisfaction or accuracy result from users, tailors or a muslin test (none exist).
* A machine-learned size-prediction model, cross-validation results, YOLO *detection* of darts/seams/landmarks, collars, negative-ease drafting or a chat assistant (none exist); "AI" for the rule-based fabric ranking or the algorithmic nesting.
* Model accuracy beyond the numbers in AI_EVIDENCE.md; "zero data leakage" (image IDs are disjoint, but near-duplicates exist); a detector's mAP (the deployed model is a classifier, not an object detector); training on DeepFashion2 (the data is Fashionpedia).
* That the system supports other necklines/sleeve styles/garments than the scope table.
* That a 15-class model exists, has been trained, or is deployed (it is only planned; the deployed model is the original M13).

## Suggested viva demonstration (≈ 10 minutes)

1. **Show the scope table** (README) and say what is deliberately excluded.
2. **Sign in → Create pattern.** Upload a blouse photo; point out the AI's confidences and any low-confidence warning; **change one prediction** to show you stay in control. Try an out-of-scope choice (T-shirt + square neck) to show it is refused with a reason.
3. **Measurements.** Type an impossible bust (5 cm) to show the inline error; switch cm ↔ in; enter the valid set (bust 88, waist 70, hip 94, height 162, neck 36, shoulder 12, across-back 34, back-waist 40, armhole 20, length 65, bicep 28, sleeve 55, wrist 16).
4. **Fabric and fit.** Show the fabric explanations; choose Cotton Poplin (woven) — mention that a T-shirt automatically uses the knit block.
5. **Pattern preview.** Point at the solid cutting line vs dashed sewing line, notches, darts, fold and grain; open the validation panel ("Geometry validation passed", armhole vs sleeve-cap numbers).
6. **Fabric estimate.** Select 36", 45" and 60" (91.44 / 114.3 / 152.4 cm); show the layout drawing and the "how this was calculated" assumptions. Say plainly it is a heuristic, not optimal.
7. **PDF.** Create and download; open it; show the 5 cm calibration square, instructions and a tile page; hold a ruler to the square if printing.
8. **Evidence.** Show `docs/AI_EVIDENCE.md` (metrics, dataset audit, why the new models were *not* deployed) and the green test suites.
9. **Close with the limitations** (no fit test yet; assumptions registry; small dataset) and the future work: muslin trials with 3–5 tailors/testers, more sleeveless/regular-sleeve data, Aldrich verification.
