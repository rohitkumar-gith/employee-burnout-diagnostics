# Verification Report

Every figure below is produced by `analysis.py` (see `outputs/results.json`). Statuses describe the ORIGINAL paper/dashboard claims.

| # | Claim (original) | Where | Calculated result | Status |
|---|---|---|---|---|
| 1 | Dataset has 1,470 records and 31 variables | Paper §4, Abstract | 1470 x 31 | Supported |
| 2 | Dataset has no missing values | Paper §4 | 0 missing cells; 0 duplicate rows | Supported |
| 3 | Attrition rate near 16.12% | Task brief | 237/1470 = 16.12% | Supported |
| 4 | Overtime associated with slightly higher engagement | Paper Abstract, §7.1, §8 | Overtime n=416 mean 2.784 vs no-overtime n=1054 mean 2.699; diff +0.085 (95% CI +0.028 to +0.142); Welch p=0.003; Holm p=0.030; d=0.17 | Supported (statistically significant, small effect; association only) |
| 5 | Overtime engagement is higher because involved employees volunteer for challenging projects | Paper §7.1 | Not tested by any analysis | NOT SUPPORTED -> relabelled as an untested hypothesis |
| 6 | No evidence for a 3.5-year promotion cliff; engagement 'statistically flat' | Paper Abstract, §7.2 | Spearman rho=0.025, p=0.34; >=4 vs <=3 yrs diff +0.001 (95% CI -0.058 to +0.061), p=0.96 | Supported as absence of evidence (reworded; not proof of no effect) |
| 7 | 'Exploratory regression' was used for promotion timing | Paper §7.2 | Original code contained no regression; a simple OLS (slope +0.0013, 95% CI -0.0067 to +0.0093) is now actually computed in analysis.py | Now supported (was not backed by code) |
| 8 | Commute distance affects burnout score by mathematical design | Paper Abstract, §7.3 | Distance = up to 20 of 100 points; distance points account for about 12% of score variance; Spearman distance-vs-score rho=0.37 | Supported (mechanical, not independent evidence) |
| 9 | Attrition 7.4% in lowest score tertile | Paper Abstract, §7.4 | 38/513 = 7.41% (95% CI 5.4-10.0) | Number reproduces |
| 10 | Attrition 29.6% in highest score tertile | Paper Abstract, §7.4 | 144/486 = 29.63% (95% CI 25.7-33.8) | Number reproduces |
| 11 | Score 'predicts' attrition / 'highly significant predictive validity' / 'proves a highly effective triage tool' | Paper Abstract, §7.4, §8, §10 | Chi-square p=<0.001 (association); in-sample AUC=0.70 vs overtime-only 0.65; no held-out or longitudinal data; 81% of highest third work overtime | NOT SUPPORTED as prediction -> reworded as in-sample association |
| 12 | Tertile groups (thresholds) were undefined | Paper §7.4 | Defined: 33.3/66.7th percentiles = 26.43 / 44.29; ties to lower group; sizes 513/471/486 | Now documented and reproducible |
| 13 | Welch t-tests, contingency analysis and relative risk were performed | Paper §6 | Original dashboard code computed none of these; analysis.py now performs them (plus Mann-Whitney, Kruskal-Wallis, chi-square, Wilson CIs, Holm correction) | Now supported (was not backed by code) |
| 14 | Distance penalty uses fixed bounds 1 and 29 (paper) vs min-max (code) | Paper App. A.1 vs app.py | Observed min/max = 1/29; max |score difference| between old code, paper formula and final = 0.00 / 0.00; 0 scores changed | Resolved: fixed bounds, identical results on this data |
| 15 | Commute labels '<5m', '5-15m', '>15m' | app.py | Code placed 5 in Short and 15 in Medium; 65 employees at 5, 26 at 15; reclassified after fix: 0 | Labels were inaccurate -> corrected; no one changes group |
| 16 | Risk and priority category definitions | Paper §5, App. A.2 | Match code; counts Low/Medium/High = 756/588/126; Critical = 13 | Supported |
| 17 | Dataset 'represents' a high-pressure cybersecurity company (Palo Alto Networks) | Paper §1, §4 | Roles in data include Healthcare Representative, Laboratory Technician, Manufacturing Director, Research Scientist; no documentation; resembles a fictional IBM sample (record count matches, rows not compared) | NOT SUPPORTED -> neutral provenance wording |
| 18 | References (Bakker & Demerouti 2007; Marler & Boudreau 2017; Maslach & Leiter 2016) | Paper §11 | Authors, titles, journals, volume/issue/pages, years match Crossref records (3/3) | Metadata verified; content paraphrases NOT checked against full text |
| 19 | Attrition differs by department and career stage (new analysis) | Paper §7.6 | Dept chi-square p=0.005 (Holm 0.036); career stage p=<0.001 | Computed (not in the original paper) |
| 20 | Commute-group attrition gradient (new analysis) | Paper §7.5 | 13.8% -> 20.7%; raw p=0.022; Holm p=0.155 | Not significant after correction -> described as suggestive |

## Dashboard values vs paper/analysis values

Dashboard values were captured by executing `app.py`'s Executive Summary code with stand-in Streamlit/Plotly modules at default filters (`tests/dashboard_metrics_capture.py`). This is not a rendered-UI check.

| Metric | Dashboard shows | Analysis value |
|---|---|---|
| Total Workforce | 1,470 | 1,470 |
| Avg Engagement | 2.72 / 4.0 | 2.723 |
| Avg Burnout Score | 37.6 / 100 | 37.59 |
| Avg Satisfaction | 2.73 / 4.0 | 2.729 |
| Avg Work-Life Balance | 2.76 / 4.0 | 2.761 |
| Attrition Rate | 16.1% | 16.12% |
| Critical-Priority Flags | 13 | 13 |

## Multiple-comparison family (Holm)

| Test | raw p | Holm p |
|---|---|---|
| Overtime vs engagement (Welch t) | 0.003 | 0.030 |
| Promotion wait vs engagement (Spearman) | 0.341 | 1.000 |
| Promotion >=4 vs <=3 yrs, engagement (Welch t) | 0.961 | 1.000 |
| Tenure vs engagement (Spearman) | 0.671 | 1.000 |
| Engagement across departments (Kruskal-Wallis) | 0.709 | 1.000 |
| Engagement across career stages (Kruskal-Wallis) | 0.539 | 1.000 |
| Engagement across commute groups (Kruskal-Wallis) | 0.885 | 1.000 |
| Attrition across score thirds (chi-square) | <0.001 | <0.001 |
| Attrition across departments (chi-square) | 0.005 | 0.036 |
| Attrition across career stages (chi-square) | <0.001 | <0.001 |
| Attrition across commute groups (chi-square) | 0.022 | 0.155 |

## What was NOT tested or could not be verified

- **The Streamlit app was not run.** Streamlit, Plotly and statsmodels could not be installed in the verification environment (the package index was blocked by the network policy, HTTP 403). Instead, every page's Python/pandas logic was executed against stand-in modules (`tests/smoke_app_with_stubs.py`); this catches NameErrors and pandas errors but not rendering, layout, or invalid Plotly arguments. Please run `streamlit run app.py` yourself.
- `requirements.txt` minimum versions for streamlit, plotly and statsmodels are untested. `width="stretch"` (already used in your original code) needs a recent Streamlit release; the original docs pinned streamlit 1.32.0, which is unlikely to support it.
- Reference *content* (how Section 3 paraphrases each source) was not checked against full texts; only bibliographic metadata was verified.
- Dataset provenance: resemblance to a fictional IBM sample dataset rests on matching record count and a documentation page; no row-level comparison was made.
- The PDF was produced by LibreOffice from the DOCX; Word's pagination may differ slightly.
- No sensitivity analysis of the burnout-score weights, no multivariable models, and no out-of-sample/longitudinal validation were performed.
