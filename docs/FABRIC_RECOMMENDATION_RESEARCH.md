# Fabric recommendation: research evidence and implementation audit

Reviewed: 4 October 2026 (Asia/Colombo).

This is a literature and source-code audit, not an experimental validation result. The project owner confirmed that no fabric-selection references or expert notes are currently available to supply as project evidence.

## Implementation update (4 October 2026)

The additive point scoring described in this baseline audit has now been removed, including the legacy feature-string ranking path. The active module implements **crisp AHP-weighted TOPSIS** with sourced sample observations, recorded expert matrices, consistency checks and an auditable result. It is an adaptation, not a reproduction of Hong's fuzzy algorithm. See [the implemented method and data collection instructions](fabric-ranking-algorithm.md).

The default workflow now uses published measurements for five cotton knit samples and thirteen cotton woven samples, together with the user's live goals and three pairwise importance answers. Source tables and scope are in [published-fabric-data.md](published-fabric-data.md). The user answers are not expert judgments. Optional expert profiles remain empty. Independent textile/garment evaluation is still pending; the sections below preserve the removed additive-score baseline.

## Baseline finding before the algorithm update

The recommender audited before the update had a documented computational procedure, but its numerical preferences were not derived from a published method, measured fabric data, or recorded expert judgments. Published research supports investigating fabric construction, stretch/recovery, drape and comfort as selection criteria. It does not establish the project's `+5`, `+10`, `+15`, baseline `60`, or recommendation threshold `60`.

A defensible research account needs three separate forms of evidence: sources supporting the criteria; documented data and a method producing the ranking; and an evaluation on this project's designs and fabrics. Adding citations supplies the first part only.

## Verified primary sources

### R1. A directly relevant fabric recommendation study

Y. Hong, X. Zeng, P. Bruniaux, Y. Chen, and X. Zhang, “Development of a new knowledge-based fabric recommendation system by integrating the collaborative design process and multi-criteria decision support,” *Textile Research Journal*, vol. 88, no. 23, pp. 2682–2698, 2018. Published online 4 October 2017. DOI: [10.1177/0040517517729383](https://doi.org/10.1177/0040517517729383).

- Verified access: publisher abstract and bibliographic information; journal full text was not available through the reviewed publisher page.
- Relevant contribution: a decision hierarchy links consumer requirements, fabric properties, evaluation scales and alternatives. Fuzzy AHP derives criterion weights and Fuzzy TOPSIS produces a ranking using elicited evaluations.
- Application: a methodological reference for redesigning the recommender. The project does not reproduce this fuzzy method or its participant study; its new crisp adaptation still needs genuine inputs.
- Boundary: the paper does not validate our catalogue, our point additions, or the Jersey/French Terry result shown in the app.

### R2. Accessible methodological detail from the original researcher

Y. Hong, *Development of an Intelligent Knowledge-Based Personalized Garment Design Support System for People with Atypical Morphology*, doctoral thesis, Université de Lille, 2018; defended 20 April 2018. [University-hosted full text](https://pepite-depot.univ-lille.fr/LIBRE/EDSPI/2018/50376-2018-Hong.pdf).

- Sections inspected: §2.2.2 (fabric selection procedure) and §4.2 (data acquisition, weighting and validation).
- The procedure uses participant judgments and fabric evaluations; the case study evaluates summer-dress alternatives and checks recommendations against an additional consumer group.
- This is an accessible primary methodological source. Its garments, participants, fabrics and resulting weights cannot be treated as observations from this project's blouse/T-shirt system.

### R3. Garment drape and measurable fabric properties

R. Sanad and T. Cassidy, “Investigating garment drape behaviour,” *Journal of Fiber Bioengineering and Informatics*, vol. 8, no. 1, pp. 47–56, 2015. DOI: [10.3993/jfbi03201505](https://doi.org/10.3993/jfbi03201505). [University repository and accepted manuscript](https://eprints.whiterose.ac.uk/id/eprint/84213/).

- Verified access: repository metadata and the accepted manuscript; abstract and opening discussion inspected.
- Relevant contribution: measured weight, bending behaviour and extensibility are related to garment drape assessments.
- Application: supports treating drape/mechanical behaviour as a criterion, rather than inferring garment appearance from a fabric name alone.
- Boundary: it does not supply our ordinal drape levels `1..5`, the cutoff `3`, or a `+5` loose-fit reward.

### R4. Knit structure and thermo-physiological properties

R. Mishra et al., “Thermo physiological comfort of single jersey knitted fabric derivatives,” *Fashion and Textiles*, vol. 8, article 40, 2021. Published 15 November 2021. DOI: [10.1186/s40691-021-00266-5](https://doi.org/10.1186/s40691-021-00266-5).

- Verified access: open publisher full text; abstract, ANOVA discussion and conclusions inspected.
- Relevant contribution: changing knit structure, yarn characteristics and relaxation affects areal density, thickness, air permeability and thermal/moisture behaviour in the tested samples.
- Application: supports specifying construction and comfort criteria with identifiable data.
- Boundary: a generic label such as “cotton” or “High breathability” is not a measurement of the selected cloth. The study does not establish this catalogue's GSM ranges or recommendation weights.

### R5. Jersey stretch and recovery depend on composition and structure

E. Eltahan, “Effect of Lycra Percentages and Loop Length on the Physical and Mechanical Properties of Single Jersey Knitted Fabrics,” *Journal of Composites*, vol. 2016, article 3846936, 2016. Published 14 August 2016. DOI: [10.1155/2016/3846936](https://doi.org/10.1155/2016/3846936).

- Verified access: open publisher text; abstract and introduction inspected.
- Relevant contribution: experiments compare cotton and cotton/spandex jerseys and examine how composition and loop length affect extension and recovery.
- Application: supports considering both stretch and recovery for fit-related requirements.
- Boundary: it does not establish a universal stretch value for every jersey, or validate the project's `+5` close-fit weight.

### R6. Industry technical guidance on knit constructions and end uses

Cotton Incorporated, “Single & Double Knits,” *CottonWorks*, undated, accessed 4 October 2026. [Technical learning resource](https://cottonworks.com/learning-hub/knitting/single-and-double-knits/).

- Verified sections: Jersey and French Terry.
- Jersey is associated with T-shirts and comes in differing weights. French Terry is described as a knit construction used for sweatshirts, sweatpants and layering garments, also in differing weights.
- Application: supports catalogue construction descriptions and the general association between jersey and T-shirts.
- Boundary: this is industry guidance, not a peer-reviewed comparison validating our rankings. It does not prove that French Terry is always heavy, or that every jersey is preferable to every French Terry for every T-shirt.

## Baseline code and screenshot calculation before the update

In both versions, the UI sends the user-confirmed garment attributes and fit preference to the design-aware route. It does not send body measurements to the fabric-ranking endpoint.

| Component | Actual role |
|---|---|
| [FabricRecommendation.jsx](../frontend/src/components/FabricRecommendation.jsx) | Sends confirmed attributes and fit; displays compatible, recommended and incompatible catalogue entries. |
| [fabric.py](../backend/app/routes/fabric.py) | The `confirmed_attributes` request uses `recommend_for_design`. |
| [fabric_selection.py](../backend/app/logic/fabric_selection.py) | Previously applied construction compatibility, additive point rules and recommendation limits; now replaced by AHP/TOPSIS. |
| [fabric_recommendation.py](../backend/app/logic/fabric_recommendation.py) | Contains manually compiled fabric descriptions and properties; previously also held a legacy point recommender, now removed. |

The removed legacy recommender differed from the algorithm used by the screenshot. Tests of legacy crop-top or bell-sleeve recommendations do not establish support for those designs in the active pattern workflow.

For the displayed T-shirt, round-neck, short regular sleeve and close fit, the baseline calculation was:

| Catalogue entry | Computation | Score |
|---|---|---:|
| Cotton Jersey Knit | `60 + 10` (medium-weight knit) `+ 5` (close-fit stretch preference) | 75 |
| French Terry Knit | `60 - 5` (heavy-knit penalty) `+ 5` (close-fit stretch preference) | 60 |

This result was reproduced through the pre-change `recommend_for_design` function. It demonstrates the computation for that input; it is not an observed textile-suitability result, probability, or accuracy percentage.

## Rule-to-evidence mapping

“Criterion supported” below means that the source establishes the relevance of a property. It does not mean that the current numeric rule or its fabric labels have been validated.

| Baseline rule | Evidence identified | Research status of the baseline rule |
|---|---|---|
| T-shirt requires knit; blouse requires woven | R6 supports jersey/T-shirt association; the hard restriction follows this project's chosen drafting blocks. | Project compatibility constraint, not a universal textile prohibition. |
| Puff sleeve: drape ≤3 and light/medium gives +15; fluid fabric −10; heavy fabric −10 | R3 establishes drape relevance, but no directly applicable gathered-sleeve comparison was verified here. | Hypotheses and point magnitudes need evidence. |
| Blouse: drape levels 2–4 gives +5 | R3 supports investigating drape. | The range and reward remain project choices. |
| T-shirt: medium knit +10, heavy knit −5 | R5/R6 support jersey end use; R4 supports examining physical and comfort properties. | The categorical weights, penalty and actual fabric specifications need substantiation. |
| Square/V neck: drape ≤3 gives +5 | No directly applicable neckline comparison was verified in this search. | Unsupported project preference until justified and tested. |
| Sleeveless: “High/Very High” breathability gives +5 | R4 supports a comfort/air-permeability criterion. | The catalogue's qualitative labels and reward are unvalidated. |
| Close fit: stretch gives +5 | R5 supports examining extension and recovery. | The reward is uncalibrated; direction, recovery and sample-specific stretch are missing. |
| Loose fit: drape ≥4 gives +5 | R3 supports a drape criterion. | The cutoff and reward are unvalidated. |
| Sheer −15; semi-sheer −5; show lining warning | The current pattern has no lining pieces. | Construction limitation can be explained; the ranking penalties are project choices. |
| Start at 60; recommend at ≥60; normally pick 2–4 | No source-derived calibration was found. The code can take the top two even below the threshold. | Software selection policy, not an established suitability threshold. |

The catalogue's `TRAITS` values, GSM ranges and categorical descriptions are not sample-level test data. Fibre names such as rayon also do not uniquely identify a woven/knit construction. Each assessed alternative needs an identifiable fabric specification if numerical physical properties are to be used.

## A research procedure that can be evaluated

The following describes the remaining empirical study. The computational redesign is now implemented; genuine data collection and evaluation are not complete.

1. **Define the decision and scope.** Record the supported garment design, desired fit, target use and the actual fabric alternatives being compared. Separate drafting compatibility from textile preference.
2. **Define and source the criteria.** For each alternative, record construction, composition, weight, relevant stretch/recovery and drape/comfort information. Attach a source, test method or documented assessment. Mark unavailable values as missing.
3. **Specify how preference weights are obtained.** R1/R2 offer a documented participant-driven approach. Adopting it requires genuine judgments and fabric evaluations; copying its name or its case-study coefficients is insufficient. If a simpler rule system is retained, identify which relationships have direct support and disclose every unvalidated preference.
4. **Separate development from evaluation.** Freeze the criteria, rules/weights and dataset version before evaluating held-out designs or independent judgments. Avoid using the same answers both to build a ranking and to claim that the ranking is correct.
5. **Evaluate the claimed result.** Record which fabrics reviewers independently regard as suitable, their reasons, and any disagreements. Report agreement/precision for a declared recommendation set; use ranking metrics only if genuine ranked or graded reference judgments exist. Report sample sizes and uncertainty. Physical comfort, fit or performance claims require suitable garment/material tests beyond ranking agreement.
6. **Check robustness.** Record how conclusions change with reasonable alternative weights and fabric variants. Keep contradictory cases rather than selecting only successful examples.

Software regression tests remain useful for API behaviour, deterministic arithmetic, compatibility constraints and explanation consistency. They do not substitute for the fabric data and independent evaluation above.

## Completion requirements for this module

| Requirement | Current evidence |
|---|---|
| Relevant primary research identified | R1–R5; R6 provides supplementary industry guidance. |
| Current algorithm and unsupported numerical assumptions identified | Source-code audit and mapping above. |
| Sources tied to actual catalogue fabric specifications | Published measurements are tied to 18 identified research sample IDs; generic catalogue types remain unranked. [Source tables](published-fabric-data.md). |
| Preference weights obtained through a documented process | Live user goals and three pairwise comparisons are required, consistency checked and saved; they are not expert judgments or validation participants. |
| AHP/TOPSIS or another justified redesign implemented | Crisp AHP/TOPSIS is implemented; see the method document. No fuzzy reproduction or empirical validation is claimed. |
| Independent validation on this project's recommendations | Not established. |

Use the sources to design and justify a method, then evaluate the implementation. Do not describe the removed additive score as AHP/TOPSIS, the new crisp method as a fuzzy reproduction, or either result as empirically validated solely because references and software tests exist.

## Published data implementation (4 October 2026)

The active sources are Salopek Čubrić et al. (2022), *Material and Structural Functionalization of Knitted Fabrics for Sportswear*, [full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC9104909/), Tables 4–6 (Y1 cotton only), and Alam & Ghosh (2013), *Selection of Cotton Fabrics for Optimal Comfort Properties Using Multi-Criteria Decision Making*, [publisher](https://jtatm.textiles.ncsu.edu/index.php/JTATM/article/view/3836), Tables 4 and 6. Unlike the earlier criteria-only literature sources, these supply the numerical observations actually used in the app. The app does not reuse their rankings as an accuracy benchmark, or their weights as this user's answers. [Transcriptions and protocols](published-fabric-data.md).
