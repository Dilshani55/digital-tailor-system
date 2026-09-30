# Proposal ↔ implementation reconciliation

The only research document in the repository is `Proposal.pdf` (December 2025); there is no thesis draft yet.
This table compares every technical claim of the proposal with the code as it is now (checked against the
source, tests and evidence files on 30 Sep 2026). Use the last column when writing the thesis: where the
system differs from the proposal, the thesis must describe the **system**, and say why it changed.

Status: **Matches** · **Changed** (implemented differently; describe what was built) · **Not implemented**
(remove the claim or move it to future work) · **Instrument only** (the software to collect the evidence
exists, the evidence itself does not yet).

| # | Proposal (section) | What the proposal says | What the system does | Status | What the thesis should say |
|---|---|---|---|---|---|
| 1 | 4.3.2 | Train on **DeepFashion2** (Kaggle) | Trained on **Fashionpedia** (annotations CC BY 4.0): 15,794 labelled garment records, splits by source image (docs/AI_EVIDENCE.md §2) | Changed | Name Fashionpedia. Reason recorded in `docs/ai_history/DATASET_SOURCE_AUDIT.md`: DeepFashion2 does not provide the neckline and sleeve-style labels this project needs. |
| 2 | 4.5 B | **YOLOv8 object detection** of necklines, sleeve types, **darts and seam configurations**, key **landmarks** | One **image classifier** (YOLOv8n-cls backbone + 4 heads: garment type, neckline, sleeve length, sleeve style). No detection boxes, no landmarks, no dart/seam recognition. Darts are produced by the drafting engine from measurements. | Changed | "A multi-task image classifier based on the YOLOv8n-cls backbone"; report classification accuracy / macro-F1, **not mAP**. State that darts/seams are determined by the drafting method, not recognised in the photo. |
| 3 | 4.5 C | **Supervised size-prediction model** mapping image features + body metrics to garment measurements, validated by **cross-validation**; "personalised size chart" | **No size-prediction model.** Garment dimensions are computed deterministically: body measurement + documented ease → drafting values → base block (docs/PATTERN_ENGINE.md). The PDF lists the 13 body measurements used, the ease added and every piece with its cut size. | Changed | Describe parametric (rule-based) drafting as the answer to RQ2. There was no labelled data of "features → garment measurements" to train a model on; a deterministic method is explainable and testable. Do not claim ML size prediction or cross-validation results. The "size chart" is the measurement + ease + piece-size summary. |
| 4 | 4.5 D | Proportional scaling "based on **Winifred Aldrich's** Metric Pattern Cutting" | Conventional metric bodice/sleeve drafting; ~25 non-derived constants registered as **project assumptions** in `drafting/assumptions.py`. No equation has been checked against the book (not in the repository). | Changed / unverified | Do **not** call the method Aldrich-based unless each equation is verified against the book first. Say "conventional metric block drafting with documented assumptions". |
| 5 | 4.5 D | Fabric-specific ease **including negative ease for stretch knits** | Woven and knit blocks with positive ease; stretch-knit (negative ease) is **rejected with a message**, not approximated | Changed | Knit with moderate stretch only; negative-ease drafting is future work. |
| 6 | 4.5 D | Consider **collars** and other design elements | Necklines round / V / square; collared neck and off-shoulder are selectable but **rejected** at generation (no collar piece) | Not implemented | List collars as out of scope / future work. |
| 7 | 4.5 D | 2D **nesting** algorithm "to minimise material waste"; "exact fabric yardage" | Greedy **Bottom-Left-Fill** heuristic on real cutting-line polygons (0.5 cm grid, grain-preserving 0°/180°, fold handling), exact overlap/bounds checks; purchase = layout + 3 % + 10 cm | Matches (with caveat) | "Heuristic nesting; the layout is feasible and verified, but not proven minimal." Never "optimal" or "minimum". |
| 8 | 4.5 D | "production-ready PDF drafting guide via **ReportLab**" | ReportLab 1:1 A4-tiled PDF with calibration square; scale verified by reading the PDF vector data; the PDF prints the stored, validated pieces | Matches (wording) | Drop "production-ready" (no fit trial). "Printable 1:1 tiled pattern, scale-verified." |
| 9 | 4.4 (1) | **Chat assistant** interface | None | Not implemented | Remove, or list as future work. |
| 10 | 4.4 (2) | "Material Estimation Subsystem … AI-based material calculation" (also 2.2) | Fabric quantity is computed by the nesting **algorithm**; fabric *recommendation* is **rule-based** and explains itself | Changed | Only the design classifier is AI/ML. Call nesting "algorithmic" and fabric recommendation "rule-based". |
| 11 | 4.4 (4) | **Evaluation module**: comparison logic between traditional methods and the system | **Internal API only (30 Sep 2026):** `/api/research/fabric-comparisons` stores a traditional estimate (tailor / manual calculation / shop rule of thumb) next to the system estimate recomputed for the same width; researchers get a descriptive summary and a pseudonymised CSV. It was removed from the customer app on request: the product calculates fabric from the pattern and never asks for a tailor estimate | Instrument only | Describe the instrument. Report results **only** after real estimates have been collected; until then there is no comparison result. |
| 12 | 4.3.1 | Fabric consumption for **10 designs**, validated against **3–5 professional tailors** | No tailor data exists in the database or the repository | Not done | Collect it with the instrument in #11 (same fabric width, pseudonymous labels). If it is not collected before submission, state it as a limitation. |
| 13 | 4.6.2 | "Quantify fabric saved … present **percentage change**" | The summary gives mean/median/SD of (traditional − system) and a mean relative difference **from entered data only**; `avg_fabric_savings` stays `null` | Instrument only | No saving percentage may be claimed now. With data: report the descriptive values and n, and note that "system recommends less" ≠ "enough cloth" (not verified by cutting). |
| 14 | 4.6.1 | **Fit accuracy** vs actual measurements and standard size charts | Geometry validation only (66–90 automatic checks per design); no fit trial, no comparison with size charts | Not done | Limitation: fit has not been tested on bodies; future work = muslin trials. |
| 15 | 4.6.3 | **Usability** survey, Likert scale | In-app 1–5 ease-of-use rating + comment after the PDF download, stored pseudonymised; **no participant study has been run** | Instrument only | Report only if a study is run (with consent, n, instrument). |
| 16 | 4.4 | Backend in Node.js (given as an example) | Python **Flask** REST API, React (Vite) frontend, MongoDB | Changed | Describe Flask/React/MongoDB. |
| 17 | 4.4 (3) | Database stores users, images, size profiles, system logs | MongoDB: users, measurement profiles (customers), design images + predictions + confirmations, sessions, patterns (+ validation, measurement snapshot, drafting time), PDF exports, research records (+ measured analysis/drafting times), fabric comparisons | Matches | — |
| 18 | 4.8 | Scope: women's blouses, T-shirts, crop tops | Same three garments; the draftable combinations are the scope table in README | Matches | Include the scope table. |
| 19 | 3.2 RQ1 | Which AI/image methods can identify design parameters | Classifier results in docs/AI_EVIDENCE.md (garment type macro-F1 ≈ 0.79 on the locked benchmark; neckline ≈ 0.42, sleeve length ≈ 0.60, sleeve style ≈ 0.32) and three controlled experiments that failed the acceptance gate | Matches | Report these numbers exactly, including the weak heads and why the user must confirm the design. |
| 20 | Title / 1.3 | "…for custom clothing fit and **fabric waste reduction**" | Waste reduction has **not** been measured (#13) and fit has not been tested (#14) | Open | Either collect the evidence (#12, #15, muslin trial) or phrase results as "a system designed to support…", with the evaluation stated as future work. |

## Changes made on 30 Sep 2026 to close gaps

* Evaluation instrument for #11–#13 as an internal researcher-only API with tests (no customer UI).
* Measured timings (#17): classifier inference time and pattern drafting time are now measured and stored;
  previously these research fields were always "not measured".
* Honest AI availability: a missing/corrupt checkpoint is reported as "AI unavailable — choose the design manually" (503), never as a generic error.
* Removed fabricated values from the UI (notifications, customer pattern counts, e-mail addresses, database status) and the "AI-Assisted" label from the rule-based fabric ranking (#10).
* The PDF now prints the stored, validated pieces (#8).

## Claims that remain safe

See [LIMITATIONS_AND_CLAIMS.md](LIMITATIONS_AND_CLAIMS.md). In short: an integrated, tested prototype
implements photo → AI suggestion → mandatory confirmation → validated measurements → parametric pattern →
seam allowances → geometry validation → heuristic nesting → scale-verified 1:1 PDF; only the design
suggestion uses machine learning.
