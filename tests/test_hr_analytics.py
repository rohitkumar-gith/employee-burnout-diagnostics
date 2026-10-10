import os
import sys

import numpy as np
import pandas as pd
import pytest
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hr_analytics as hr  # noqa: E402

CSV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Palo Alto Networks.csv")


def make_df(**overrides):
    """A minimal valid frame with every required column (3 employees)."""
    base = {
        "Age": [30, 40, 50], "Attrition": [0, 1, 0],
        "BusinessTravel": ["Non-Travel", "Travel_Rarely", "Travel_Frequently"],
        "DistanceFromHome": [1, 15, 29], "Department": ["Sales", "Sales", "R&D"],
        "Education": [3, 3, 3], "EnvironmentSatisfaction": [3, 3, 3], "Gender": ["Male", "Female", "Male"],
        "JobInvolvement": [3, 3, 3], "JobLevel": [1, 2, 3], "JobRole": ["A", "B", "C"],
        "JobSatisfaction": [3, 3, 3], "MaritalStatus": ["Single", "Married", "Single"],
        "MonthlyIncome": [3000, 4000, 5000], "OverTime": ["No", "Yes", "Yes"],
        "PerformanceRating": [3, 3, 3], "RelationshipSatisfaction": [3, 3, 3],
        "TotalWorkingYears": [2, 10, 20], "WorkLifeBalance": [4, 2, 1],
        "YearsAtCompany": [1, 5, 10], "YearsInCurrentRole": [1, 3, 5],
        "YearsSinceLastPromotion": [0, 1, 2], "YearsWithCurrManager": [1, 2, 3],
        "TrainingTimesLastYear": [2, 2, 2], "NumCompaniesWorked": [1, 2, 3],
    }
    base.update(overrides)
    return pd.DataFrame(base)


# ------------------------------------------------------------ burnout score
def test_score_known_values():
    df = make_df()
    s = hr.burnout_score(df)
    # no overtime, WLB 4, non-travel, distance 1 -> 0
    assert s.iloc[0] == 0.0
    # overtime 30 + WLB 2 -> (4-2)/3*30 = 20 + travel rarely 10 + distance 15 -> (15-1)/28*20 = 10 -> 70
    assert s.iloc[1] == pytest.approx(70.0)
    # overtime 30 + WLB (1) 30 + frequent 20 + distance 29 -> 20 = 100
    assert s.iloc[2] == 100.0


def test_score_components_sum_to_score_and_weights_total_100():
    df = make_df()
    comps = hr.burnout_components(df)
    assert comps.sum(axis=1).round(2).tolist() == hr.burnout_score(df).tolist()
    assert hr.W_OVERTIME + hr.W_WLB + hr.W_TRAVEL + hr.W_DISTANCE == 100


def test_score_bounds_with_extreme_inputs():
    df = make_df(DistanceFromHome=[0, 29, 500], WorkLifeBalance=[4, 1, 1])
    s = hr.burnout_score(df)
    assert s.between(0, 100).all()
    # distance far above the upper bound is capped at 20 points
    assert hr.burnout_components(df)["DistancePoints"].iloc[2] == 20.0
    # distance below the lower bound is floored at 0 points
    assert hr.burnout_components(df)["DistancePoints"].iloc[0] == 0.0


def test_score_all_possible_combinations_within_bounds():
    rows = [(ot, w, t, d) for ot in ["Yes", "No"] for w in [1, 2, 3, 4]
            for t in hr.TRAVEL_MAP for d in [1, 15, 29]]
    n = len(rows)
    df = make_df(
        Age=[30] * n, Attrition=[0] * n, BusinessTravel=[r[2] for r in rows],
        DistanceFromHome=[r[3] for r in rows], Department=["S"] * n, Education=[3] * n,
        EnvironmentSatisfaction=[3] * n, Gender=["Male"] * n, JobInvolvement=[3] * n,
        JobLevel=[1] * n, JobRole=["A"] * n, JobSatisfaction=[3] * n, MaritalStatus=["Single"] * n,
        MonthlyIncome=[1] * n, OverTime=[r[0] for r in rows], PerformanceRating=[3] * n,
        RelationshipSatisfaction=[3] * n, TotalWorkingYears=[1] * n, WorkLifeBalance=[r[1] for r in rows],
        YearsAtCompany=[1] * n, YearsInCurrentRole=[1] * n, YearsSinceLastPromotion=[0] * n,
        YearsWithCurrManager=[1] * n, TrainingTimesLastYear=[1] * n, NumCompaniesWorked=[1] * n,
    )
    s = hr.burnout_score(df)
    assert s.between(0, 100).all() and s.min() == 0 and s.max() == 100


def test_score_independent_of_other_rows():
    """Fixed distance bounds: an employee's score must not change with the
    other employees in the frame (the old min/max approach did)."""
    df = make_df()
    alone = hr.burnout_score(df.iloc[[1]])
    together = hr.burnout_score(df)
    assert alone.iloc[0] == together.iloc[1]


def test_risk_and_priority_rules():
    df = make_df(OverTime=["Yes", "Yes", "No"], WorkLifeBalance=[1, 3, 4])
    risk = hr.burnout_risk(df)
    assert risk.tolist() == ["High", "Medium", "Low"]
    pr = hr.priority_level(risk, pd.Series([2.0, 2.4, 3.9]))
    assert pr.tolist() == ["Critical", "High", "Low"]
    # boundary: engagement exactly 2.2 is Critical for High risk; exactly 2.5 is not <2.5
    assert hr.priority_level(pd.Series(["High"]), pd.Series([2.2])).iloc[0] == "Critical"
    assert hr.priority_level(pd.Series(["Medium"]), pd.Series([2.5])).iloc[0] == "Medium"


# ---------------------------------------------------- commute categories
@pytest.mark.parametrize("dist,label", [
    (0, "Short (1-5)"), (1, "Short (1-5)"), (5, "Short (1-5)"),
    (6, "Medium (6-15)"), (15, "Medium (6-15)"),
    (16, "Long (16+)"), (29, "Long (16+)"), (100, "Long (16+)"),
])
def test_commute_boundaries(dist, label):
    assert str(hr.commute_category(pd.Series([dist])).iloc[0]) == label


def test_commute_labels_match_code_and_are_exclusive():
    d = pd.Series(range(0, 60))
    cats = hr.commute_category(d)
    assert cats.notna().all()
    assert set(cats.astype(str)) == set(hr.COMMUTE_LABELS)
    counts = cats.value_counts()
    assert counts.sum() == len(d)


@pytest.mark.parametrize("yrs,label", [(0, "Early (0-5 yrs)"), (5, "Early (0-5 yrs)"), (6, "Mid (6-15 yrs)"),
                                       (15, "Mid (6-15 yrs)"), (16, "Late (16+ yrs)"), (40, "Late (16+ yrs)")])
def test_career_stage_boundaries(yrs, label):
    assert str(hr.career_stage(pd.Series([yrs])).iloc[0]) == label


# ------------------------------------------------------ attrition encoding
@pytest.mark.parametrize("values", [
    [1, 0, 1], [1.0, 0.0, 1.0], ["1", "0", "1"], ["Yes", "No", "Yes"],
    ["yes", " NO ", "YES"], ["Y", "N", "Y"], [True, False, True], ["true", "false", "True"],
])
def test_attrition_encoding_supported_formats(values):
    out = hr.normalize_attrition(pd.Series(values))
    assert out.tolist() == [1, 0, 1]
    assert pd.api.types.is_integer_dtype(out)


@pytest.mark.parametrize("values", [["Yes", "Maybe"], [1, 2], ["Yes", None], [1, np.nan], ["left", "stayed"]])
def test_attrition_unexpected_values_raise_not_silently_zero(values):
    with pytest.raises(hr.DataValidationError):
        hr.normalize_attrition(pd.Series(values))


def test_text_attrition_gives_numeric_rate():
    df, _ = hr.prepare_dataframe(make_df(Attrition=["No", "Yes", "No"]))
    assert df["Attrition_Flag"].tolist() == [0, 1, 0]
    assert df["Attrition_Flag"].mean() == pytest.approx(1 / 3)
    assert df["Attrition_Label"].tolist() == ["Stayed", "Left Company", "Stayed"]


# ---------------------------------------------------------- schema / values
def test_missing_required_columns_clear_error():
    df = make_df().drop(columns=["OverTime", "WorkLifeBalance"])
    with pytest.raises(hr.SchemaError) as e:
        hr.prepare_dataframe(df)
    assert set(e.value.missing) == {"OverTime", "WorkLifeBalance"}
    assert "OverTime" in str(e.value)


def test_schema_error_is_not_keyerror():
    with pytest.raises(hr.SchemaError):
        hr.validate_schema(pd.DataFrame({"Age": [1]}))


@pytest.mark.parametrize("col,vals,fragment", [
    ("WorkLifeBalance", [4, 2, 5], "WorkLifeBalance"),
    ("JobSatisfaction", [0, 3, 3], "JobSatisfaction"),
    ("OverTime", ["No", "Maybe", "Yes"], "OverTime"),
    ("BusinessTravel", ["Never", "Travel_Rarely", "Non-Travel"], "BusinessTravel"),
    ("DistanceFromHome", [-1, 5, 6], "DistanceFromHome"),
    ("Education", [1, 2, 9], "Education"),
])
def test_out_of_range_or_unexpected_values_rejected(col, vals, fragment):
    with pytest.raises(hr.DataValidationError) as e:
        hr.prepare_dataframe(make_df(**{col: vals}))
    assert fragment in str(e.value)


def test_missing_values_imputed_but_attrition_never_imputed():
    raw = make_df(JobSatisfaction=[3, np.nan, 3])
    df, report = hr.prepare_dataframe(raw)
    assert report["imputed"] == {"JobSatisfaction": 1}
    assert df["EngagementIndex"].notna().all()
    raw2 = make_df(Attrition=[0, np.nan, 1])
    with pytest.raises(hr.DataValidationError):
        hr.prepare_dataframe(raw2)


def test_distance_above_bound_gets_notice():
    _, report = hr.prepare_dataframe(make_df(DistanceFromHome=[1, 15, 40]))
    assert any("above" in n for n in report["notices"])


# --------------------------------------------------- empty / group calculations
def test_empty_filtered_frame_is_handled():
    df, _ = hr.prepare_dataframe(make_df())
    empty = df.iloc[0:0]
    assert empty.empty
    assert hr.attrition_table(empty, "Department").empty
    assert hr.safe_rate(empty["Attrition_Flag"]) is None


def test_attrition_table_counts_and_denominators():
    big = pd.concat([make_df(), make_df()], ignore_index=True)
    big["Attrition"] = [1, 0, 0, 1, 1, 0]
    big["Department"] = ["A", "A", "A", "B", "B", "B"]
    big, _ = hr.prepare_dataframe(big)
    t = hr.attrition_table(big, "Department").set_index("Department")
    assert t.loc["A", "Employees"] == 3 and t.loc["A", "Left"] == 1
    assert t.loc["B", "Employees"] == 3 and t.loc["B", "Left"] == 2
    assert t.loc["A", "AttritionRate_pct"] == pytest.approx(33.33, abs=0.01)
    assert t.loc["B", "AttritionRate_pct"] == pytest.approx(66.67, abs=0.01)
    # denominators are the group sizes, never the company total
    assert t["Employees"].sum() == len(big)
    assert t["Left"].sum() == big["Attrition_Flag"].sum()
    assert (t["CI95_low_pct"] <= t["AttritionRate_pct"]).all() and (t["AttritionRate_pct"] <= t["CI95_high_pct"]).all()


def test_wilson_ci_known_value_and_edges():
    lo, hi = hr.wilson_ci(0, 10)
    assert lo == 0.0 and 0.2 < hi < 0.35
    lo, hi = hr.wilson_ci(10, 10)
    assert hi == pytest.approx(1.0) and 0.65 < lo < 0.75
    assert all(np.isnan(hr.wilson_ci(0, 0)))
    lo, hi = hr.wilson_ci(50, 100)
    assert lo == pytest.approx(0.4038, abs=1e-3) and hi == pytest.approx(0.5962, abs=1e-3)


def test_tertiles_cover_everyone_and_ties_stay_together():
    score = pd.Series([0, 0, 0, 10, 10, 20, 20, 30, 40, 50, 60, 100], dtype=float)
    groups, (t1, t2) = hr.score_tertiles(score)
    g = pd.Series(groups)
    assert g.notna().all() and len(g) == len(score)
    assert t1 <= t2
    # identical scores never split across groups
    for v in score.unique():
        assert g[score == v].nunique() == 1
    # ordering is monotone: every score in a lower group is <= every score in a higher group
    codes = pd.Series(pd.Categorical(groups).codes)
    for lo_g, hi_g in [(0, 1), (1, 2)]:
        a, b = score[codes == lo_g], score[codes == hi_g]
        if len(a) and len(b):
            assert a.max() <= b.min()


def test_attrition_by_score_group_sums():
    big = pd.concat([make_df() for _ in range(20)], ignore_index=True)
    rng = np.random.default_rng(0)
    big["Attrition"] = rng.integers(0, 2, len(big))
    big["DistanceFromHome"] = rng.integers(1, 30, len(big))
    big["WorkLifeBalance"] = rng.integers(1, 5, len(big))
    big["OverTime"] = rng.choice(["Yes", "No"], len(big))
    df, _ = hr.prepare_dataframe(big)
    t = hr.attrition_table(df, "ScoreGroup")
    assert t["Employees"].sum() == len(df)
    assert t["Left"].sum() == df["Attrition_Flag"].sum()
    for _, r in t.iterrows():
        sub = df[df["ScoreGroup"] == r["ScoreGroup"]]
        assert r["Left"] == sub["Attrition_Flag"].sum()
        assert r["AttritionRate_pct"] == pytest.approx(round(sub["Attrition_Flag"].mean() * 100, 2))


# ------------------------------------------------------------- statistics
def test_welch_matches_scipy_and_direction():
    rng = np.random.default_rng(1)
    a = pd.Series(rng.normal(2.8, 0.5, 120))
    b = pd.Series(rng.normal(2.7, 0.6, 300))
    w = hr.welch_ttest(a, b)
    ref = stats.ttest_ind(a, b, equal_var=False)
    assert w["t"] == pytest.approx(ref.statistic) and w["p"] == pytest.approx(ref.pvalue)
    assert w["diff"] == pytest.approx(a.mean() - b.mean())
    assert w["ci_low"] < w["diff"] < w["ci_high"]
    assert (w["n_a"], w["n_b"]) == (120, 300)
    # swapping the groups flips the sign only
    w2 = hr.welch_ttest(b, a)
    assert w2["diff"] == pytest.approx(-w["diff"]) and w2["p"] == pytest.approx(w["p"])


def test_holm_adjustment():
    assert hr.holm_adjust([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
    assert hr.holm_adjust([0.5]) == [0.5]
    assert max(hr.holm_adjust([0.9, 0.8])) <= 1.0


def test_relative_risk_and_auc():
    rr = hr.relative_risk(30, 100, 10, 100)
    assert rr["rr"] == pytest.approx(3.0) and rr["ci_low"] < 3.0 < rr["ci_high"]
    assert np.isnan(hr.relative_risk(0, 10, 5, 10)["rr"])
    score = pd.Series([1, 2, 3, 4]); flag = pd.Series([0, 0, 1, 1])
    assert hr.auc_mann_whitney(score, flag) == 1.0
    assert hr.auc_mann_whitney(pd.Series([1, 1, 1, 1]), flag) == 0.5


# ------------------------------------------ the supplied CSV (if present)
@pytest.mark.skipif(not os.path.exists(CSV), reason="CSV not present")
def test_supplied_csv_baseline_and_paper_numbers():
    raw = pd.read_csv(CSV)
    assert raw.shape == (1470, 31)
    assert raw.isna().sum().sum() == 0 and raw.duplicated().sum() == 0
    df, report = hr.prepare_dataframe(raw)
    assert report["imputed"] == {}
    assert df["Attrition_Flag"].mean() * 100 == pytest.approx(16.12, abs=0.005)
    assert df["NumericBurnoutScore"].between(0, 100).all()
    assert df["CommuteCategory"].notna().all()
    assert df["DistanceFromHome"].min() == hr.DIST_MIN and df["DistanceFromHome"].max() == hr.DIST_MAX
    t = hr.attrition_table(df, "ScoreGroup")
    assert t["Employees"].sum() == 1470 and t["Left"].sum() == 237
    assert t["AttritionRate_pct"].iloc[0] == pytest.approx(7.41, abs=0.01)
    assert t["AttritionRate_pct"].iloc[-1] == pytest.approx(29.63, abs=0.01)


@pytest.mark.skipif(not os.path.exists(CSV), reason="CSV not present")
def test_fixed_bounds_equal_original_minmax_on_supplied_csv():
    raw = pd.read_csv(CSV)
    d = raw["DistanceFromHome"]
    old = ((d - d.min()) / (d.max() - d.min() + 1e-9)) * 20.0
    new = hr.burnout_components(raw)["DistancePoints"]
    assert (old - new).abs().max() < 1e-6
