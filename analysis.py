#!/usr/bin/env python3
r"""
analysis.py - reproducible statistics for the paper and the dashboard.

Usage:
    python analysis.py [path/to/Palo\ Alto\ Networks.csv] [output_dir]

Regenerates results.json and a set of CSV tables from the CSV alone. The paper
builder (build_paper.py) reads results.json, so no number is typed by hand.
All calculations come from hr_analytics.py (the same code the dashboard uses).
"""
import json
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

import hr_analytics as hr

CSV = sys.argv[1] if len(sys.argv) > 1 else "Palo Alto Networks.csv"
OUT = sys.argv[2] if len(sys.argv) > 2 else "outputs"
os.makedirs(OUT, exist_ok=True)

# Paper (original draft) claims that we verify against the data.
ORIGINAL_PAPER_CLAIMS = {
    "attrition_lowest_tertile_pct": 7.4,
    "attrition_highest_tertile_pct": 29.6,
    "records": 1470, "columns": 31,
}


def clean(o):
    """Make numpy/pandas objects JSON serialisable."""
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return None if np.isnan(o) else float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, pd.DataFrame):
        return clean(o.to_dict(orient="records"))
    return o


def save_table(df, name):
    df.to_csv(os.path.join(OUT, name + ".csv"), index=False)


R = {}

# ---------------------------------------------------------------- 1. dataset
raw = pd.read_csv(CSV)
R["dataset"] = {
    "file": os.path.basename(CSV),
    "rows": int(raw.shape[0]), "columns": int(raw.shape[1]),
    "missing_cells": int(raw.isna().sum().sum()),
    "duplicate_rows": int(raw.duplicated().sum()),
    "missing_required_columns": hr.missing_required_columns(raw),
    "attrition_unique_values": sorted(map(str, raw["Attrition"].unique())),
    "value_issues": hr.validate_values(raw),
    "ranges": {
        c: [float(raw[c].min()), float(raw[c].max())]
        for c in hr.SAT_COLS + ["WorkLifeBalance", "DistanceFromHome", "Education",
                                "JobLevel", "TotalWorkingYears", "YearsSinceLastPromotion",
                                "YearsAtCompany"]
    },
    "overtime_values": raw["OverTime"].value_counts().to_dict(),
    "travel_values": raw["BusinessTravel"].value_counts().to_dict(),
    "dtypes": {c: str(t) for c, t in raw.dtypes.items()},
}

df, prep = hr.prepare_dataframe(raw)
R["dataset"]["imputed"] = prep["imputed"]
n = len(df)
R["overall"] = {
    "n": n,
    "attrition_left": int(df["Attrition_Flag"].sum()),
    "attrition_rate_pct": df["Attrition_Flag"].mean() * 100,
    "engagement_mean": df["EngagementIndex"].mean(),
    "engagement_sd": df["EngagementIndex"].std(),
    "burnout_mean": df["NumericBurnoutScore"].mean(),
    "burnout_sd": df["NumericBurnoutScore"].std(),
    "burnout_min": df["NumericBurnoutScore"].min(),
    "burnout_max": df["NumericBurnoutScore"].max(),
    "job_satisfaction_mean": df["JobSatisfaction"].mean(),
    "wlb_mean": df["WorkLifeBalance"].mean(),
    "overtime_yes_n": int((df["OverTime"] == "Yes").sum()),
    "burnout_risk_counts": df["BurnoutRisk"].value_counts().to_dict(),
    "priority_counts": df["PriorityLevel"].value_counts().to_dict(),
}

# ------------------------------------------- 2. burnout score normalisation
orig_dist = ((raw["DistanceFromHome"] - raw["DistanceFromHome"].min())
             / (raw["DistanceFromHome"].max() - raw["DistanceFromHome"].min() + 1e-9)) * 20.0
paper_dist = ((raw["DistanceFromHome"] - 1) / (29 - 1 + 1e-9)) * 20.0
orig_score = (
    (raw["OverTime"] == "Yes").astype(float) * 30
    + ((4.0 - raw["WorkLifeBalance"]) / 3.0) * 30
    + (raw["BusinessTravel"].map(hr.TRAVEL_MAP).astype(float) / 2.0) * 20
    + orig_dist
).clip(0, 100).round(2)
paper_score = (orig_score - orig_dist.round(10) + paper_dist).clip(0, 100).round(2)
R["score_audit"] = {
    "observed_distance_min": int(raw["DistanceFromHome"].min()),
    "observed_distance_max": int(raw["DistanceFromHome"].max()),
    "fixed_bounds_used": [hr.DIST_MIN, hr.DIST_MAX],
    "max_abs_diff_original_code_vs_final": float((orig_score - df["NumericBurnoutScore"]).abs().max()),
    "max_abs_diff_paper_formula_vs_final": float((paper_score - df["NumericBurnoutScore"]).abs().max()),
    "n_scores_changed_vs_original_code": int((orig_score != df["NumericBurnoutScore"]).sum()),
    "weights": {"overtime": hr.W_OVERTIME, "work_life_balance": hr.W_WLB,
                "travel": hr.W_TRAVEL, "distance": hr.W_DISTANCE},
    "all_scores_within_0_100": bool(df["NumericBurnoutScore"].between(0, 100).all()),
    "component_means": {c: df[c].mean() for c in
                        ["OvertimePoints", "WLBPoints", "TravelPoints", "DistancePoints"]},
    "component_sd": {c: df[c].std() for c in
                     ["OvertimePoints", "WLBPoints", "TravelPoints", "DistancePoints"]},
}

# ----------------------------------------------------- 3. commute categories
old_cat = pd.cut(raw["DistanceFromHome"], bins=[-1, 5, 15, 50],
                 labels=["Short (<5m)", "Medium (5-15m)", "Long (>15m)"])
new_cat = df["CommuteCategory"]
commute_rows = []
for lab, g in df.groupby("CommuteCategory", observed=False):
    commute_rows.append({
        "Category": lab, "Employees": len(g),
        "Distance_min": g["DistanceFromHome"].min(), "Distance_max": g["DistanceFromHome"].max(),
        "MeanBurnoutScore": g["NumericBurnoutScore"].mean(),
        "MeanEngagement": g["EngagementIndex"].mean(),
        "Left": int(g["Attrition_Flag"].sum()),
        "AttritionRate_pct": g["Attrition_Flag"].mean() * 100,
    })
commute_tbl = pd.DataFrame(commute_rows)
save_table(commute_tbl, "commute_groups")
R["commute"] = {
    "labels": hr.COMMUTE_LABELS,
    "every_employee_in_exactly_one_category": bool(new_cat.notna().all()),
    "category_counts_sum": int(new_cat.value_counts().sum()),
    "employees_at_distance_5": int((raw["DistanceFromHome"] == 5).sum()),
    "employees_at_distance_6": int((raw["DistanceFromHome"] == 6).sum()),
    "employees_at_distance_15": int((raw["DistanceFromHome"] == 15).sum()),
    "employees_at_distance_16": int((raw["DistanceFromHome"] == 16).sum()),
    "original_bins_counts": old_cat.value_counts().to_dict(),
    "original_bins_missing": int(old_cat.isna().sum()),
    "n_reclassified_vs_original": int(
        (old_cat.astype(str).map({"Short (<5m)": "S", "Medium (5-15m)": "M", "Long (>15m)": "L"})
         != new_cat.astype(str).map(dict(zip(hr.COMMUTE_LABELS, "SML")))).sum()),
    "groups": commute_tbl,
}

# ------------------------------------------ 4. attrition by score tertile
groups, (t1, t2) = hr.score_tertiles(df["NumericBurnoutScore"])
df["ScoreGroup"] = groups
tert = hr.attrition_table(df, "ScoreGroup")
tert["MeanScore"] = [df.loc[df["ScoreGroup"] == g, "NumericBurnoutScore"].mean() for g in tert["ScoreGroup"]]
tert["ScoreMin"] = [df.loc[df["ScoreGroup"] == g, "NumericBurnoutScore"].min() for g in tert["ScoreGroup"]]
tert["ScoreMax"] = [df.loc[df["ScoreGroup"] == g, "NumericBurnoutScore"].max() for g in tert["ScoreGroup"]]
save_table(tert, "attrition_by_score_tertile")
ct = pd.crosstab(df["ScoreGroup"], df["Attrition_Flag"])
low = tert.iloc[0]
high = tert.iloc[-1]
rr = hr.relative_risk(int(high["Left"]), int(high["Employees"]), int(low["Left"]), int(low["Employees"]))
# 2x2 high vs low, difference in proportions
p_hi, p_lo = high["Left"] / high["Employees"], low["Left"] / low["Employees"]
se_diff = np.sqrt(p_hi * (1 - p_hi) / high["Employees"] + p_lo * (1 - p_lo) / low["Employees"])
auc = hr.auc_mann_whitney(df["NumericBurnoutScore"], df["Attrition_Flag"])
auc_ot = hr.auc_mann_whitney((df["OverTime"] == "Yes").astype(int), df["Attrition_Flag"])
R["tertiles"] = {
    "method": "Thresholds at the 33.3rd and 66.7th percentiles of the score; score<=t1 lowest, t1<score<=t2 middle, >t2 highest; ties go to the lower group.",
    "t1": t1, "t2": t2,
    "table": tert,
    "chi_square_3x2": hr.chi_square_with_effect(ct),
    "relative_risk_high_vs_low": rr,
    "risk_difference_pp": (p_hi - p_lo) * 100,
    "risk_difference_ci_pp": [(p_hi - p_lo - 1.96 * se_diff) * 100, (p_hi - p_lo + 1.96 * se_diff) * 100],
    "auc_score_in_sample": auc,
    "auc_overtime_only_in_sample": auc_ot,
    "paper_claim_lowest_pct": ORIGINAL_PAPER_CLAIMS["attrition_lowest_tertile_pct"],
    "paper_claim_highest_pct": ORIGINAL_PAPER_CLAIMS["attrition_highest_tertile_pct"],
}

comp = pd.crosstab(df["ScoreGroup"], df["OverTime"])
R["tertiles"]["overtime_composition"] = {
    str(g): {"overtime_yes": int(comp.loc[g, "Yes"]) if "Yes" in comp else 0,
             "n": int(comp.loc[g].sum()),
             "overtime_share_pct": float(comp.loc[g, "Yes"] / comp.loc[g].sum() * 100) if "Yes" in comp else 0.0}
    for g in comp.index
}

# attrition by overtime and, within each overtime stratum, by score group
ot_tbl = hr.attrition_table(df, "OverTime")
save_table(ot_tbl, "attrition_by_overtime")
strata = []
for ot, g in df.groupby("OverTime", observed=True):
    t = hr.attrition_table(g, "ScoreGroup")
    t.insert(0, "OverTime", ot)
    strata.append(t)
strata_tbl = pd.concat(strata, ignore_index=True)
save_table(strata_tbl, "attrition_by_tertile_within_overtime")
R["attrition_by_overtime"] = ot_tbl
R["attrition_tertile_within_overtime"] = strata_tbl

# attrition by existing burnout risk categories
risk_tbl = hr.attrition_table(df, "BurnoutRisk")
save_table(risk_tbl, "attrition_by_burnout_risk")
R["attrition_by_burnout_risk"] = risk_tbl

# ------------------------------------------------ 5. overtime vs engagement
ot = df.loc[df["OverTime"] == "Yes", "EngagementIndex"]
no = df.loc[df["OverTime"] == "No", "EngagementIndex"]
w = hr.welch_ttest(ot, no)
mw = stats.mannwhitneyu(ot, no, alternative="two-sided")
sw_ot = stats.shapiro(ot.sample(min(len(ot), 5000), random_state=0))
R["overtime_engagement"] = {
    "welch": w,
    "mann_whitney_p": float(mw.pvalue),
    "direction": "overtime higher" if w["diff"] > 0 else "overtime lower",
    "engagement_skewness_overtime": float(stats.skew(ot)),
    "engagement_skewness_no_overtime": float(stats.skew(no)),
    "shapiro_p_overtime": float(sw_ot.pvalue),
    "note": "EngagementIndex is a bounded mean of four ordinal items; n is large so the Welch t-test is reasonable; Mann-Whitney is reported as a robustness check.",
}

# -------------------------------------- 6. department / career stage / commute
def kruskal_by(col, val):
    groups_ = [g[val].values for _, g in df.groupby(col, observed=True)]
    h = stats.kruskal(*groups_)
    return {"H": float(h.statistic), "p": float(h.pvalue), "k": len(groups_)}

def group_table(col):
    t = df.groupby(col, observed=True).agg(
        Employees=("Age", "count"),
        MeanEngagement=("EngagementIndex", "mean"),
        MeanBurnoutScore=("NumericBurnoutScore", "mean"),
        MeanWLB=("WorkLifeBalance", "mean"),
        Left=("Attrition_Flag", "sum"),
        AttritionRate_pct=("Attrition_Flag", lambda s: s.mean() * 100),
    ).reset_index()
    return t

for col, key in [("Department", "department"), ("CareerStage", "career_stage")]:
    t = group_table(col)
    save_table(t, f"{key}_summary")
    ctab = pd.crosstab(df[col], df["Attrition_Flag"])
    R[key] = {
        "table": t,
        "engagement_kruskal": kruskal_by(col, "EngagementIndex"),
        "burnout_kruskal": kruskal_by(col, "NumericBurnoutScore"),
        "attrition_chi2": hr.chi_square_with_effect(ctab),
    }
R["commute"]["engagement_kruskal"] = kruskal_by("CommuteCategory", "EngagementIndex")
R["commute"]["burnout_kruskal_MECHANICAL"] = kruskal_by("CommuteCategory", "NumericBurnoutScore")
R["commute"]["attrition_chi2"] = hr.chi_square_with_effect(pd.crosstab(df["CommuteCategory"], df["Attrition_Flag"]))
R["commute"]["spearman_distance_vs_burnout_score"] = dict(zip(["rho", "p"], map(float, stats.spearmanr(df["DistanceFromHome"], df["NumericBurnoutScore"]))))
R["commute"]["spearman_distance_vs_engagement"] = dict(zip(["rho", "p"], map(float, stats.spearmanr(df["DistanceFromHome"], df["EngagementIndex"]))))
# share of the burnout score's variance that is mechanically due to distance
R["commute"]["distance_points_share_of_score_variance_pct"] = float(
    np.cov(df["DistancePoints"], df["NumericBurnoutScore"])[0, 1] / df["NumericBurnoutScore"].var() * 100)

# ------------------------------------------------ 7. promotion / tenure
yp = df["YearsSinceLastPromotion"]
promo_tbl = df.groupby("YearsSinceLastPromotion").agg(
    Employees=("Age", "count"), MeanEngagement=("EngagementIndex", "mean")).reset_index()
save_table(promo_tbl, "engagement_by_years_since_promotion")
sp = stats.spearmanr(yp, df["EngagementIndex"])
recent = df.loc[yp <= 3, "EngagementIndex"]
stale = df.loc[yp >= 4, "EngagementIndex"]
R["promotion"] = {
    "spearman_rho": float(sp.statistic), "spearman_p": float(sp.pvalue),
    "ols": hr.simple_ols(yp, df["EngagementIndex"]),
    "threshold_test_le3_vs_ge4": hr.welch_ttest(stale, recent),
    "threshold_note": "YearsSinceLastPromotion is an integer, so the paper's 3.5-year cliff is tested as >=4 years vs <=3 years.",
    "mean_engagement_by_year": promo_tbl,
    "mean_years_since_promotion": float(yp.mean()),
}
ten = df["YearsAtCompany"]
spt = stats.spearmanr(ten, df["EngagementIndex"])
R["tenure"] = {
    "spearman_rho": float(spt.statistic), "spearman_p": float(spt.pvalue),
    "ols": hr.simple_ols(ten, df["EngagementIndex"]),
}
R["other_associations"] = {
    "spearman_wlb_vs_attrition": dict(zip(["rho", "p"], map(float, stats.spearmanr(df["WorkLifeBalance"], df["Attrition_Flag"])))),
}

# ---------------------------------------- 8. multiple-comparison correction
family = [
    ("Overtime vs engagement (Welch t)", R["overtime_engagement"]["welch"]["p"]),
    ("Promotion wait vs engagement (Spearman)", R["promotion"]["spearman_p"]),
    ("Promotion >=4 vs <=3 yrs, engagement (Welch t)", R["promotion"]["threshold_test_le3_vs_ge4"]["p"]),
    ("Tenure vs engagement (Spearman)", R["tenure"]["spearman_p"]),
    ("Engagement across departments (Kruskal-Wallis)", R["department"]["engagement_kruskal"]["p"]),
    ("Engagement across career stages (Kruskal-Wallis)", R["career_stage"]["engagement_kruskal"]["p"]),
    ("Engagement across commute groups (Kruskal-Wallis)", R["commute"]["engagement_kruskal"]["p"]),
    ("Attrition across score thirds (chi-square)", R["tertiles"]["chi_square_3x2"]["p"]),
    ("Attrition across departments (chi-square)", R["department"]["attrition_chi2"]["p"]),
    ("Attrition across career stages (chi-square)", R["career_stage"]["attrition_chi2"]["p"]),
    ("Attrition across commute groups (chi-square)", R["commute"]["attrition_chi2"]["p"]),
]
adj = hr.holm_adjust([p for _, p in family])
fam_tbl = pd.DataFrame({"Test": [f for f, _ in family], "p_raw": [p for _, p in family], "p_holm": adj})
fam_tbl["Significant_at_0.05_after_Holm"] = fam_tbl["p_holm"] < 0.05
save_table(fam_tbl, "multiple_comparison_holm")
R["holm_family"] = fam_tbl

# ------------------------------------------------ 9. claim verification
c = ORIGINAL_PAPER_CLAIMS
tl = tert.iloc[0]["AttritionRate_pct"]
th = tert.iloc[-1]["AttritionRate_pct"]
R["claim_checks"] = [
    {"claim": "1,470 records", "computed": n, "supported": n == c["records"]},
    {"claim": "31 columns", "computed": int(raw.shape[1]), "supported": raw.shape[1] == c["columns"]},
    {"claim": "Zero missing values", "computed": R["dataset"]["missing_cells"], "supported": R["dataset"]["missing_cells"] == 0},
    {"claim": "Attrition near 16.12%", "computed": round(R["overall"]["attrition_rate_pct"], 2), "supported": abs(R["overall"]["attrition_rate_pct"] - 16.12) < 0.01},
    {"claim": f"Lowest tertile attrition {c['attrition_lowest_tertile_pct']}%", "computed": round(tl, 2), "supported": abs(tl - c["attrition_lowest_tertile_pct"]) < 0.05},
    {"claim": f"Highest tertile attrition {c['attrition_highest_tertile_pct']}%", "computed": round(th, 2), "supported": abs(th - c["attrition_highest_tertile_pct"]) < 0.05},
    {"claim": "Overtime associated with slightly higher engagement", "computed": round(w["diff"], 4), "supported": w["diff"] > 0},
    {"claim": "No relationship between promotion wait and engagement", "computed": round(R["promotion"]["spearman_rho"], 4), "supported": R["promotion"]["spearman_p"] >= 0.05},
]

with open(os.path.join(OUT, "results.json"), "w") as fh:
    json.dump(clean(R), fh, indent=2, default=str)

# --------------------------------------------------- console summary
print(f"Dataset: {R['dataset']['rows']} rows x {R['dataset']['columns']} cols; "
      f"missing={R['dataset']['missing_cells']}; dups={R['dataset']['duplicate_rows']}")
print(f"Attrition: {R['overall']['attrition_left']}/{n} = {R['overall']['attrition_rate_pct']:.2f}%")
print(f"EI mean {R['overall']['engagement_mean']:.3f}; burnout mean {R['overall']['burnout_mean']:.2f}")
print("Score audit:", R["score_audit"]["max_abs_diff_original_code_vs_final"],
      R["score_audit"]["max_abs_diff_paper_formula_vs_final"], R["score_audit"]["n_scores_changed_vs_original_code"])
print(tert.to_string(index=False))
print("t1,t2 =", round(t1, 3), round(t2, 3), "| AUC", round(auc, 3), "| AUC overtime-only", round(auc_ot, 3))
print("RR", rr, "chi2", R["tertiles"]["chi_square_3x2"])
print("Overtime Welch", {k: round(v, 4) for k, v in w.items()}, "MW p", mw.pvalue)
print(commute_tbl.to_string(index=False))
print("old bins", R["commute"]["original_bins_counts"], "reclassified", R["commute"]["n_reclassified_vs_original"])
print("Promotion", R["promotion"]["spearman_rho"], R["promotion"]["spearman_p"], R["promotion"]["threshold_test_le3_vs_ge4"])
print("Tenure", R["tenure"]["spearman_rho"], R["tenure"]["spearman_p"])
print(fam_tbl.to_string(index=False))
print(strata_tbl.to_string(index=False))
for k in ("department", "career_stage"):
    print(R[k]["table"].to_string(index=False))
