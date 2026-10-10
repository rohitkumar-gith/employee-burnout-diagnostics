#!/usr/bin/env python3
"""Builds outputs/VERIFICATION_REPORT.md from outputs/results.json (+ dashboard_metrics.json).
Run after analysis.py. Every number below is read from the computed results."""
import json, os
OUT = "outputs"
R = json.load(open(f"{OUT}/results.json"))
DM = json.load(open(f"{OUT}/dashboard_metrics.json")) if os.path.exists(f"{OUT}/dashboard_metrics.json") else {}
D, O, T, SA, C = R["dataset"], R["overall"], R["tertiles"], R["score_audit"], R["commute"]
W, P, TEN = R["overtime_engagement"]["welch"], R["promotion"], R["tenure"]
TT = T["table"]; LOW, HIGH = TT[0], TT[2]
H = {r["Test"]: r for r in R["holm_family"]}
pv = lambda p: "<0.001" if p < 0.001 else f"{p:.3f}"
OT = {r["OverTime"]: r for r in R["attrition_by_overtime"]}

rows = [
 ("Dataset has 1,470 records and 31 variables", "Paper §4, Abstract", f"{D['rows']} x {D['columns']}", "Supported"),
 ("Dataset has no missing values", "Paper §4", f"{D['missing_cells']} missing cells; {D['duplicate_rows']} duplicate rows", "Supported"),
 ("Attrition rate near 16.12%", "Task brief", f"{O['attrition_left']}/{O['n']} = {O['attrition_rate_pct']:.2f}%", "Supported"),
 ("Overtime associated with slightly higher engagement", "Paper Abstract, §7.1, §8",
  f"Overtime n={W['n_a']} mean {W['mean_a']:.3f} vs no-overtime n={W['n_b']} mean {W['mean_b']:.3f}; diff {W['diff']:+.3f} (95% CI {W['ci_low']:+.3f} to {W['ci_high']:+.3f}); Welch p={pv(W['p'])}; Holm p={pv(H['Overtime vs engagement (Welch t)']['p_holm'])}; d={W['cohens_d']:.2f}",
  "Supported (statistically significant, small effect; association only)"),
 ("Overtime engagement is higher because involved employees volunteer for challenging projects", "Paper §7.1", "Not tested by any analysis", "NOT SUPPORTED -> relabelled as an untested hypothesis"),
 ("No evidence for a 3.5-year promotion cliff; engagement 'statistically flat'", "Paper Abstract, §7.2",
  f"Spearman rho={P['spearman_rho']:.3f}, p={P['spearman_p']:.2f}; >=4 vs <=3 yrs diff {P['threshold_test_le3_vs_ge4']['diff']:+.3f} (95% CI {P['threshold_test_le3_vs_ge4']['ci_low']:+.3f} to {P['threshold_test_le3_vs_ge4']['ci_high']:+.3f}), p={P['threshold_test_le3_vs_ge4']['p']:.2f}",
  "Supported as absence of evidence (reworded; not proof of no effect)"),
 ("'Exploratory regression' was used for promotion timing", "Paper §7.2", f"Original code contained no regression; a simple OLS (slope {P['ols']['slope']:+.4f}, 95% CI {P['ols']['slope_ci_low']:+.4f} to {P['ols']['slope_ci_high']:+.4f}) is now actually computed in analysis.py", "Now supported (was not backed by code)"),
 ("Commute distance affects burnout score by mathematical design", "Paper Abstract, §7.3",
  f"Distance = up to 20 of 100 points; distance points account for about {C['distance_points_share_of_score_variance_pct']:.0f}% of score variance; Spearman distance-vs-score rho={C['spearman_distance_vs_burnout_score']['rho']:.2f}", "Supported (mechanical, not independent evidence)"),
 ("Attrition 7.4% in lowest score tertile", "Paper Abstract, §7.4", f"{LOW['Left']}/{LOW['Employees']} = {LOW['AttritionRate_pct']:.2f}% (95% CI {LOW['CI95_low_pct']:.1f}-{LOW['CI95_high_pct']:.1f})", "Number reproduces"),
 ("Attrition 29.6% in highest score tertile", "Paper Abstract, §7.4", f"{HIGH['Left']}/{HIGH['Employees']} = {HIGH['AttritionRate_pct']:.2f}% (95% CI {HIGH['CI95_low_pct']:.1f}-{HIGH['CI95_high_pct']:.1f})", "Number reproduces"),
 ("Score 'predicts' attrition / 'highly significant predictive validity' / 'proves a highly effective triage tool'", "Paper Abstract, §7.4, §8, §10",
  f"Chi-square p={pv(T['chi_square_3x2']['p'])} (association); in-sample AUC={T['auc_score_in_sample']:.2f} vs overtime-only {T['auc_overtime_only_in_sample']:.2f}; no held-out or longitudinal data; {T['overtime_composition']['Highest third']['overtime_share_pct']:.0f}% of highest third work overtime",
  "NOT SUPPORTED as prediction -> reworded as in-sample association"),
 ("Tertile groups (thresholds) were undefined", "Paper §7.4", f"Defined: 33.3/66.7th percentiles = {T['t1']:.2f} / {T['t2']:.2f}; ties to lower group; sizes {LOW['Employees']}/{TT[1]['Employees']}/{HIGH['Employees']}", "Now documented and reproducible"),
 ("Welch t-tests, contingency analysis and relative risk were performed", "Paper §6", "Original dashboard code computed none of these; analysis.py now performs them (plus Mann-Whitney, Kruskal-Wallis, chi-square, Wilson CIs, Holm correction)", "Now supported (was not backed by code)"),
 ("Distance penalty uses fixed bounds 1 and 29 (paper) vs min-max (code)", "Paper App. A.1 vs app.py",
  f"Observed min/max = {SA['observed_distance_min']}/{SA['observed_distance_max']}; max |score difference| between old code, paper formula and final = {SA['max_abs_diff_original_code_vs_final']:.2f} / {SA['max_abs_diff_paper_formula_vs_final']:.2f}; {SA['n_scores_changed_vs_original_code']} scores changed", "Resolved: fixed bounds, identical results on this data"),
 ("Commute labels '<5m', '5-15m', '>15m'", "app.py", f"Code placed 5 in Short and 15 in Medium; {C['employees_at_distance_5']} employees at 5, {C['employees_at_distance_15']} at 15; reclassified after fix: {C['n_reclassified_vs_original']}", "Labels were inaccurate -> corrected; no one changes group"),
 ("Risk and priority category definitions", "Paper §5, App. A.2", f"Match code; counts Low/Medium/High = {O['burnout_risk_counts']['Low']}/{O['burnout_risk_counts']['Medium']}/{O['burnout_risk_counts']['High']}; Critical = {O['priority_counts']['Critical']}", "Supported"),
 ("Dataset 'represents' a high-pressure cybersecurity company (Palo Alto Networks)", "Paper §1, §4", "Roles in data include Healthcare Representative, Laboratory Technician, Manufacturing Director, Research Scientist; no documentation; resembles a fictional IBM sample (record count matches, rows not compared)", "NOT SUPPORTED -> neutral provenance wording"),
 ("References (Bakker & Demerouti 2007; Marler & Boudreau 2017; Maslach & Leiter 2016)", "Paper §11", "Authors, titles, journals, volume/issue/pages, years match Crossref records (3/3)", "Metadata verified; content paraphrases NOT checked against full text"),
 ("Attrition differs by department and career stage (new analysis)", "Paper §7.6", f"Dept chi-square p={pv(R['department']['attrition_chi2']['p'])} (Holm {pv(H['Attrition across departments (chi-square)']['p_holm'])}); career stage p={pv(R['career_stage']['attrition_chi2']['p'])}", "Computed (not in the original paper)"),
 ("Commute-group attrition gradient (new analysis)", "Paper §7.5", f"{C['groups'][0]['AttritionRate_pct']:.1f}% -> {C['groups'][2]['AttritionRate_pct']:.1f}%; raw p={pv(C['attrition_chi2']['p'])}; Holm p={pv(H['Attrition across commute groups (chi-square)']['p_holm'])}", "Not significant after correction -> described as suggestive"),
]

L = ["# Verification Report", "",
     "Every figure below is produced by `analysis.py` (see `outputs/results.json`). Statuses describe the ORIGINAL paper/dashboard claims.", "",
     "| # | Claim (original) | Where | Calculated result | Status |", "|---|---|---|---|---|"]
for i, (a, b, c, d) in enumerate(rows, 1):
    L.append(f"| {i} | {a} | {b} | {c} | {d} |")

L += ["", "## Dashboard values vs paper/analysis values", "",
      "Dashboard values were captured by executing `app.py`'s Executive Summary code with stand-in Streamlit/Plotly modules at default filters (`tests/dashboard_metrics_capture.py`). This is not a rendered-UI check.", "",
      "| Metric | Dashboard shows | Analysis value |", "|---|---|---|"]
pairs = [("Total Workforce", f"{O['n']:,}"), ("Avg Engagement", f"{O['engagement_mean']:.3f}"), ("Avg Burnout Score", f"{O['burnout_mean']:.2f}"),
         ("Avg Satisfaction", f"{O['job_satisfaction_mean']:.3f}"), ("Avg Work-Life Balance", f"{O['wlb_mean']:.3f}"),
         ("Attrition Rate", f"{O['attrition_rate_pct']:.2f}%"), ("Critical-Priority Flags", f"{O['priority_counts']['Critical']}")]
for k, v in pairs:
    L.append(f"| {k} | {DM.get(k, 'n/a')} | {v} |")

L += ["", "## Multiple-comparison family (Holm)", "", "| Test | raw p | Holm p |", "|---|---|---|"]
for r in R["holm_family"]:
    L.append(f"| {r['Test']} | {pv(r['p_raw'])} | {pv(r['p_holm'])} |")

L += ["", "## What was NOT tested or could not be verified", "",
 "- **The Streamlit app was not run.** Streamlit, Plotly and statsmodels could not be installed in the verification environment (the package index was blocked by the network policy, HTTP 403). Instead, every page's Python/pandas logic was executed against stand-in modules (`tests/smoke_app_with_stubs.py`); this catches NameErrors and pandas errors but not rendering, layout, or invalid Plotly arguments. Please run `streamlit run app.py` yourself.",
 "- `requirements.txt` minimum versions for streamlit, plotly and statsmodels are untested. `width=\"stretch\"` (already used in your original code) needs a recent Streamlit release; the original docs pinned streamlit 1.32.0, which is unlikely to support it.",
 "- Reference *content* (how Section 3 paraphrases each source) was not checked against full texts; only bibliographic metadata was verified.",
 "- Dataset provenance: resemblance to a fictional IBM sample dataset rests on matching record count and a documentation page; no row-level comparison was made.",
 "- The PDF was produced by LibreOffice from the DOCX; Word's pagination may differ slightly.",
 "- No sensitivity analysis of the burnout-score weights, no multivariable models, and no out-of-sample/longitudinal validation were performed.",
 ]
open(f"{OUT}/VERIFICATION_REPORT.md", "w").write("\n".join(L) + "\n")
print("wrote VERIFICATION_REPORT.md,", len(rows), "claims")
