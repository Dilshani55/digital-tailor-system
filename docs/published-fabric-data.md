# Published fabric measurements used by the app

සිංහලෙන් භාවිත කරන විදිහ: **Fabric & fit** පියවරේ fit එක තෝරන්න. ඉන්පසු fabric ගුණාංග තුන සඳහා කැමැත්ත සහ වැදගත්කම සසඳන ප්‍රශ්න තුනට පිළිතුරු දෙන්න. **Compare fabric samples** ඔබන්න. **View Details** තුළ මැනපු අගයන්, source එක සහ ඔබේ තේරීම් අනුව ගණනය කළ weights පෙන්වනවා. Sample එක තෝරා pattern එක save කළාම ඒ විස්තරත් save වෙනවා. මේවා ඔබේ preferences; expert validation තවම සිදු කර නැහැ.

Implemented 4 October 2026 after choosing published samples plus the user's own preferences. Data is transcribed from numerical tables; nothing is estimated from texture photographs, generic fabric descriptions or graph pixels. The [JSON dataset](../backend/app/data/published_fabric_samples.json) records each sample's ID, source table, unit and protocol. The API records its SHA-256 in the saved selection.

## Knit group: five cotton samples

Salopek Čubrić, I., Potočić Matković, V. M., Pavlović, Ž., & Pavko Čuden, A. (2022). *Material and Structural Functionalization of Knitted Fabrics for Sportswear*. Materials, 15(9), 3306. [Full text and tables](https://pmc.ncbi.nlm.nih.gov/articles/PMC9104909/), [DOI](https://doi.org/10.3390/ma15093306). CC BY 4.0.

Only Y1 (100% cotton) is included. Mass comes from Table 4, thermal resistance from Table 5 and airflow from Table 6. The decimal comma in Y1 ST mass, `267,35`, is transcribed as `267.35`.

| Original ID | Structure | Mass (g/m²) | Airflow (L/min) | Thermal resistance (m² K/W) |
|---|---|---:|---:|---:|
| Y1 SP | Single plain | 260.38 | 140.12 | 0.0444 |
| Y1 SM | Single miss | 287.17 | 119.72 | 0.0504 |
| Y1 ST | Single tuck / piqué | 267.35 | 206.14 | 0.0424 |
| Y1 DP | Double plain | 433.40 | 82.44 | 0.0464 |
| Y1 DM | Double Milano rib | 430.49 | 77.14 | 0.0419 |

Within this group, air testing uses ISO 9237, Air-Tronic B, 50 Pa and 20 cm². The paper's PA samples used 5 cm²; they are excluded. Mass uses 100 × 100 mm specimens and a Kern ALJ 220-4 balance. Thermal resistance uses an ISO 11092 sweating guarded hotplate at 20 °C, 65% RH and 1 m/s airflow. The fabrics were knitted on a 12-gauge machine. These values do not describe every commercial cotton jersey or French terry.

## Woven group: thirteen cotton samples

Alam, M. S., & Ghosh, A. (2013). *Selection of Cotton Fabrics for Optimal Comfort Properties Using Multi-Criteria Decision Making*. Journal of Textile and Apparel, Technology and Management, 8(3). [Publisher record](https://jtatm.textiles.ncsu.edu/index.php/JTATM/article/view/3836), [paper](https://jtatm.textiles.ncsu.edu/index.php/JTATM/article/download/3836/2532/20512).

Mass and thickness come from Table 4; measured thermal resistance comes from Table 6 (both PDF page 7). The original serial numbers are preserved. IDs F01–F13 are app display labels.

| Original serial number | Weave | Mass (g/m²) | Thickness (mm) | Thermal resistance (m² K/W) |
|---|---|---:|---:|---:|
| 1 | 3/1 twill | 151 | 0.44 | 0.0097 |
| 2 | 3/1 twill | 169 | 0.32 | 0.0061 |
| 3 | 3/1 twill | 534 | 0.95 | 0.0133 |
| 4 | Plain | 173 | 0.37 | 0.0075 |
| 5 | Plain | 151 | 0.28 | 0.0060 |
| 6 | Plain | 144 | 0.23 | 0.0049 |
| 7 | Plain | 161 | 0.31 | 0.0064 |
| 8 | Plain | 166 | 0.29 | 0.0059 |
| 9 | 2/1 twill | 292 | 0.42 | 0.0077 |
| 10 | 3/1 twill | 210 | 0.32 | 0.0047 |
| 11 | 2/2 twill | 215 | 0.46 | 0.0079 |
| 12 | 2/2 twill | 211 | 0.49 | 0.0091 |
| 13 | 4 end satin | 212 | 0.47 | 0.0085 |

The study reports a GSM cutter and ALAMBETA thermal measurements. Thickness test pressure is not specified, so the app retains that limitation and compares only this study's samples. Calculated porosity and cover factor are not substituted for measured airflow. The study's original cold-climate weights and published rankings are not reused as this user's preferences or our validation results.

## What the implemented comparison establishes

The app first checks its drafting support: T-shirt → knit group; blouse → woven group. This construction filter is an implementation constraint. It does not prove fabric stretch, drape, recovery, sewability or physical fit. Samples from the two studies are never mixed in one TOPSIS matrix.

The user explicitly selects a direction for each of three properties and answers the three pairwise importance questions. AHP calculates their weights and rejects inconsistent answers; TOPSIS compares all samples in the chosen study. No default equal weights are silently assigned. The UI shows sample-specific observations and sources, while the ten general catalogue types remain separate unranked choices. Paper samples are research alternatives, not a supplier inventory.

On generation, the server recomputes the comparison and saves the selected sample, observations, source, dataset hash, user choices, design, fit, AHP matrix/weights/consistency and TOPSIS audit in `fabric_selection_snapshot`. The saved pattern screen displays the source and priorities. A manual sample choice is recorded as manual, without a claimed preference ranking.

Published data and working code make this a reproducible decision-support implementation. Independent tailor/participant comparison, local sample measurements and garment trials remain future evaluation; no ranking accuracy, comfort percentage or fit guarantee is claimed. Run the dataset structure check from the repo root:

```powershell
backend\venv\Scripts\python.exe backend\tools\fabric_research_data.py --published
```
