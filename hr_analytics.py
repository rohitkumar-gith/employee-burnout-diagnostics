"""
hr_analytics.py
===============
Reusable, Streamlit-free calculations shared by the dashboard (app.py), the
reproducible analysis script (analysis.py) and the automated tests.

Everything in the paper and the dashboard that is a number is produced by the
functions in this module, so the two cannot drift apart.

IMPORTANT: the Numeric Burnout Score is a transparent, rule-based indicator.
It is NOT a clinical measure of burnout and NOT a validated predictive model.
"""
from __future__ import annotations

from io import BytesIO
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

# --------------------------------------------------------------------------
# Constants (single source of truth for formulas and category boundaries)
# --------------------------------------------------------------------------
REQUIRED_COLUMNS: List[str] = [
    "Age", "Attrition", "BusinessTravel", "DistanceFromHome", "Department",
    "Education", "EnvironmentSatisfaction", "Gender", "JobInvolvement",
    "JobLevel", "JobRole", "JobSatisfaction", "MaritalStatus",
    "MonthlyIncome", "OverTime", "PerformanceRating",
    "RelationshipSatisfaction", "TotalWorkingYears", "WorkLifeBalance",
    "YearsAtCompany", "YearsInCurrentRole", "YearsSinceLastPromotion",
    "YearsWithCurrManager", "TrainingTimesLastYear", "NumCompaniesWorked",
]

SAT_COLS: List[str] = [
    "JobInvolvement", "JobSatisfaction",
    "EnvironmentSatisfaction", "RelationshipSatisfaction",
]

TRAVEL_MAP: Dict[str, int] = {"Non-Travel": 0, "Travel_Rarely": 1, "Travel_Frequently": 2}
OVERTIME_MAP: Dict[str, int] = {"No": 0, "Yes": 1}

# Burnout-score weights (points). They sum to 100.
W_OVERTIME = 30.0
W_WLB = 30.0
W_TRAVEL = 20.0
W_DISTANCE = 20.0

# Commute-distance normalisation: FIXED documented bounds.
# On the supplied CSV the observed minimum and maximum are 1 and 29, so this is
# numerically identical to min-max scaling, but an employee's score no longer
# depends on which other employees happen to be in the file or filter.
DIST_MIN = 1.0
DIST_MAX = 29.0

# Commute categories: mutually exclusive, exhaustive, right-inclusive bins.
# (distance unit is not documented in the dataset; labels are unit-neutral)
COMMUTE_BINS = [-np.inf, 5, 15, np.inf]
COMMUTE_LABELS = ["Short (1-5)", "Medium (6-15)", "Long (16+)"]

# Career stage by TotalWorkingYears.
CAREER_BINS = [-np.inf, 5, 15, np.inf]
CAREER_LABELS = ["Early (0-5 yrs)", "Mid (6-15 yrs)", "Late (16+ yrs)"]

# Priority thresholds
ENGAGEMENT_CRITICAL = 2.2
ENGAGEMENT_LOW = 2.5

TERTILE_LABELS = ["Lowest third", "Middle third", "Highest third"]


class SchemaError(ValueError):
    """Raised when the CSV lacks required columns."""

    def __init__(self, missing: Iterable[str]):
        self.missing = list(missing)
        super().__init__("Missing required columns: " + ", ".join(self.missing))


class DataValidationError(ValueError):
    """Raised when values are unexpected / out of range."""

    def __init__(self, issues: Iterable[str]):
        self.issues = list(issues)
        super().__init__("; ".join(self.issues))


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------
def missing_required_columns(df: pd.DataFrame) -> List[str]:
    return [c for c in REQUIRED_COLUMNS if c not in df.columns]


def validate_schema(df: pd.DataFrame) -> None:
    """Raise SchemaError (clear message) instead of a KeyError later on."""
    missing = missing_required_columns(df)
    if missing:
        raise SchemaError(missing)


def normalize_attrition(series: pd.Series) -> pd.Series:
    """
    Convert attrition to a binary int indicator (1 = left, 0 = stayed).

    Accepts 1/0, 1.0/0.0, True/False and (case-insensitive) Yes/No, Y/N,
    True/False, 1/0 as text. Anything else - including missing values - raises
    DataValidationError listing the offending values; nothing is silently
    treated as "stayed".
    """
    mapping = {
        "1": 1, "1.0": 1, "yes": 1, "y": 1, "true": 1,
        "0": 0, "0.0": 0, "no": 0, "n": 0, "false": 0,
    }
    as_text = series.astype("object").map(
        lambda v: str(v).strip().lower() if pd.notna(v) else None
    )
    out = as_text.map(mapping)
    bad_mask = out.isna()
    if bad_mask.any():
        bad_vals = sorted({repr(v) for v in series[bad_mask].unique()})
        raise DataValidationError([
            f"Attrition has {int(bad_mask.sum())} unsupported/missing value(s): "
            + ", ".join(bad_vals[:10])
            + ". Supported: 1/0 or Yes/No."
        ])
    return out.astype(int)


def validate_values(df: pd.DataFrame) -> List[str]:
    """Return a list of human-readable problems (empty list = OK). Expects
    required columns to exist (call validate_schema first)."""
    issues: List[str] = []

    def bad_count(mask: pd.Series) -> int:
        return int(mask.sum())

    for col in SAT_COLS + ["WorkLifeBalance"]:
        s = pd.to_numeric(df[col], errors="coerce")
        n = bad_count(s.notna() & ~s.between(1, 4))
        if n:
            issues.append(f"{col}: {n} value(s) outside the valid 1-4 range")
        n = bad_count(df[col].notna() & s.isna())
        if n:
            issues.append(f"{col}: {n} non-numeric value(s)")

    s = pd.to_numeric(df["Education"], errors="coerce")
    n = bad_count(s.notna() & ~s.between(1, 5))
    if n:
        issues.append(f"Education: {n} value(s) outside the valid 1-5 range")

    s = pd.to_numeric(df["DistanceFromHome"], errors="coerce")
    n = bad_count(s.notna() & (s < 0))
    if n:
        issues.append(f"DistanceFromHome: {n} negative value(s)")
    n = bad_count(df["DistanceFromHome"].notna() & s.isna())
    if n:
        issues.append(f"DistanceFromHome: {n} non-numeric value(s)")

    n = bad_count(df["OverTime"].notna() & ~df["OverTime"].isin(OVERTIME_MAP))
    if n:
        vals = sorted(map(str, df.loc[~df["OverTime"].isin(OVERTIME_MAP) & df["OverTime"].notna(), "OverTime"].unique()))
        issues.append(f"OverTime: {n} unexpected value(s) {vals[:5]} (expected Yes/No)")

    n = bad_count(df["BusinessTravel"].notna() & ~df["BusinessTravel"].isin(TRAVEL_MAP))
    if n:
        vals = sorted(map(str, df.loc[~df["BusinessTravel"].isin(TRAVEL_MAP) & df["BusinessTravel"].notna(), "BusinessTravel"].unique()))
        issues.append(
            f"BusinessTravel: {n} unexpected value(s) {vals[:5]} "
            f"(expected {', '.join(TRAVEL_MAP)})"
        )
    return issues


def impute_missing(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """
    Fill missing values (median for numeric, mode for categorical) EXCEPT for
    Attrition, which must never be imputed. Returns the frame and a
    {column: n_filled} report so the UI can disclose what was done.
    """
    df = df.copy()
    report: Dict[str, int] = {}
    for col in df.columns:
        if col == "Attrition":
            continue
        n = int(df[col].isna().sum())
        if not n:
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].fillna(df[col].median())
            report[col] = n
        else:
            mode = df[col].mode()
            if not mode.empty:
                df[col] = df[col].fillna(mode.iloc[0])
                report[col] = n
    return df, report


# --------------------------------------------------------------------------
# Feature engineering
# --------------------------------------------------------------------------
def commute_category(distance: pd.Series) -> pd.Categorical:
    """Short 1-5, Medium 6-15, Long 16+ (right-inclusive, no gaps, no exclusions)."""
    return pd.cut(distance, bins=COMMUTE_BINS, labels=COMMUTE_LABELS, right=True)


def career_stage(years: pd.Series) -> pd.Categorical:
    return pd.cut(years, bins=CAREER_BINS, labels=CAREER_LABELS, right=True)


def burnout_components(df: pd.DataFrame) -> pd.DataFrame:
    """The four additive components of the Numeric Burnout Score (points)."""
    overtime = (df["OverTime"] == "Yes").astype(float) * W_OVERTIME
    wlb = ((4.0 - df["WorkLifeBalance"].astype(float)) / 3.0) * W_WLB
    travel = (df["BusinessTravel"].map(TRAVEL_MAP).astype(float) / 2.0) * W_TRAVEL
    dist_norm = ((df["DistanceFromHome"].astype(float) - DIST_MIN) / (DIST_MAX - DIST_MIN)).clip(0.0, 1.0)
    distance = dist_norm * W_DISTANCE
    return pd.DataFrame({
        "OvertimePoints": overtime,
        "WLBPoints": wlb,
        "TravelPoints": travel,
        "DistancePoints": distance,
    })


def burnout_score(df: pd.DataFrame) -> pd.Series:
    """Numeric Burnout Score, bounded to [0, 100], rounded to 2 decimals."""
    comps = burnout_components(df)
    return comps.sum(axis=1).clip(0, 100).round(2)


def burnout_risk(df: pd.DataFrame) -> pd.Series:
    high = (df["OverTime"] == "Yes") & (df["WorkLifeBalance"] <= 2)
    med = (df["OverTime"] == "Yes") | (df["WorkLifeBalance"] <= 2)
    return pd.Series(np.select([high, med], ["High", "Medium"], default="Low"), index=df.index)


def priority_level(risk: pd.Series, engagement: pd.Series) -> pd.Series:
    crit = (risk == "High") & (engagement <= ENGAGEMENT_CRITICAL)
    high = (risk == "High") | ((risk == "Medium") & (engagement < ENGAGEMENT_LOW))
    med = risk == "Medium"
    return pd.Series(
        np.select([crit, high, med], ["Critical", "High", "Medium"], default="Low"),
        index=risk.index,
    )


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add all derived columns. Input must already be validated/imputed."""
    df = df.copy()
    df["Attrition_Flag"] = normalize_attrition(df["Attrition"])
    df["Attrition_Label"] = df["Attrition_Flag"].map({1: "Left Company", 0: "Stayed"})

    df["EngagementIndex"] = df[SAT_COLS].mean(axis=1)
    df["SatisfactionStabilityScore"] = 4.0 - df[SAT_COLS].std(axis=1).fillna(0)
    df["WorkLifeBalanceIndex"] = df["WorkLifeBalance"] / 4.0
    df["WorkloadStressIndicator"] = (
        df["BusinessTravel"].map(TRAVEL_MAP).astype(float)
        + df["OverTime"].map(OVERTIME_MAP).astype(float) * 2
    )
    df["CommuteCategory"] = commute_category(df["DistanceFromHome"])
    df["CareerStage"] = career_stage(df["TotalWorkingYears"])

    for k, v in burnout_components(df).items():
        df[k] = v
    df["NumericBurnoutScore"] = burnout_score(df)
    df["BurnoutRisk"] = pd.Categorical(burnout_risk(df), categories=["Low", "Medium", "High"])
    df["PriorityLevel"] = pd.Categorical(
        priority_level(df["BurnoutRisk"].astype(str), df["EngagementIndex"]),
        categories=["Low", "Medium", "High", "Critical"],
    )
    df["ScoreGroup"], _ = score_tertiles(df["NumericBurnoutScore"])
    return df


def prepare_dataframe(raw: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, object]]:
    """
    Full pipeline: schema check -> value check -> impute -> engineer.
    Raises SchemaError / DataValidationError with readable messages.
    Returns (df, report) where report lists imputation counts and notices.
    """
    validate_schema(raw)
    normalize_attrition(raw["Attrition"])  # raises early with a clear message
    issues = validate_values(raw)
    if issues:
        raise DataValidationError(issues)
    clean, imputed = impute_missing(raw)
    df = engineer_features(clean)
    notices: List[str] = []
    n_far = int((df["DistanceFromHome"] > DIST_MAX).sum())
    if n_far:
        notices.append(
            f"{n_far} employee(s) have DistanceFromHome above {DIST_MAX:g}; their "
            "commute points are capped at the maximum (20)."
        )
    return df, {"imputed": imputed, "notices": notices}


def load_csv_bytes(file_bytes: bytes) -> Tuple[pd.DataFrame, Dict[str, object]]:
    return prepare_dataframe(pd.read_csv(BytesIO(file_bytes)))


# --------------------------------------------------------------------------
# Grouping helpers
# --------------------------------------------------------------------------
def score_tertiles(score: pd.Series) -> Tuple[pd.Series, Tuple[float, float]]:
    """
    Burnout-score thirds with documented, reproducible, tie-safe thresholds.

    t1 = 33.333th percentile, t2 = 66.667th percentile of the score
    (linear interpolation). Assignment:
        score <= t1          -> Lowest third
        t1 < score <= t2     -> Middle third
        score > t2           -> Highest third
    Because many employees share identical scores, tied values always go to the
    same (lower) group, so groups are only approximately equal in size.
    Returns (categorical series, (t1, t2)).
    """
    t1, t2 = (float(x) for x in np.percentile(score.dropna(), [100 / 3, 200 / 3]))
    grp = pd.Series(
        np.select([score <= t1, score <= t2], TERTILE_LABELS[:2], default=TERTILE_LABELS[2]),
        index=score.index,
    )
    grp = grp.where(score.notna())
    return pd.Categorical(grp, categories=TERTILE_LABELS, ordered=True), (t1, t2)


def wilson_ci(k: int, n: int, z: float = 1.959964) -> Tuple[float, float]:
    """Wilson score interval for a proportion (returns fractions)."""
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def attrition_table(df: pd.DataFrame, by: str) -> pd.DataFrame:
    """
    Attrition counts and rate per group. Denominator = employees in that group
    (all employees with a valid attrition flag), never the whole company.
    """
    rows = []
    grouped = df.groupby(by, observed=True)
    for key, g in grouped:
        n = int(len(g))
        k = int(g["Attrition_Flag"].sum())
        lo, hi = wilson_ci(k, n)
        rows.append({
            by: key, "Employees": n, "Left": k,
            "AttritionRate_pct": round(100 * k / n, 2) if n else np.nan,
            "CI95_low_pct": round(100 * lo, 2), "CI95_high_pct": round(100 * hi, 2),
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Statistics
# --------------------------------------------------------------------------
def welch_ttest(a: pd.Series, b: pd.Series) -> Dict[str, float]:
    """Welch independent-samples t-test of mean(a) - mean(b) with 95% CI and
    Cohen's d (pooled SD)."""
    a = pd.Series(a).dropna().astype(float)
    b = pd.Series(b).dropna().astype(float)
    res = stats.ttest_ind(a, b, equal_var=False)
    ci = res.confidence_interval(0.95)
    n1, n2 = len(a), len(b)
    sp = np.sqrt(((n1 - 1) * a.var(ddof=1) + (n2 - 1) * b.var(ddof=1)) / (n1 + n2 - 2))
    return {
        "n_a": n1, "n_b": n2,
        "mean_a": float(a.mean()), "mean_b": float(b.mean()),
        "sd_a": float(a.std(ddof=1)), "sd_b": float(b.std(ddof=1)),
        "diff": float(a.mean() - b.mean()),
        "ci_low": float(ci.low), "ci_high": float(ci.high),
        "t": float(res.statistic), "df": float(res.df), "p": float(res.pvalue),
        "cohens_d": float((a.mean() - b.mean()) / sp),
    }


def holm_adjust(pvalues: List[float]) -> List[float]:
    """Holm-Bonferroni adjusted p-values (same order as input)."""
    p = np.asarray(pvalues, dtype=float)
    m = len(p)
    order = np.argsort(p)
    adj = np.empty(m)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (m - rank) * p[idx])
        adj[idx] = min(1.0, running)
    return adj.tolist()


def chi_square_with_effect(table: pd.DataFrame) -> Dict[str, float]:
    """Chi-square test of independence for a contingency table + Cramer's V."""
    chi2, p, dof, _ = stats.chi2_contingency(table.values, correction=False)
    n = table.values.sum()
    k = min(table.shape) - 1
    return {"chi2": float(chi2), "dof": int(dof), "p": float(p),
            "cramers_v": float(np.sqrt(chi2 / (n * k))) if n and k else np.nan}


def relative_risk(k1: int, n1: int, k0: int, n0: int, z: float = 1.959964) -> Dict[str, float]:
    """Relative risk of group 1 vs group 0 with log-method 95% CI."""
    if min(k1, k0) == 0:
        return {"rr": np.nan, "ci_low": np.nan, "ci_high": np.nan}
    rr = (k1 / n1) / (k0 / n0)
    se = np.sqrt(1 / k1 - 1 / n1 + 1 / k0 - 1 / n0)
    return {"rr": float(rr), "ci_low": float(np.exp(np.log(rr) - z * se)),
            "ci_high": float(np.exp(np.log(rr) + z * se))}


def auc_mann_whitney(score: pd.Series, flag: pd.Series) -> float:
    """In-sample ROC AUC of `score` for flag==1 (rank-based, ties handled)."""
    s = np.asarray(score, dtype=float)
    f = np.asarray(flag, dtype=int)
    pos, neg = s[f == 1], s[f == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    u = stats.mannwhitneyu(pos, neg, alternative="two-sided").statistic
    return float(u / (len(pos) * len(neg)))


def simple_ols(x: pd.Series, y: pd.Series) -> Dict[str, float]:
    """Simple linear regression y ~ x with slope CI (scipy.linregress)."""
    d = pd.concat([x, y], axis=1).dropna()
    r = stats.linregress(d.iloc[:, 0].astype(float), d.iloc[:, 1].astype(float))
    n = len(d)
    tcrit = stats.t.ppf(0.975, n - 2)
    return {"n": n, "slope": float(r.slope), "intercept": float(r.intercept),
            "slope_ci_low": float(r.slope - tcrit * r.stderr),
            "slope_ci_high": float(r.slope + tcrit * r.stderr),
            "r": float(r.rvalue), "r2": float(r.rvalue ** 2), "p": float(r.pvalue)}


def safe_rate(series: pd.Series) -> Optional[float]:
    """Mean of a 0/1 series as a percent, or None for an empty series."""
    return None if len(series) == 0 else float(series.mean() * 100)
