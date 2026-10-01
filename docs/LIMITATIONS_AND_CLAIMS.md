# Limitations, thesis-safe claims and viva demonstration

## Known limitations (state these yourself before an examiner finds them)

**Pattern**
1. The pattern is **mathematically generated and geometry-validated only**. It has not been fit-tested on bodies, compared with a professional pattern-maker's block, or checked by a muslin. Fit quality is therefore *unknown*.
2. About 30 drafting constants (ease, shoulder slope, back-neck depth, waist-to-hip distance, sleeve fractions, allowance widths …) are **project assumptions**, registered in `backend/app/logic/drafting/assumptions.py`. None is traced to Aldrich's *Metric Pattern Cutting* (the book is not in the repository) — do not describe the method as "Aldrich-based" without verifying each equation against the book.
3. Height, bust-point position (bust height, apex-to-apex), waist-to-hip distance and elbow circumference are not measured (considered on 30 Sep 2026 and deliberately not added: the bust point stays a registered assumption and is labelled as derived); the engine uses fixed assumptions where a tailor would measure. Negative-ease stretch-knit drafting is not implemented (rejected with a message).
4. Scope is deliberately narrow: two garments (blouse, T-shirt), the necklines and sleeves in the scope table. Other necklines/sleeve styles/lengths (incl. a collared neck) are rejected, not approximated. Puff and bell sleeves are geometry-validated (gathering range, flat lower cap, flare, perpendicular hem) but their spread, crown rise and flare amounts are project assumptions that have not been sewn. The sleeveless blouse armhole is the sleeved armhole without a sleeve; it has not been sewn either.
5. Pieces are simple (no collar, facing shapes are straight strips, no pockets/closures/lining); construction instructions are minimal.

**Fabric**
6. Nesting is a **greedy Bottom-Left-Fill heuristic** on a 0.5 cm grid — an upper bound on cloth, not an optimal marker. Plain fabric only (no print matching, nap, or stripes). Fabric shrinkage (3 %) and cutting margin (10 cm) are assumptions.
7. **No comparison with tailors or with a manual baseline has been collected yet**, so no fabric-saving percentage versus traditional practice can be claimed. An internal, researcher-only API for such a comparison exists (not in the customer app), but it holds no study data. Even with data, "the system recommends less" does not show the amount is enough - that needs a real cut. "Utilisation" is the share of the laid fabric covered by pattern pieces.
8. The fabric knowledge base is an author-compiled, rule-based ranking; its properties are not cited to a published standard.

**AI**
9. Four small image classifiers look at the garment area found by a garment detector. On the independent test sets with that crop they reach accuracy / macro-F1 of 0.89 / 0.89 for garment type (only 82 human-verified photos), 0.88 / 0.87 for sleeve length, 0.71 / 0.60 for neckline and 0.61 / 0.46 for sleeve design. **A 90 % target for every feature is not reached** ([AI_MODELS.md](AI_MODELS.md)). Automatic answers: garment type 90 % correct on 98 % of test photos; sleeve length 88 % on almost all (94 % on validation, so the test result is below the aim); neckline 91 % on the 43 % of photos where it is confident; sleeve design never. This is why the confirmed design, not the prediction, drives the pattern.
10. **Sleeve design is weak**: barely better than always answering "regular", and bell sleeves are almost never recognised (61 training and 13 test photos). Square neck (24 test photos) and collared neck (64) rest on very few examples. Collared neck and regular sleeve were labelled by **one reviewer who answered 725 photos in about 24 minutes**; a sample showed some wrong answers (jackets, coats) and no second reviewer has checked them. The detector crops the correct top in 79 % (street photos) to 90 % (shop photos) of test photos; otherwise a wrong area or the whole photo is classified.
11. Labels come from dataset annotations (Fashionpedia attributes, DeepFashion2 categories, DeepFashion-MultiModal shape labels). Most garment-type training labels are **proxies** (the shop category), not a judgement of woven against knit. No labelled set of real user phone photos exists, so behaviour on such photos is not measured. Each model was trained once; differences of a few points on the small sets are within noise.
12. The results of the earlier single model (M40) and of the four models are not directly comparable: the classes changed and 36 near-duplicate test photos were removed. The switch to four separate models was a project decision, not the outcome of a like-for-like comparison.

**System**
13. Prototype security: no e-mail service, so **no "forgot password" reset** (a signed-in user changes the password with the current one; otherwise the server operator resets it with `backend/tools/reset_password.py`), no e-mail verification, no rate limiting, no production deployment hardening (WSGI server, HTTPS). Changing a password does not sign out other devices before their 24-hour session ends. Google sign-in works only after a Google OAuth client id is configured. `npm audit` still reports 6 findings that need major upgrades of the development tools (vite 5, vitest 1) and of react-router 6; they concern the development server, the test UI and server-side rendering, none of which runs in the built app.
14. Usability, accuracy and fabric-waste **user studies have not been run**; there is no participant data. The in-app instruments (1-5 usability rating, traditional-vs-system fabric comparison, measured analysis/drafting times) are ready for such a study.
15. The proposal promised items that were not built: a supervised size-prediction model, YOLO detection of darts/seams/landmarks, collars, negative-ease stretch knits and a chat assistant. See [THESIS_RECONCILIATION.md](THESIS_RECONCILIATION.md).

## AI accuracy — what may and may not be said

* **May say:** a garment detector and four separate classifiers (MobileNetV3-Large for garment type; YOLOv8n-cls for neckline, sleeve length and sleeve design) were trained on licensed research datasets and evaluated on independent, near-duplicate-filtered test photos through the app's own inference code; the app shows each feature's score, fills a feature in only above a validation-chosen threshold, marks the rest "uncertain — please select", and always requires user confirmation.
* **Must not say:** that the AI reaches 90 %, or that it is "accurate". Say the measured numbers of [AI_MODELS.md](AI_MODELS.md) with their test-set sizes, including the weak ones (neckline 0.71, sleeve design 0.61, bell sleeve F1 0.10) and the 88 % for automatic sleeve-length answers. Do not present the garment-type result without saying it rests on 82 photos.

## SAFE thesis / viva claims

* An integrated prototype implements the full pipeline photo → AI suggestion → mandatory user confirmation → validated measurements → parametric pattern → seam allowances → automatic validation → polygon nesting → printable 1:1 PDF, verified by automated tests (see TESTING.md) and a real-browser end-to-end run.
* The AI is used only for **design suggestion**; pattern generation is deterministic and explainable, and every non-derived constant is listed and labelled as an assumption.
* The system **refuses instead of guessing**: unsupported combinations, contradictory garment length, missing (for the design) or non-positive measurements, measurements that cannot be drafted, invalid geometry and pieces wider than the fabric all produce explicit errors.
* Seam allowance is real offset geometry (woven and knit differ), with notches, grainlines, fold lines, darts and cut quantities on every piece; 72–95 automatic geometric checks pass for each of six representative designs (`backend/tools/generate_evidence.py`).
* Printing: the PDF is genuine 1:1 A4 tiles with overlap, crop marks and a 5 cm calibration square; scale was verified by reading the PDF vector data.
* Fabric estimates for 36", 45" and 60" cloth (91.44, 114.3, 152.4 cm) are produced from the actual cutting-line polygons, with exact overlap/bounds/fold/grain verification and a documented purchase allowance.
* Reported AI metrics are those in AI_MODELS.md, computed by `backend/training/evaluate_models.py` on photos never used for training; thresholds were chosen on validation photos only and not changed after the test results were seen.
* Security and privacy measures: verified Google sign-in, hashed passwords, JWT with ownership checks, content-checked uploads, researcher-only pseudonymised study data, no internal error details in API responses.
* The system is honest about the AI being unavailable (HTTP 503, "choose the design manually"), and the manual path drafts the same pattern.
* An internal, researcher-only API can record traditional fabric estimates next to the system estimate for the same width (descriptive statistics, pseudonymised export) — it is not part of the customer app, and **no results exist until data is collected**.

## Claims that MUST NOT be made

* "Production-ready", "tailor-quality", "accurate fit", "guaranteed fit", "professionally validated", "100 % accurate" — for the pattern or the AI.
* "Aldrich-based / Aldrich-validated" drafting (unverified — see limitation 2).
* Any percentage fabric saving or waste reduction versus traditional/tailor estimation; "optimal" or "minimum" fabric.
* Any usability, satisfaction or accuracy result from users, tailors or a muslin test (none exist).
* A machine-learned size-prediction model, cross-validation results, YOLO *detection* of darts/seams/landmarks, collars, negative-ease drafting or a chat assistant (none exist); "AI" for the rule-based fabric ranking or the algorithmic nesting.
* Model accuracy beyond the numbers in AI_MODELS.md; "zero data leakage" (photos, garment items and near-identical photos are kept apart, which reduces but cannot prove the absence of leakage); mAP of design features (the design models are classifiers; only the garment detector is an object detector); TensorFlow / Keras models (all models are PyTorch).
* That the system supports other necklines/sleeve styles/garments than the scope table.
* That the AI recognises crop tops, off-shoulder necklines or any class outside the scope file; that sleeve design is recognised reliably.

## Suggested viva demonstration (≈ 10 minutes)

1. **Show the scope table** (README) and say what is deliberately excluded.
2. **Sign in → Create pattern.** Upload a blouse photo; point out the four separate model scores and any "uncertain - please select" feature; **change one prediction** to show you stay in control. Try an out-of-scope choice (T-shirt + square neck) to show it is refused with a reason.
3. **Measurements.** Type an impossible bust (5 cm) to show the inline error; switch cm ↔ in; enter the valid set (bust 88, waist 70, hip 94, height 162, neck 36, shoulder 12, across-back 34, back-waist 40, armhole 20, length 65, bicep 28, sleeve 55, wrist 16).
4. **Fabric and fit.** Show the fabric explanations; choose Cotton Poplin (woven) — mention that a T-shirt automatically uses the knit block.
5. **Pattern preview.** Point at the solid cutting line vs dashed sewing line, notches, darts, fold and grain; open the validation panel ("Geometry validation passed", armhole vs sleeve-cap numbers).
6. **Fabric estimate.** Select 36", 45" and 60" (91.44 / 114.3 / 152.4 cm); show the layout drawing and the "how this was calculated" assumptions. Say plainly it is a heuristic, not optimal.
7. **PDF.** Create and download; open it; show the 5 cm calibration square, instructions and a tile page; hold a ruler to the square if printing.
8. **Evidence.** Show `docs/AI_MODELS.md` (the four models, data, per-class results, what is and is not filled in automatically) and the green test suites.
9. **Close with the limitations** (no fit test yet; assumptions registry; small dataset) and the future work: muslin trials with 3–5 tailors/testers, more sleeve-design and neckline data, phone-photo test set, Aldrich verification.
