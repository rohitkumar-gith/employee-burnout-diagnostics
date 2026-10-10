# Change Log

Originals are preserved in `backup/` (`app.py.original`, `paper.original.pdf`, `Palo_Alto_Networks.csv`).

## Calculations (`hr_analytics.py`, new)
- All formulas moved into a Streamlit-free module used by the dashboard, `analysis.py` and the tests, so the paper and dashboard cannot drift apart.
- **Burnout score / distance normalization.** The code used dataset min-max (+1e-9) while the paper's appendix used fixed bounds 1 and 29. Chose **fixed bounds (1, 29) with capping** so a score does not depend on the other rows in the file or filter. On the supplied CSV min=1 and max=29, so **no score changes** (verified). Weights (30/30/20/20) unchanged.
- **Commute categories.** Old labels (`<5m`, `5-15m`, `>15m`) contradicted the right-inclusive bins (5 -> Short, 15 -> Medium). Now `Short (1-5)`, `Medium (6-15)`, `Long (16+)` with open-ended outer bins (no one can be excluded). No employee changes group on this data. Same fix for career stages (`0-5`, `6-15`, `16+` years).
- **Attrition.** Robust 0/1 encoding for 1/0, Yes/No, True/False (case/whitespace-insensitive). Unsupported or missing values now raise a clear error instead of silently counting as "stayed". Attrition is never imputed.
- **Validation.** Early schema check (clear missing-columns error instead of `KeyError`); out-of-range/unexpected values (1-4 ratings, OverTime, BusinessTravel, negative distance) are reported; missing values are still imputed but the sidebar now discloses what was filled.
- **Group statistics.** Attrition tables always use group size as denominator and report counts, rates and Wilson CIs; score thirds use documented tie-safe thresholds.

## Dashboard (`app.py`)
- Uses `hr_analytics`; clear errors for bad CSVs; default CSV path is resolved relative to `app.py`.
- Metric tooltips, consistent precision, attrition shown as "k of n (x%)", disclaimer on key pages and sidebar.
- New "Observed Attrition by Burnout-Score Group" table/chart with the grouping rule stated.
- Honest labelling: "Prediction Engine" -> "Review Queue"; "High Flight Risk" -> "Elevated observed attrition"; recommendations rewritten as supportive follow-ups; segment-level cut-offs labelled as heuristics.
- Overtime insight now reports the *direction* with n, CI and p instead of only ever stating a decrease; commute insight and charts note the score's built-in dependence on distance.
- Axis fixes (department/role engagement bars no longer truncated at 1.5/2.0); chart titles/axes clarified; "Satisfaction Distribution" heading corrected; OLS trendlines fall back gracefully when statsmodels is missing; tenure slider no longer crashes when min = max; category orders consistent.
- Documentation tab: provenance statement rewritten (no claim that the data are Palo Alto Networks records), dependency list corrected, new Methodology & Limitations tab.
- Page title/sidebar no longer name a company.

## Analysis, tests, packaging
- `analysis.py`: regenerates every statistic (Welch t-test with CI and Cohen's d, Mann-Whitney, Kruskal-Wallis, chi-square + Cramer's V, Spearman, simple OLS, Wilson CIs, relative risk, in-sample AUC, Holm correction) into `outputs/`.
- `tests/test_hr_analytics.py`: 55 tests (score values/bounds, boundaries, attrition encodings, schema errors, empty frames, group counts/denominators, statistics, CSV baseline).
- `requirements.txt`: added **matplotlib** (needed by pandas Styler `background_gradient`, was missing), scipy; replaced the stale pins that the old Documentation tab listed.

## Paper
- Rebuilt from computed results by `build_paper.py` (no hand-copied numbers). Structure preserved; sections 1-12 kept.
- Removed/reworded: "predicts attrition", "proves ... highly effective", "validated attrition metrics", "rigorous verification", the cybersecurity/Palo Alto framing, the untested "voluntary involvement" explanation, and "absolutely no evidence" wording.
- Added: dataset validation table, provenance statement, score-component table, group definitions, Welch/CI/effect-size reporting, Holm-adjusted table, overtime-stratified attrition figure, limitations on mechanical dependence and cross-sectional design.
- Reported results that stand: 7.4% vs 29.6% (reproduced as 7.41% vs 29.63%), slightly higher engagement with overtime (confirmed), no promotion-timing effect (confirmed).
- References: metadata for all three verified against Crossref; paraphrases flagged for the author to confirm.
