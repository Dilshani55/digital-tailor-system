# Fabric selection with crisp AHP and TOPSIS

Implemented on 4 October 2026. The default workflow compares published measurements of five cotton knit samples or thirteen cotton woven samples using the user's explicitly entered preferences. [Source tables and sampling scope](published-fabric-data.md). The optional expert-profile file remains empty; user answers are never presented as expert judgments.

## Research basis and adaptation

Hong et al. (2018), [DOI 10.1177/0040517517729383](https://doi.org/10.1177/0040517517729383), provide a directly relevant fabric decision-support precedent using **Fuzzy AHP and Fuzzy TOPSIS**. This project implements a **crisp adaptation** with numeric observations and reciprocal comparisons, not their fuzzy model, participant data or experimental results. The distinction must remain in the thesis. See the [literature audit](FABRIC_RECOMMENDATION_RESEARCH.md) for textile criteria sources and access limits.

For the AHP calculation, see T. L. Saaty (2008), “Decision making with the analytic hierarchy process,” *International Journal of Services Sciences*, 1(1), 83–98, [DOI 10.1504/IJSSCI.2008.017590](https://doi.org/10.1504/IJSSCI.2008.017590) (publisher bibliographic record reviewed). An accessible primary methods/software paper is Françozo et al. (2023), “A web-based software for group decision with analytic hierarchy process,” *MethodsX*, 11, 102277, [full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC10372897/). Its background covers power iteration, consistency checking and geometric aggregation of judgements. Our code uses full pairwise matrices, not that software's reduced-comparison AHP-Express procedure. The RI constants explicitly use the **Saaty & Vargas (2012)** column of its Table 2: orders 3–10 use 0.52, 0.89, 1.11, 1.25, 1.35, 1.40, 1.45, 1.49.

TOPSIS follows vector normalisation, weighted Euclidean distances and relative ideal closeness. H.-S. Shih, H.-J. Shyur and E. S. Lee (2007), “An extension of TOPSIS for group decision making,” *Mathematical and Computer Modelling*, 45(7–8), 801–813, [DOI 10.1016/j.mcm.2006.03.023](https://doi.org/10.1016/j.mcm.2006.03.023), discusses these choices. The publisher abstract and indexed formula extracts were accessible; full publisher access was unreliable. This implementation uses one decision matrix and externally aggregated AHP weights; it does not reproduce their internal group TOPSIS extension.

## Actual algorithm

1. **Check drafting support.** The current T-shirt engine uses knit; the blouse engine uses woven. Exclude fabrics unsupported by that block. This is a project constraint, not a universal claim that blouses cannot be knit.
2. **Select comparable alternatives.** The default T-shirt workflow uses the five Y1 cotton knit samples of Salopek Čubrić et al. (2022); blouses use the thirteen cotton woven samples of Alam & Ghosh (2013). Rank each complete study group separately. Do not mix protocols or give their values to generic fabric families. If a recorded expert profile is configured, it must match all four design attributes and fit exactly; its catalogue coverage is separately validated.
3. **Collect and validate priorities.** The default workflow requires an explicit benefit/cost goal for all three measured properties and the three pairwise importance answers. Every sample has all observations with units, protocols and source tables. No midpoint, imputation or adjective score is used. Optional expert profiles instead require 2–10 criteria and recorded expert matrices.
4. **Calculate AHP weights.** The user supplies three ordered pairs on the 1, 3, 5, 7, 9 scale (or reciprocal values); the server builds the reciprocal matrix. For optional expert profiles, each recorded expert supplies a positive reciprocal matrix `A`, diagonal 1, entries in `[1/9, 9]`. Obtain the principal eigenvector by power iteration, normalised to sum to 1. Calculate `lambda_max = mean((A w)_i / w_i)`, `CI = (lambda_max - n)/(n - 1)`, and `CR = CI / RI_n`. Reject `CR > 0.10`. For two criteria, a reciprocal matrix has `CR = 0`. Validate individuals before combining them. For an optional profile with multiple experts, take the equal-participant geometric mean of each matrix entry and recalculate weights and group CR. Equal participant influence is a declared project convention, not a learned textile fact.
5. **Prepare the decision matrix.** Benefit means larger is preferred; cost means smaller is preferred. For an explicitly recorded target, use absolute deviation `abs(observed - target)` as a cost. This target-distance transformation is a project adaptation; the target and preference source must be documented. GSM, stretch and drape are not automatically treated as “more is better.”
6. **Apply TOPSIS.** For each column `j`, use `r_ij = x_ij / sqrt(sum_i x_ij²)` and `v_ij = w_j r_ij`. Form the positive and negative ideals using column maxima/minima according to benefit/cost direction. Compute `D_i+` and `D_i-` as Euclidean distances. The coefficient is `C_i = D_i- / (D_i+ + D_i-)`.
7. **Return the comparison and evidence.** Order by descending closeness, expose ranks, sample records, weights, consistency ratios, normalised values, ideals and distances. Recommend the highest rank, including ties within `1e-10`; do not force two or four winners. Sample IDs stabilise equal scores. The UI requires an explicit choice. Pattern generation recomputes the user comparison on the server and saves provenance, observations, preferences, dataset hash, design, fit, weights and audit in fabric_selection_snapshot.

Constant criteria contribute no distance; an all-zero column normalises to zero. When no criterion distinguishes the samples, the coefficient is undefined: return `null`, status `indistinguishable` and no recommendation. A coefficient of 1 means closest among these assessed alternatives under these preferences; it is not 100% suitability, confidence, accuracy or a fit guarantee. Results depend on the alternative set; adding/removing samples can change TOPSIS ranks.

## What counts as input data

| Input | Acceptable record | What does not supply it |
|---|---|---|
| Sample identity | Supplier/style/lot or study sample code, composition and construction specification, with a traceable record | A generic family name such as “rayon” |
| Physical observation | Numeric result with units, conditions and protocol from a material test, supplier technical sheet or published sample table | A catalogue adjective or estimated range midpoint |
| Assessed preference | Documented panel rating with defined anchors, protocol and sample identity, justified as an input scale | An invented “drape level 4” |
| Criterion direction/target | Current user's explicit property goals, or an optional recorded expert/design brief | Assuming lower GSM or higher stretch always wins |
| Criterion weights | Current user's three pairwise answers; optional profiles may instead hold identified, pseudonymised expert comparisons | Copying another study's coefficients or filling defaults |

Different test units or protocols block ranking. Equal strings are a metadata check, not proof that experiments are scientifically comparable. The researcher must check test conditions, assessment scales, sample identity and sources. Merely supplying a nonempty source string does not authenticate it. Keep raw measurements and original judgement forms outside the public catalogue; do not put personal expert details in source labels returned by the API.

Published measurements can be used for **the samples actually measured in that paper**, with the relevant table/sample identifiers. They cannot establish measurements for the app's generic fabric families or a locally bought cloth. In particular, the single-jersey derivatives in Mishra et al. do not provide a French Terry sample by renaming a derivative. Supplier data must likewise describe the actual sample under study.

## Optional expert profiles

Begin with the two knit alternatives for one supported T-shirt design and one fit. Identify one actual jersey sample and one French Terry sample, then select and justify criteria with your supervisor/expert. The template suggests air permeability and areal density only as editable fields; it supplies no objectives, weights, measurements or claimed expert answers. Replace/add criteria to match the study protocol.

From the repository root in PowerShell:

```powershell
backend\venv\Scripts\python.exe backend\tools\fabric_research_data.py --template t-shirt > "$env:TEMP\fabric-study.json"
```

Complete the file:

1. Record profile `id`, `source`, the exact `design` and `fit_preference`.
2. For each criterion, complete `id`, `label`, `unit`, `protocol`, supporting `source`, `objective` (`benefit`, `cost` or `target`) and `preference_source`. A target also needs a numeric `target` in the declared unit.
3. Record each expert's pseudonym, source form/session code and comparison matrix in the **same criterion order**. Diagonal values are 1. For example, if the respondent says criterion A is moderately more important than B, record 3 in row A/column B and 1/3 in row B/column A. This is an elicitation example, not a production judgement. Add each respondent as a separate entry; the software combines them.
4. Record each sample's existing catalogue `fabric_id`, unique `sample_id` and descriptive `label`. Every `values[criterion_id]` needs numeric `value`, the matching `unit` and `protocol`, and the observation's `source` (table/row, test record or supplier specification).

PowerShell 5 may create a UTF-16 file with `>`; use a UTF-8 editor save or an explicit UTF-8 write before validating. A portable PowerShell command is:

```powershell
backend\venv\Scripts\python.exe backend\tools\fabric_research_data.py --template t-shirt | Set-Content -LiteralPath "$env:TEMP\fabric-study.json" -Encoding utf8
backend\venv\Scripts\python.exe backend\tools\fabric_research_data.py --validate "$env:TEMP\fabric-study.json"
```

An incomplete template fails validation. A completed file prints calculated weights, CR and sample coefficients; this checks structure/arithmetic, not physical suitability. Once approved for the study, set `FABRIC_RESEARCH_DATA_PATH` in `backend/.env` to its absolute path and restart the backend. The optional [fabric_research.json](../backend/app/data/fabric_research.json) remains empty; published samples live in the separate [published_fabric_samples.json](../backend/app/data/published_fabric_samples.json) and require live user priorities. The server reads the configured file per request; subsequent edits must be validated and the study version recorded before evaluation.

Production never loads synthetic fixtures from `backend/tests/`. The old feature-string endpoint and its additive scoring path have been removed: requests need `confirmed_attributes`. Catalogue descriptions remain visible as general guides and are not used as observations.

## API and implementation

`POST /api/fabric/recommend` returns `ranking_status`:

| Status | App behaviour |
|---|---|
| `awaiting_preferences` | Published samples available; user goals and comparisons required, no scores or weights |
| `invalid_preferences` | Incomplete/inconsistent user answers, HTTP 422; keep the answers for correction |
| `awaiting_data` | Explicit expert-profile mode has no matching profile; all compatible choices visible, no scores or recommendations |
| `invalid_data` | Incomplete/inconsistent data; ranking blocked, compatible choices visible, diagnostic in `ranking_audit.data_error` |
| `indistinguishable` | Data complete but no ideal separation; no winner, compatible choices visible |
| `ranked` | Ranked identified samples, relative coefficients and full calculation audit |

`topsis_closeness` is in `[0,1]` only for ranked results. Legacy `recommendation_score` stays `null` and `score_reasons` stays empty, so clients cannot mistake the old 0–100 point score for the new coefficient. `View Details` shows observed sample values, sources, weights and consistency. Generic properties are separately identified as catalogue descriptions.

- [fabric_mcda.py](../backend/app/logic/fabric_mcda.py): arithmetic and consistency checks.
- [fabric_research.py](../backend/app/logic/fabric_research.py): profile matching, provenance/comparability metadata and observation validation.
- [published_fabrics.py](../backend/app/logic/published_fabrics.py): within-study source validation, live user elicitation and source-specific sample definitions.
- [fabric_selection.py](../backend/app/logic/fabric_selection.py): drafting compatibility and API result construction.
- [fabric_research_data.py](../backend/tools/fabric_research_data.py): blank template and study validation.

## Verification versus research evaluation

Arithmetic tests use explicitly synthetic fixtures and hand-computable comparisons. Published-data tests additionally anchor transcribed values to the source tables, check sample identity and study separation, reject incomplete/inconsistent user preferences, prevent client observation injection and verify server recomputation and saved evidence. UI tests cover explicit answers, no silent defaults, correction, selection, stale responses and retained choices. These software checks are not evidence of garment suitability.

For research evaluation, collect independent expert/participant assessments or local measurements and garment trials. Freeze dataset versions, user elicitation procedure and alternative sets before evaluating outcomes. Report participants, samples, protocols, ranking agreement and sensitivity to weights/alternative sets. Published property data and AHP consistency do not prove garment fit or independent recommendation accuracy; neither has been measured for this module yet.
