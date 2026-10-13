import os
from typing import List, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from scipy import stats

import hr_analytics as hr

# ---------------------------------------------------------------------------
# Constants used by the manager-action recommendations. They are simple
# heuristic cut-offs for the *filtered segment*, not validated clinical limits.
# ---------------------------------------------------------------------------
BURNOUT_ALERT = 70.0      # segment mean burnout score (0-100)
ENGAGEMENT_ALERT = 2.5    # segment mean engagement (1-4)
PROMOTION_ALERT = 3.0     # segment mean years since last promotion
WLB_ALERT = 2.5           # segment mean work-life balance (1-4)
ATTRITION_ALERT = 15.0    # segment observed attrition, percent
MIN_GROUP_FOR_TEST = 30   # minimum group size for the in-app Welch test

DISCLAIMER = (
    "⚠️ **Analytical flags, not diagnoses.** The burnout score and risk/priority "
    "labels are transparent rule-based indicators built from workload variables. "
    "They are not clinical measures, do not predict any individual's future, and "
    "must not be used alone for employment decisions."
)

PLOTLY_CONFIG = {
    "displayModeBar": False,
    "responsive": True,
    "scrollZoom": False,
}


def polish_chart(fig: go.Figure, height: int = 380,
                 showlegend: bool | None = None,
                 horizontal_legend: bool = False) -> go.Figure:
    fig.update_layout(
        template="plotly_white",
        height=height,
        autosize=True,
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        font=dict(family="Arial, sans-serif", size=12, color="#263238"),
        title=dict(
            x=0.02,
            xanchor="left",
            font=dict(size=16, color="#172B4D"),
        ),
        margin=dict(l=58, r=24, t=58, b=58),
        hoverlabel=dict(
            bgcolor="#172B4D",
            font_size=12,
            font_family="Arial, sans-serif",
        ),
        legend=dict(
            font=dict(size=11),
            bgcolor="rgba(255,255,255,0.90)",
            borderwidth=0,
        ),
    )
    axis_style = dict(
        showgrid=True,
        gridcolor="#E9EEF5",
        gridwidth=1,
        zeroline=False,
        showline=True,
        linecolor="#D7DEE8",
        tickfont=dict(size=11, color="#52606D"),
        title_font=dict(size=12, color="#344563"),
        automargin=True,
    )
    fig.update_xaxes(**axis_style)
    fig.update_yaxes(**axis_style)
    if showlegend is not None:
        fig.update_layout(showlegend=showlegend)
    if horizontal_legend:
        fig.update_layout(
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="left",
                x=0,
                font=dict(size=11),
                bgcolor="rgba(255,255,255,0)",
            )
        )
    return fig


def show_chart(fig: go.Figure, height: int = 380,
               showlegend: bool | None = None,
               horizontal_legend: bool = False) -> None:
    polish_chart(
        fig,
        height=height,
        showlegend=showlegend,
        horizontal_legend=horizontal_legend,
    )
    st.plotly_chart(fig, config=PLOTLY_CONFIG, width="stretch")


def scatter_with_trend(data: pd.DataFrame, **kwargs) -> go.Figure:
    """Scatter plot with an OLS trendline when statsmodels is installed (and the
    fit is possible); otherwise the same scatter without the trendline."""
    try:
        return px.scatter(data, trendline="ols", **kwargs)
    except Exception:
        return px.scatter(data, **kwargs)


st.set_page_config(
    page_title="HR Diagnostics Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ---------------------------------------------------------------------------
# Data loading (all logic lives in hr_analytics.py so it can be unit-tested)
# ---------------------------------------------------------------------------
@st.cache_data
def load_and_process_data(file_bytes: bytes):
    return hr.load_csv_bytes(file_bytes)


st.sidebar.markdown("### 📂 Dataset")

uploaded_file = st.sidebar.file_uploader(
    "Upload a CSV file",
    type=["csv"],
    help=(
        "Upload an employee HR CSV file with the same column structure as the "
        "default dataset. If no file is uploaded, the default dataset is used."
    ),
)

DEFAULT_DATASET = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Palo Alto Networks.csv")

if uploaded_file is not None:
    dataset_bytes = uploaded_file.getvalue()
    dataset_name = uploaded_file.name
    st.sidebar.success(f"Using: {dataset_name}")
else:
    try:
        with open(DEFAULT_DATASET, "rb") as default_file:
            dataset_bytes = default_file.read()
        dataset_name = os.path.basename(DEFAULT_DATASET)
        st.sidebar.info(f"Default: {dataset_name}")
    except FileNotFoundError:
        st.error(
            f"Default dataset '{os.path.basename(DEFAULT_DATASET)}' was not found. "
            "Please upload a CSV file from the sidebar."
        )
        st.stop()

try:
    df, load_report = load_and_process_data(dataset_bytes)
except hr.SchemaError as exc:
    st.error("❌ This CSV does not contain all required HR columns.")
    st.write("Missing columns:")
    st.code("\n".join(exc.missing))
    st.info(
        "Please upload a CSV with the same column structure as the default "
        "employee dataset."
    )
    st.stop()
except hr.DataValidationError as exc:
    st.error("❌ This CSV contains unexpected or out-of-range values.")
    for issue in exc.issues:
        st.write(f"- {issue}")
    st.info("Please correct the file and upload it again.")
    st.stop()
except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as exc:
    st.error(f"❌ The file could not be read as a CSV: {exc}")
    st.stop()

if load_report["imputed"]:
    st.sidebar.warning(
        "Missing values were filled (median for numbers, most frequent value for "
        "text): "
        + ", ".join(f"{c} ({n})" for c, n in load_report["imputed"].items())
    )
for notice in load_report["notices"]:
    st.sidebar.warning(notice)


roster_cols = [
    'Department', 'JobRole', 'PriorityLevel', 'EngagementIndex',
    'NumericBurnoutScore', 'WorkLifeBalance', 'OverTime', 'YearsAtCompany'
]


st.sidebar.markdown("### 🛡️ HR Analytics")
st.sidebar.markdown("---")

page = st.sidebar.radio("Dashboard Modules:", [
    "Executive Summary",
    "Department Scorecard",
    "Engagement Health Overview",
    "Burnout Risk Dashboard",
    "Role & Career Stage Analysis",
    "Manager Action Panel",
    "Documentation & Export"
])

st.sidebar.markdown("---")
st.sidebar.markdown("### Global Filters")


def present_in_order(series: pd.Series, order: List[str]) -> List[str]:
    values = set(series.dropna().unique().tolist())
    return [o for o in order if o in values]


dept_opts = df['Department'].unique().tolist()
selected_dept = st.sidebar.multiselect("Department", options=dept_opts, default=dept_opts)

avail_roles = df[df['Department'].isin(selected_dept)]['JobRole'].unique().tolist() if selected_dept else df['JobRole'].unique().tolist()
selected_roles = st.sidebar.multiselect("Job Role", options=avail_roles, default=avail_roles)

burnout_opts = present_in_order(df['BurnoutRisk'], ["Low", "Medium", "High"])
burnout_filter = st.sidebar.multiselect(
    "Burnout Risk", options=burnout_opts, default=burnout_opts,
    help="High = overtime AND work-life balance <= 2. Medium = overtime OR work-life balance <= 2. Low = neither.")

priority_opts = present_in_order(df['PriorityLevel'], ["Low", "Medium", "High", "Critical"])
priority_filter = st.sidebar.multiselect("Priority Level", options=priority_opts, default=priority_opts)

career_opts = present_in_order(df['CareerStage'], hr.CAREER_LABELS)
career_filter = st.sidebar.multiselect("Career Stage", options=career_opts, default=career_opts,
                                       help="By total working years: " + "; ".join(hr.CAREER_LABELS))

commute_opts = present_in_order(df['CommuteCategory'], hr.COMMUTE_LABELS)
commute_filter = st.sidebar.multiselect(
    "Commute Category", options=commute_opts, default=commute_opts,
    help="By DistanceFromHome (unit not documented in the dataset): " + "; ".join(hr.COMMUTE_LABELS))

gender_opts = df['Gender'].unique().tolist()
gender_filter = st.sidebar.multiselect("Gender", options=gender_opts, default=gender_opts)

marital_opts = df['MaritalStatus'].unique().tolist()
marital_filter = st.sidebar.multiselect("Marital Status", options=marital_opts, default=marital_opts)

edu_opts = sorted(df['Education'].unique().tolist())
edu_filter = st.sidebar.multiselect("Education Level (1-5)", options=edu_opts, default=edu_opts)

travel_opts = df['BusinessTravel'].unique().tolist()
travel_filter = st.sidebar.multiselect("Business Travel", options=travel_opts, default=travel_opts)

overtime_toggle = st.sidebar.checkbox("Show Overtime Employees Only", value=False)
engagement_threshold = st.sidebar.slider(
    "Max Engagement Score", min_value=1.0, max_value=4.0, value=4.0, step=0.1,
    help="Keeps employees whose Engagement Index is at or below this value.")

min_tenure = int(df['YearsAtCompany'].min())
max_tenure = int(df['YearsAtCompany'].max())
if min_tenure < max_tenure:
    tenure_range = st.sidebar.slider("Tenure Range (Years at Company)", min_value=min_tenure,
                                     max_value=max_tenure, value=(min_tenure, max_tenure))
else:
    tenure_range = (min_tenure, max_tenure)
    st.sidebar.caption(f"All employees have {min_tenure} year(s) at the company.")

st.sidebar.markdown("---")
st.sidebar.caption(DISCLAIMER)


mask = (
    df['Department'].isin(selected_dept) &
    df['JobRole'].isin(selected_roles) &
    df['BurnoutRisk'].isin(burnout_filter) &
    df['PriorityLevel'].isin(priority_filter) &
    df['CareerStage'].isin(career_filter) &
    df['CommuteCategory'].isin(commute_filter) &
    df['Gender'].isin(gender_filter) &
    df['MaritalStatus'].isin(marital_filter) &
    df['Education'].isin(edu_filter) &
    df['BusinessTravel'].isin(travel_filter) &
    (df['EngagementIndex'] <= engagement_threshold) &
    (df['YearsAtCompany'].between(tenure_range[0], tenure_range[1]))
)

if overtime_toggle:
    mask = mask & (df['OverTime'] == 'Yes')

filtered_df = df[mask]

if filtered_df.empty:
    st.warning("⚠️ No employees match the current filter criteria. Please adjust your filters in the sidebar.")
    st.stop()

st.caption(
    f"📂 Active dataset: **{dataset_name}**  •  "
    f"{len(df):,} records loaded  •  "
    f"{len(filtered_df):,} records after filters  •  "
    "All rates and averages below use the filtered records only."
)


def attrition_text(dff: pd.DataFrame) -> str:
    """'k of n (x.x%)' - the count, denominator and percentage together."""
    n = len(dff)
    k = int(dff['Attrition_Flag'].sum())
    return f"{k:,} of {n:,} ({(k / n * 100):.1f}%)" if n else "n/a"


def render_drill_down(dataframe: pd.DataFrame, title: str, filter_col: Optional[str] = None, filter_options: Optional[List[str]] = None) -> None:
    st.markdown("---")
    st.subheader(f"📋 Employee Drill-Down: {title}")

    if filter_col and filter_options is not None:
        col_filter1, _ = st.columns(2)
        with col_filter1:
            selected_val = st.selectbox(f"Filter by {filter_col}:", options=filter_options)
        display_df = dataframe[dataframe[filter_col] == selected_val]
    else:
        display_df = dataframe

    if display_df.empty:
        st.info("No employees found matching this specific drill-down criteria.")
    else:
        st.caption(f"{len(display_df):,} employees shown, sorted by lowest engagement first.")
        st.dataframe(display_df[roster_cols].sort_values(by="EngagementIndex"), hide_index=True, width="stretch")


def render_insights_engine(dff: pd.DataFrame) -> None:
    st.markdown("---")
    st.subheader("🧠 Auto-Generated Business Insights")
    st.caption("Descriptive observations about the filtered records. They describe associations, not causes.")

    insights = []

    if not dff.empty:
        by_dept = dff.groupby('Department', observed=True)['NumericBurnoutScore'].mean()
        insights.append(f"**{by_dept.idxmax()}** has the highest average burnout score ({by_dept.max():.1f}) among the departments shown.")

        by_dept_e = dff.groupby('Department', observed=True)['EngagementIndex'].mean()
        insights.append(f"**{by_dept_e.idxmax()}** has the highest average engagement ({by_dept_e.max():.2f} / 4.0) among the departments shown.")

    ot = dff.loc[dff['OverTime'] == 'Yes', 'EngagementIndex']
    no_ot = dff.loc[dff['OverTime'] == 'No', 'EngagementIndex']
    if len(ot) >= MIN_GROUP_FOR_TEST and len(no_ot) >= MIN_GROUP_FOR_TEST:
        w = hr.welch_ttest(ot, no_ot)
        direction = "higher" if w['diff'] > 0 else "lower"
        insights.append(
            f"Employees working overtime (n={w['n_a']:,}) have **{direction}** average engagement than those who do not "
            f"(n={w['n_b']:,}): difference {w['diff']:+.2f} points (95% CI {w['ci_low']:+.2f} to {w['ci_high']:+.2f}, "
            f"Welch p = {w['p']:.3f})."
        )
    else:
        insights.append("Too few overtime / non-overtime employees in the current filter to compare engagement reliably.")

    long_c = dff.loc[dff['CommuteCategory'] == hr.COMMUTE_LABELS[2], 'NumericBurnoutScore']
    short_c = dff.loc[dff['CommuteCategory'] == hr.COMMUTE_LABELS[0], 'NumericBurnoutScore']
    if len(long_c) and len(short_c):
        insights.append(
            f"Average burnout score is **{long_c.mean():.1f}** for {hr.COMMUTE_LABELS[2]} commutes versus "
            f"**{short_c.mean():.1f}** for {hr.COMMUTE_LABELS[0]}. This gap is partly built into the score "
            "(commute distance contributes up to 20 of its 100 points), so it is not independent evidence."
        )

    if len(dff):
        insights.append(f"Observed attrition in the filtered segment: **{attrition_text(dff)}**.")

    for i, insight in enumerate(insights):
        st.markdown(f"{i+1}. {insight}")


def render_executive_summary(dff: pd.DataFrame) -> None:
    st.title("📈 Executive Summary")
    st.markdown("High-level overview of organizational health and key risk metrics.")
    st.caption(DISCLAIMER)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Workforce", f"{len(dff):,}", help="Employees matching the current filters.")
    c2.metric("Avg Engagement", f"{dff['EngagementIndex'].mean():.2f} / 4.0",
              help="Mean of JobInvolvement, JobSatisfaction, EnvironmentSatisfaction and RelationshipSatisfaction (each 1-4).")
    c3.metric("Avg Burnout Score", f"{dff['NumericBurnoutScore'].mean():.1f} / 100",
              help="Rule-based indicator: overtime (30) + work-life balance deficit (30) + travel (20) + commute distance (20). Not a clinical measure.")
    c4.metric("Avg Satisfaction", f"{dff['JobSatisfaction'].mean():.2f} / 4.0", help="Mean JobSatisfaction (1-4).")

    st.write("")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Avg Work-Life Balance", f"{dff['WorkLifeBalance'].mean():.2f} / 4.0", help="Mean WorkLifeBalance (1 = poor, 4 = excellent).")
    c6.metric("Attrition Rate", f"{(dff['Attrition_Flag'].mean() * 100):.1f}%",
              help=f"Employees who left / employees in the filter: {attrition_text(dff)}.")
    c7.metric("Critical-Priority Flags", f"{int((dff['PriorityLevel'] == 'Critical').sum()):,}",
              help="High burnout-risk label AND engagement <= 2.2. A flag for human review, not a diagnosis.")
    c8.metric("Avg Monthly Income", f"${dff['MonthlyIncome'].mean():,.0f}", help="Mean MonthlyIncome in the dataset's currency units.")

    st.markdown("---")

    st.subheader("🏆 Department Rankings & Risks")
    st.caption("Rankings compare departments inside the filtered records; check the Department Scorecard for group sizes.")
    rank_c1, rank_c2, rank_c3, rank_c4 = st.columns(4)

    with rank_c1:
        top_risk_dept = dff.groupby('Department', observed=True)['NumericBurnoutScore'].mean().idxmax()
        st.error(f"**Highest Avg Burnout Score:**\n\n{top_risk_dept}")
    with rank_c2:
        low_eng_dept = dff.groupby('Department', observed=True)['EngagementIndex'].mean().idxmin()
        st.warning(f"**Lowest Avg Engagement:**\n\n{low_eng_dept}")
    with rank_c3:
        high_attr_dept = dff.groupby('Department', observed=True)['Attrition_Flag'].mean().idxmax()
        st.error(f"**Highest Observed Attrition:**\n\n{high_attr_dept}")
    with rank_c4:
        top_role = dff.groupby('JobRole', observed=True)['NumericBurnoutScore'].mean().idxmax()
        st.warning(f"**Highest Avg Burnout Score (Role):**\n\n{top_role}")

    st.markdown("---")

    st.subheader("📊 Organization-Wide Distributions")
    dist_c1, dist_c2, dist_c3 = st.columns(3)

    with dist_c1:
        fig_pie = px.pie(dff, names='PriorityLevel', hole=0.4, title="Priority Distribution",
                         color='PriorityLevel',
                         color_discrete_map={"Critical": "#8B0000", "High": "#EF553B", "Medium": "#FFA15A", "Low": "#00CC96"})
        fig_pie.update_layout(template="plotly_white", margin=dict(t=40, b=10))
        show_chart(fig_pie, height=330)

    with dist_c2:
        fig_b_dist = px.histogram(dff, x="NumericBurnoutScore", nbins=20, title="Burnout Score Distribution",
                                  color_discrete_sequence=["#EF553B"], template="plotly_white")
        fig_b_dist.update_layout(yaxis_title="Employees", xaxis_title="Burnout Score (0-100)", margin=dict(t=40, b=10))
        show_chart(fig_b_dist, height=350)

    with dist_c3:
        fig_e_dist = px.histogram(dff, x="EngagementIndex", nbins=15, title="Engagement Distribution",
                                  color_discrete_sequence=["#1F77B4"], template="plotly_white")
        fig_e_dist.update_layout(yaxis_title="Employees", xaxis_title="Engagement Index (1-4)", margin=dict(t=40, b=10))
        show_chart(fig_e_dist, height=350)

    render_insights_engine(dff)


def render_department_scorecard(dff: pd.DataFrame) -> None:
    st.title("🏢 Department Scorecard")
    st.markdown("Comprehensive breakdown of key HR metrics isolated by department.")

    scorecard = dff.groupby("Department", observed=True).agg(
        Employee_Count=("Age", "count"),
        Avg_Engagement=("EngagementIndex", "mean"),
        Avg_Burnout=("NumericBurnoutScore", "mean"),
        Avg_Satisfaction=("JobSatisfaction", "mean"),
        Avg_WLB=("WorkLifeBalance", "mean"),
        Employees_Left=("Attrition_Flag", "sum"),
        Attrition_Rate=("Attrition_Flag", "mean"),
        Critical_Flags=("PriorityLevel", lambda x: (x == 'Critical').sum())
    ).reset_index()

    scorecard['Attrition_Rate (%)'] = (scorecard['Attrition_Rate'] * 100).round(1)
    scorecard['Imbalance_Ratio'] = (scorecard['Avg_Burnout'] / scorecard['Avg_Engagement']).round(2)
    scorecard.drop(columns=['Attrition_Rate'], inplace=True)

    for col in ['Avg_Engagement', 'Avg_Burnout', 'Avg_Satisfaction', 'Avg_WLB']:
        scorecard[col] = scorecard[col].round(2)

    st.markdown("---")

    styled_df = scorecard.style.background_gradient(
        subset=['Avg_Burnout', 'Attrition_Rate (%)', 'Imbalance_Ratio', 'Critical_Flags'], cmap='Reds'
    ).background_gradient(
        subset=['Avg_Engagement', 'Avg_Satisfaction', 'Avg_WLB'], cmap='Greens'
    )

    st.dataframe(styled_df, width="stretch", hide_index=True)
    st.caption("Attrition_Rate (%) = Employees_Left / Employee_Count within each department (filtered records). "
               "Small departments give unstable percentages, so read them together with Employee_Count.")

    st.markdown("---")
    st.info("💡 **Note on Imbalance Ratio:** calculated as `Average Burnout Score / Average Engagement`. It is a "
            "descriptive heuristic for comparing departments; higher values mean a higher burnout score relative to "
            "engagement. It is not a validated index.")

    render_insights_engine(dff)


def render_engagement(dff: pd.DataFrame) -> None:
    st.title("📊 Engagement Health Overview")

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Employees", f"{len(dff):,}")
    col2.metric("Avg Engagement", f"{dff['EngagementIndex'].mean():.2f} / 4.0")
    col3.metric("Avg Job Satisfaction", f"{dff['JobSatisfaction'].mean():.2f} / 4.0")
    col4.metric("Avg WLB Index", f"{dff['WorkLifeBalanceIndex'].mean()*100:.0f}%",
                help="WorkLifeBalance divided by 4, shown as a percentage.")
    col5.metric("Avg Burnout Score", f"{dff['NumericBurnoutScore'].mean():.1f} / 100")
    st.markdown("---")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Organization Engagement Level")
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = dff['EngagementIndex'].mean(),
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "Average Engagement (1-4)"},
            gauge = {
                'axis': {'range': [1, 4]},
                'bar': {'color': "#1F77B4"},
                'steps': [
                    {'range': [1, 2], 'color': "#FFCCCB"},
                    {'range': [2, 3], 'color': "#FFFFE0"},
                    {'range': [3, 4], 'color': "#E0FFFF"}]
            }))
        fig_gauge.update_layout(template="plotly_white", height=350, margin=dict(t=40, b=10))
        show_chart(fig_gauge, height=340)

    with c2:
        st.subheader("Engagement Distribution")
        fig_eng = px.histogram(
            dff,
            x="EngagementIndex",
            nbins=12,
            title="Engagement Score Distribution",
            color_discrete_sequence=["#2F6BFF"],
        )
        fig_eng.update_layout(
            yaxis_title="Employees",
            xaxis_title="Engagement Score (1–4)",
            bargap=0.08,
        )
        show_chart(fig_eng, height=350)

    c3, c4 = st.columns([1, 2.2])

    with c3:
        st.subheader("Department Ranking")
        dept_eng = dff.groupby('Department', observed=True)['EngagementIndex'].mean().sort_values().reset_index()
        fig_rank = px.bar(dept_eng, x='EngagementIndex', y='Department', orientation='h',
                          color='EngagementIndex', color_continuous_scale="Blues", template="plotly_white")
        fig_rank.update_layout(xaxis_title="Avg Engagement Score (1-4)", yaxis_title="", coloraxis_showscale=False)
        fig_rank.update_xaxes(range=[1.0, 4.0])
        show_chart(fig_rank, height=380)

    with c4:
        st.subheader("Comprehensive Driver Correlation Matrix")
        st.caption("Pearson correlations. The burnout score is built from overtime, work-life balance, travel and "
                   "distance, so its correlation with those inputs is partly by construction.")
        corr_cols = [
            'Age', 'MonthlyIncome', 'DistanceFromHome', 'JobInvolvement',
            'JobSatisfaction', 'EnvironmentSatisfaction', 'RelationshipSatisfaction',
            'EngagementIndex', 'NumericBurnoutScore', 'WorkLifeBalance',
            'YearsAtCompany', 'YearsInCurrentRole', 'YearsSinceLastPromotion',
            'TotalWorkingYears', 'PerformanceRating', 'TrainingTimesLastYear'
        ]

        corr_matrix = dff[corr_cols].corr().round(2)

        fig_corr = px.imshow(
            corr_matrix,
            text_auto=".2f",
            aspect="auto",
            color_continuous_scale="RdBu_r",
            zmin=-1, zmax=1,
            template="plotly_white"
        )

        fig_corr.update_layout(
            height=700,
            xaxis_tickangle=-45,
            margin=dict(t=20, b=100, l=20, r=20),
            xaxis_title="",
            yaxis_title=""
        )
        fig_corr.update_traces(textfont_size=9)

        show_chart(fig_corr, height=620)

    st.markdown("---")

    st.subheader("🚪 Advanced Attrition Analytics")
    st.caption("Bars show employee counts. For rates, see the tables in the Burnout Risk and Scorecard pages "
               f"(overall in this filter: {attrition_text(dff)}).")
    attr_c1, attr_c2, attr_c3 = st.columns(3)

    with attr_c1:
        st.write("**Attrition by Department**")
        fig_attr_dept = px.histogram(dff, x="Department", color="Attrition_Label", barmode="group",
                                     color_discrete_map={"Left Company": "#E45756", "Stayed": "#4C78A8"}, template="plotly_white")
        fig_attr_dept.update_layout(yaxis_title="Employees", margin=dict(t=20, b=10))
        show_chart(fig_attr_dept, height=350)

        st.write("**Attrition by Job Level**")
        fig_attr_lvl = px.histogram(dff, x="JobLevel", color="Attrition_Label", barmode="group",
                                    color_discrete_map={"Left Company": "#E45756", "Stayed": "#4C78A8"}, template="plotly_white")
        fig_attr_lvl.update_layout(yaxis_title="Employees", margin=dict(t=20, b=10))
        show_chart(fig_attr_lvl, height=330)

    with attr_c2:
        st.write("**Attrition by Burnout Risk Label**")
        fig_attr_burn = px.histogram(dff, x="BurnoutRisk", color="Attrition_Label", barmode="group",
                                     category_orders={"BurnoutRisk": ["Low", "Medium", "High"]},
                                     color_discrete_map={"Left Company": "#E45756", "Stayed": "#4C78A8"}, template="plotly_white")
        fig_attr_burn.update_layout(yaxis_title="Employees", margin=dict(t=20, b=10))
        show_chart(fig_attr_burn, height=330)

        st.write("**Attrition by Career Stage**")
        fig_attr_stage = px.histogram(dff, x="CareerStage", color="Attrition_Label", barmode="group",
                                      category_orders={"CareerStage": hr.CAREER_LABELS},
                                      color_discrete_map={"Left Company": "#E45756", "Stayed": "#4C78A8"}, template="plotly_white")
        fig_attr_stage.update_layout(yaxis_title="Employees", margin=dict(t=20, b=10))
        show_chart(fig_attr_stage, height=330)

    with attr_c3:
        st.write("**Attrition by Work Life Balance**")
        fig_attr_wlb = px.histogram(dff, x="WorkLifeBalance", color="Attrition_Label", barmode="group",
                                    color_discrete_map={"Left Company": "#E45756", "Stayed": "#4C78A8"}, template="plotly_white")
        fig_attr_wlb.update_layout(yaxis_title="Employees", margin=dict(t=20, b=10))
        show_chart(fig_attr_wlb, height=330)

        st.write("**Attrition by Overtime**")
        fig_attr_ot = px.histogram(dff, x="OverTime", color="Attrition_Label", barmode="group",
                                   color_discrete_map={"Left Company": "#E45756", "Stayed": "#4C78A8"}, template="plotly_white")
        fig_attr_ot.update_layout(yaxis_title="Employees", margin=dict(t=20, b=10))
        show_chart(fig_attr_ot, height=330)

    st.markdown("---")

    st.subheader("⚖️ Satisfaction Stability Dashboard")
    stab_c1, stab_c2 = st.columns(2)

    with stab_c1:
        st.write(f"**Average Stability Score:** {dff['SatisfactionStabilityScore'].mean():.2f} / 4.0")
        st.caption("Stability = 4 minus the standard deviation of the four satisfaction/involvement items "
                   "(higher = more consistent answers).")
        fig_stab_dist = px.histogram(dff, x="SatisfactionStabilityScore", nbins=15, title="Stability Score Distribution",
                                     template="plotly_white", color_discrete_sequence=["#8c564b"])
        fig_stab_dist.update_layout(yaxis_title="Employees", margin=dict(t=30, b=10))
        show_chart(fig_stab_dist, height=330)

        fig_stab_dept = px.box(dff, x="Department", y="SatisfactionStabilityScore", color="Department",
                               title="Stability by Department", template="plotly_white")
        fig_stab_dept.update_layout(margin=dict(t=30, b=10))
        show_chart(fig_stab_dept, height=360)

    with stab_c2:
        fig_stab_burn = scatter_with_trend(
            dff,
            x="NumericBurnoutScore",
            y="SatisfactionStabilityScore",
            color="BurnoutRisk",
            title="Stability vs. Burnout Score",
            opacity=0.72,
            render_mode="svg",
            category_orders={"BurnoutRisk": ["Low", "Medium", "High"]},
            color_discrete_map={"Low": "#19A974", "Medium": "#F2A93B", "High": "#E45756"},
        )
        fig_stab_burn.update_layout(margin=dict(t=30, b=10))
        show_chart(fig_stab_burn, height=360)

        fig_stab_attr = px.violin(dff, x="Attrition_Label", y="SatisfactionStabilityScore", color="Attrition_Label",
                                  box=True, title="Stability vs. Attrition", color_discrete_map={"Left Company": "#E45756", "Stayed": "#4C78A8"},
                                  template="plotly_white")
        fig_stab_attr.update_layout(margin=dict(t=30, b=10))
        show_chart(fig_stab_attr, height=360)

    render_drill_down(dff, "Attrition & Engagement", "Attrition_Label", dff['Attrition_Label'].dropna().unique().tolist())
    render_insights_engine(dff)


def render_burnout(dff: pd.DataFrame) -> None:
    st.title("🔥 Burnout Risk Dashboard")
    st.caption(DISCLAIMER)

    high_risk = int((dff['BurnoutRisk'] == 'High').sum())
    st.metric("Employees with HIGH Burnout-Risk Label", f"{high_risk:,}",
              help=f"{high_risk / len(dff) * 100:.1f}% of the {len(dff):,} filtered employees. "
                   "High = overtime AND work-life balance <= 2.")
    st.markdown("---")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Burnout Risk by Department")
        fig_burnout = px.histogram(dff, x="Department", color="BurnoutRisk", barmode="group",
                                   category_orders={"BurnoutRisk": ["Low", "Medium", "High"]},
                                   color_discrete_map={"Low": "#00CC96", "Medium": "#FFA15A", "High": "#EF553B"},
                                   template="plotly_white")
        fig_burnout.update_layout(yaxis_title="Employee Count", bargroupgap=0.1)
        show_chart(fig_burnout, height=400)

    with c2:
        st.subheader("Burnout Score Distribution")
        fig_b_dist = px.histogram(dff, x="NumericBurnoutScore", nbins=20, marginal="box",
                                  color_discrete_sequence=["#EF553B"], template="plotly_white")
        fig_b_dist.update_layout(xaxis_title="Burnout Score (0-100)", yaxis_title="Employees")
        show_chart(fig_b_dist, height=350)

    st.markdown("---")
    st.subheader("📉 Observed Attrition by Burnout-Score Group")
    thresholds = (
        float(df.loc[df['ScoreGroup'] == hr.TERTILE_LABELS[0], 'NumericBurnoutScore'].max()),
        float(df.loc[df['ScoreGroup'] == hr.TERTILE_LABELS[1], 'NumericBurnoutScore'].max()),
    )
    st.caption(
        f"Groups are thirds of the burnout score in the **full loaded dataset** (so they stay the same when you change filters): "
        f"Lowest third ≤ {thresholds[0]:.2f}; Middle third ≤ {thresholds[1]:.2f}; Highest third above that. "
        "Tied scores always fall in the same group, so group sizes are only approximately equal. "
        "Rates below use the employees of each group inside the current filter as the denominator."
    )
    tert_tbl = hr.attrition_table(dff, "ScoreGroup")
    if tert_tbl.empty:
        st.info("No employees available for this comparison under the current filters.")
    else:
        tc1, tc2 = st.columns([1, 1.2])
        with tc1:
            show_tbl = tert_tbl.rename(columns={
                "ScoreGroup": "Score group", "Left": "Employees left",
                "AttritionRate_pct": "Attrition (%)",
                "CI95_low_pct": "95% CI low (%)", "CI95_high_pct": "95% CI high (%)"})
            st.dataframe(show_tbl, hide_index=True, width="stretch")
        with tc2:
            fig_tert = px.bar(tert_tbl, x="ScoreGroup", y="AttritionRate_pct", text="AttritionRate_pct",
                              color="ScoreGroup",
                              category_orders={"ScoreGroup": hr.TERTILE_LABELS},
                              color_discrete_sequence=["#00CC96", "#FFA15A", "#EF553B"],
                              template="plotly_white")
            fig_tert.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig_tert.update_layout(xaxis_title="", yaxis_title="Observed attrition (%)", showlegend=False)
            show_chart(fig_tert, height=330)
        st.info("This is an **association within this dataset** (attrition is already recorded, not forecast). "
                "It is not evidence that the score predicts future departures; that would require data over time "
                "and out-of-sample testing. Much of the highest group consists of employees who work overtime, "
                "and overtime alone is strongly related to attrition here.")

    c3, c4 = st.columns(2)
    with c3:
        st.subheader("Commute vs. Burnout Score")
        st.caption("The score includes commute distance (up to 20 points), so this gap exists partly by construction.")
        fig_commute = px.box(dff, x="CommuteCategory", y="NumericBurnoutScore", color="CommuteCategory",
                             template="plotly_white", category_orders={"CommuteCategory": hr.COMMUTE_LABELS})
        fig_commute.update_layout(showlegend=False, xaxis_title="Commute category (distance from home)",
                                  yaxis_title="Burnout Score (0-100)")
        show_chart(fig_commute, height=380)

    with c4:
        st.subheader("Travel Frequency vs. Engagement")
        fig_travel = px.box(dff, x="BusinessTravel", y="EngagementIndex", color="BusinessTravel", template="plotly_white")
        fig_travel.update_layout(yaxis_title="Engagement Index (1-4)", showlegend=False)
        show_chart(fig_travel, height=380)

    st.markdown("---")

    st.subheader("⚖️ Work-Life Balance Analytics")
    wlb_c1, wlb_c2, wlb_c3 = st.columns(3)

    with wlb_c1:
        st.write(f"**Average WLB Score:** {dff['WorkLifeBalance'].mean():.2f} / 4.0")
        fig_wlb_dist = px.histogram(dff, x="WorkLifeBalance", nbins=4, template="plotly_white", color_discrete_sequence=["#9467bd"])
        fig_wlb_dist.update_layout(yaxis_title="Employees")
        fig_wlb_dist.update_xaxes(dtick=1, tickmode="linear")
        show_chart(fig_wlb_dist, height=330)

        fig_wlb_dept = px.box(dff, x="Department", y="WorkLifeBalance", color="Department", title="WLB by Department", template="plotly_white")
        fig_wlb_dept.update_layout(margin=dict(t=30, b=10))
        show_chart(fig_wlb_dept, height=360)

    with wlb_c2:
        st.write("**Workload Stress vs WLB Heatmap**")
        fig_stress = px.density_heatmap(dff, x="WorkloadStressIndicator", y="WorkLifeBalance",
                                        text_auto=True, color_continuous_scale="Reds", template="plotly_white")
        fig_stress.update_layout(
            xaxis_title="Workload Stress (0 = Low, 4 = High)",
            yaxis_title="Work-Life Balance (1 = Poor)",
        )
        show_chart(fig_stress, height=360)

        fig_wlb_attr = px.histogram(dff, x="WorkLifeBalance", color="Attrition_Label", barmode="group",
                                    title="WLB vs Attrition (employee counts)", color_discrete_map={"Left Company": "#E45756", "Stayed": "#4C78A8"}, template="plotly_white")
        fig_wlb_attr.update_layout(yaxis_title="Employees", margin=dict(t=30, b=10))
        show_chart(fig_wlb_attr, height=360)

    with wlb_c3:
        fig_wlb_burn = px.scatter(
            dff,
            x="WorkLifeBalance",
            y="NumericBurnoutScore",
            color="BurnoutRisk",
            title="WLB vs Burnout Score (partly by construction)",
            opacity=0.72,
            render_mode="svg",
            category_orders={"BurnoutRisk": ["Low", "Medium", "High"]},
            color_discrete_map={"Low": "#19A974", "Medium": "#F2A93B", "High": "#E45756"},
        )
        fig_wlb_burn.update_layout(margin=dict(t=30, b=10))
        show_chart(fig_wlb_burn, height=360)

        fig_wlb_role = px.box(
            dff,
            x="WorkLifeBalance",
            y="JobRole",
            orientation="h",
            color="JobRole",
            title="Work-Life Balance by Job Role",
        )
        fig_wlb_role.update_layout(showlegend=False)
        show_chart(fig_wlb_role, height=430)

    render_drill_down(dff, "Burnout Roster", "BurnoutRisk", [r for r in ["High", "Medium", "Low"] if r in set(dff['BurnoutRisk'].astype(str))])
    render_insights_engine(dff)


def render_career(dff: pd.DataFrame) -> None:
    st.title("📈 Role & Career Stage Analysis")
    st.markdown("---")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Average Engagement by Job Role")
        role_eng_df = dff.groupby('JobRole', observed=True)['EngagementIndex'].mean().reset_index().sort_values('EngagementIndex')
        fig_role = px.bar(role_eng_df, x="EngagementIndex", y="JobRole", orientation='h',
                          color="EngagementIndex", color_continuous_scale="Blues", template="plotly_white")
        fig_role.update_layout(xaxis_title="Avg Engagement Score (1-4)", yaxis_title="", coloraxis_showscale=False)
        fig_role.update_xaxes(range=[1.0, 4.0])
        show_chart(fig_role, height=440)

    with c2:
        st.subheader("Engagement by Job Level")
        lvl_df = dff.assign(JobLevelLabel=dff['JobLevel'].astype(str))
        fig_lvl = px.box(lvl_df, x="JobLevelLabel", y="EngagementIndex", color="JobLevelLabel", template="plotly_white",
                         category_orders={"JobLevelLabel": sorted(lvl_df['JobLevelLabel'].unique())})
        fig_lvl.update_layout(xaxis_title="Job Level", yaxis_title="Engagement Index (1-4)", showlegend=False)
        show_chart(fig_lvl, height=380)

    c3, c4 = st.columns(2)
    with c3:
        st.subheader("Tenure vs Engagement Trends")
        tenure_df = dff.groupby('YearsAtCompany')['EngagementIndex'].agg(['mean', 'count']).reset_index()
        fig_tenure = px.line(tenure_df, x="YearsAtCompany", y="mean", markers=True,
                             template="plotly_white", hover_data={"count": True})
        fig_tenure.update_layout(xaxis_title="Years at Company", yaxis_title="Avg Engagement Score (1-4)")
        show_chart(fig_tenure, height=380)
        st.caption("Long-tenure points rest on few employees (see hover for counts), so they fluctuate.")

    with c4:
        st.subheader("Career Stage Analysis")
        fig_stage = px.histogram(dff, x="CareerStage", y="EngagementIndex", histfunc="avg",
                                 color="CareerStage", template="plotly_white",
                                 category_orders={"CareerStage": hr.CAREER_LABELS})
        fig_stage.update_layout(yaxis_title="Avg Engagement Score (1-4)", xaxis_title="Career stage (total working years)",
                                showlegend=False)
        show_chart(fig_stage, height=380)

    c5, c6 = st.columns(2)
    with c5:
        st.subheader("Years in Current Role vs. Engagement")
        fig_in_role = scatter_with_trend(dff, x="YearsInCurrentRole", y="EngagementIndex", color="BurnoutRisk",
                                         template="plotly_white", opacity=0.6,
                                         category_orders={"BurnoutRisk": ["Low", "Medium", "High"]})
        show_chart(fig_in_role, height=380)

    with c6:
        st.subheader("Promotion Stagnation Analysis")
        fig_promo = px.scatter(
            dff,
            x="YearsSinceLastPromotion",
            y="EngagementIndex",
            color="PriorityLevel",
            title="Years Since Last Promotion vs. Engagement",
            render_mode="svg",
            opacity=0.72,
            color_discrete_map={"Critical": "#8B0000", "High": "#EF553B", "Medium": "#FFA15A", "Low": "#00CC96"})
        show_chart(fig_promo, height=380)
        if dff['YearsSinceLastPromotion'].nunique() > 1 and dff['EngagementIndex'].nunique() > 1 and len(dff) > 10:
            rho, p = stats.spearmanr(dff['YearsSinceLastPromotion'], dff['EngagementIndex'])
            st.caption(f"Spearman correlation in the filtered records: rho = {rho:+.3f} (p = {p:.3f}, n = {len(dff):,}). "
                       "An association measure only; it says nothing about cause.")

    render_drill_down(dff, "Job Roles", "JobRole", dff['JobRole'].unique().tolist())
    render_insights_engine(dff)


def render_action_panel(dff: pd.DataFrame) -> None:
    st.title("🚨 Manager Action Panel")
    st.markdown("Rule-based prioritization to help HR decide where to start supportive conversations, based on workload and engagement signals.")
    st.warning(DISCLAIMER)
    st.markdown("---")

    c1, c2, c3, c4 = st.columns(4)
    c1.error(f"🔴 Critical Priority: {len(dff[dff['PriorityLevel'] == 'Critical']):,}")
    c2.warning(f"🟠 High Priority: {len(dff[dff['PriorityLevel'] == 'High']):,}")
    c3.info(f"🟡 Medium Priority: {len(dff[dff['PriorityLevel'] == 'Medium']):,}")
    c4.success(f"🟢 Low Priority: {len(dff[dff['PriorityLevel'] == 'Low']):,}")

    st.markdown("---")

    st.subheader("🤖 Suggested HR Follow-Ups (segment level)")
    st.caption("Triggered by simple cut-offs on the filtered segment's averages. Cut-offs are heuristics, not validated thresholds.")
    avg_burnout = dff['NumericBurnoutScore'].mean()
    avg_eng = dff['EngagementIndex'].mean()
    avg_promo = dff['YearsSinceLastPromotion'].mean()
    avg_wlb = dff['WorkLifeBalance'].mean()
    attr_rate = dff['Attrition_Flag'].mean() * 100

    if dff.empty:
        st.info("No data available for recommendations based on current filters.")
    else:
        shown = False
        if avg_burnout > BURNOUT_ALERT:
            st.error(f"🚨 **High average burnout score ({avg_burnout:.1f}/100):** Consider reviewing workload and overtime patterns and checking team capacity.")
            shown = True
        if avg_eng < ENGAGEMENT_ALERT:
            st.warning(f"⚠️ **Low average engagement ({avg_eng:.2f}/4.0):** Consider manager check-ins and a short pulse survey to understand what is behind it.")
            shown = True
        if avg_promo > PROMOTION_ALERT:
            st.info(f"ℹ️ **Long average wait since last promotion ({avg_promo:.1f} years):** Consider a career-path conversation review for this segment.")
            shown = True
        if avg_wlb < WLB_ALERT:
            st.warning(f"⚠️ **Low average work-life balance ({avg_wlb:.2f}/4.0):** Consider discussing flexible or hybrid arrangements with the team.")
            shown = True
        if attr_rate > ATTRITION_ALERT:
            st.error(f"🚨 **Elevated observed attrition ({attrition_text(dff)}):** Consider reviewing exit feedback and holding supportive stay conversations.")
            shown = True
        if not shown:
            st.success("✅ **No segment-level alerts:** averages are within the heuristic cut-offs. Continue standard HR monitoring.")

    st.markdown("---")

    st.subheader("⚠️ Top 20 Highest Burnout Scores (Review Queue)")
    st.caption("Employees with the highest rule-based burnout scores in the filter. This list is a starting point for "
               "supportive conversations, not a prediction that anyone will leave or burn out. "
               "Exports contain individual-level records: handle them confidentially.")

    risk_cols = ['Department', 'JobRole', 'NumericBurnoutScore', 'PriorityLevel', 'EngagementIndex',
                 'YearsAtCompany', 'YearsSinceLastPromotion', 'OverTime', 'WorkLifeBalance']

    risk_df = dff.sort_values(by='NumericBurnoutScore', ascending=False).head(20)[risk_cols]

    if not risk_df.empty:
        styled_risk = risk_df.style.background_gradient(subset=['NumericBurnoutScore'], cmap='Reds') \
                                   .background_gradient(subset=['EngagementIndex', 'WorkLifeBalance'], cmap='Reds_r')
        st.dataframe(styled_risk, hide_index=True, width="stretch")

        csv_risk = risk_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Top 20 Review Queue (CSV)",
            data=csv_risk,
            file_name='top_20_burnout_score_review_queue.csv',
            mime='text/csv',
        )
    else:
        st.success("No employees found in the current filter.")

    st.markdown("---")

    st.subheader("All High & Medium Priority Follow-Ups")
    action_df = dff[dff['PriorityLevel'].isin(['High', 'Medium'])].sort_values(by='NumericBurnoutScore', ascending=False)
    if not action_df.empty:
        st.caption(f"{len(action_df):,} employees flagged High or Medium priority in the current filter.")
        st.dataframe(action_df[roster_cols], hide_index=True, width="stretch")

        csv_all = action_df[roster_cols].to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Full Follow-Up List (CSV)",
            data=csv_all,
            file_name='all_followups.csv',
            mime='text/csv',
        )
    else:
        st.info("No High or Medium priority employees in the current filter.")

    render_insights_engine(dff)


def methodology_markdown() -> str:
    t1 = float(df.loc[df['ScoreGroup'] == hr.TERTILE_LABELS[0], 'NumericBurnoutScore'].max())
    t2 = float(df.loc[df['ScoreGroup'] == hr.TERTILE_LABELS[1], 'NumericBurnoutScore'].max())
    return f"""
### Methodology & Limitations

**Engagement Index (1-4).** Row-wise mean of JobInvolvement, JobSatisfaction, EnvironmentSatisfaction and RelationshipSatisfaction.

**Satisfaction Stability Score.** `4.0 - standard deviation` of those same four items.

**Numeric Burnout Score (0-100)** - a transparent, rule-based indicator (not a clinical measure, not a trained model):

```text
Overtime points   = 30 if OverTime == "Yes" else 0
WLB points        = ((4 - WorkLifeBalance) / 3) * 30
Travel points     = (code / 2) * 20      code: Non-Travel=0, Travel_Rarely=1, Travel_Frequently=2
Distance points   = clip((DistanceFromHome - {hr.DIST_MIN:g}) / ({hr.DIST_MAX:g} - {hr.DIST_MIN:g}), 0, 1) * 20
Score             = clip(sum of the four, 0, 100), rounded to 2 decimals
```

The distance bounds ({hr.DIST_MIN:g} and {hr.DIST_MAX:g}) are fixed so that one employee's score does not depend on who else is in the file or filter.
On the default dataset they equal the observed minimum and maximum, so the result is the same as min-max scaling.

**Burnout risk label.** High = overtime AND work-life balance <= 2; Medium = overtime OR work-life balance <= 2; otherwise Low.
**Priority.** Critical = High risk AND engagement <= {hr.ENGAGEMENT_CRITICAL}; High = High risk, OR Medium risk with engagement < {hr.ENGAGEMENT_LOW}; Medium = Medium risk; otherwise Low.

**Commute categories** (DistanceFromHome; unit not documented in the dataset): {hr.COMMUTE_LABELS[0]}, {hr.COMMUTE_LABELS[1]}, {hr.COMMUTE_LABELS[2]}.
Bins are right-inclusive: 5 is Short, 15 is Medium, 16 and above is Long. Every employee falls in exactly one category.

**Career stages** (TotalWorkingYears): {hr.CAREER_LABELS[0]}, {hr.CAREER_LABELS[1]}, {hr.CAREER_LABELS[2]}.

**Burnout-score groups.** Thirds of the score in the full loaded data: Lowest <= {t1:.2f}; Middle <= {t2:.2f}; Highest above {t2:.2f}. Ties stay in the same group, so group sizes are approximate.

**Attrition.** Stored as 1/0 (Yes/No text is also accepted) and converted to a 0/1 flag. Unsupported values stop the load with an error instead of being treated as "stayed". Every rate is *employees who left / employees in that group*.

**Limitations**
- The burnout score contains overtime, work-life balance, travel and distance. Differences in the score between groups defined by those same variables are partly mechanical and are not independent evidence of causes.
- Observed attrition by score group is an association inside one cross-sectional dataset. It does not show that the score predicts future attrition.
- Risk and priority labels are analytical flags to prompt supportive human conversations. They are not diagnoses and must not be used alone for employment decisions.
- Cut-offs in the Manager Action Panel are heuristics.
- Dataset provenance: the file name does not establish that these are real internal records of any company (see the Documentation tab).
"""


def render_documentation(dff: pd.DataFrame) -> None:
    st.title("📚 Project Documentation & Bulk Export")

    tab1, tab_m, tab2 = st.tabs(["📄 Documentation & Scope", "🧮 Methodology & Limitations", "💾 Bulk Data Export"])

    with tab1:
        st.markdown(f"""
        ### Employee Engagement, Satisfaction, and Burnout Diagnostic Analysis

        #### 1. Summary
        This application shifts HR analytics from reactive attrition reporting towards proactive, supportive follow-up. By combining Work-Life Balance, Overtime, Business Travel, Commute Distance and satisfaction items, it surfaces a rule-based `NumericBurnoutScore` and a contextual `EngagementIndex`. These indicators feed the Manager Action Panel, which suggests where supportive conversations may be worth starting. They are analytical flags, not diagnoses.

        #### 2. Dataset provenance
        - Default file: `{os.path.basename(DEFAULT_DATASET)}`. The file name is a project label.
        - No documentation about who collected the data, when, or where accompanies the file, so its provenance could not be verified. Its structure (employee-level HR attributes with a 0/1 attrition flag) matches publicly circulated sample HR-attrition datasets, but that was not confirmed against the supplied files.
        - It should therefore not be described as verified internal employee data of any named company.

        #### 3. Project architecture
        - **Calculations:** `hr_analytics.py` (validation, scoring, grouping, statistics). Shared by the dashboard, the analysis script and the tests.
        - **Reproducible statistics:** `analysis.py` regenerates `outputs/results.json` and tables from the CSV.
        - **UI layer:** Streamlit with modular routing (`app.py`).
        - **Visualization:** Plotly Express and Graph Objects (`plotly_white` theme).

        #### 4. Installation
        ```text
        pip install -r requirements.txt
        streamlit run app.py
        pytest
        python analysis.py
        ```
        `statsmodels` is needed for the OLS trendlines on scatter plots; without it the scatter plots still render without the trendline.

        #### 5. Future scope
        - Integration with HRIS APIs (e.g., Workday, BambooHR).
        - Predictive models validated on data collected over time, with out-of-sample evaluation.
        - Natural-language queries for non-technical HR managers.
        """)

    with tab_m:
        st.markdown(methodology_markdown())

    with tab2:
        st.subheader("Generate & Download Reports")
        st.write("Generate customized CSV reports based on current global filter settings. "
                 "Reports can contain individual-level information: store and share them confidentially.")

        dept_report = dff.groupby("Department", observed=True).mean(numeric_only=True).reset_index()
        st.download_button(
            label="📥 Download Department Report (CSV)",
            data=dept_report.to_csv(index=False).encode('utf-8'),
            file_name='department_report.csv',
            mime='text/csv'
        )

        exec_summary = dff[['Age', 'Department', 'JobRole', 'EngagementIndex', 'NumericBurnoutScore', 'PriorityLevel', 'Attrition_Label']]
        st.download_button(
            label="📥 Download Executive Summary Data (CSV)",
            data=exec_summary.to_csv(index=False).encode('utf-8'),
            file_name='executive_summary_data.csv',
            mime='text/csv'
        )

        crit_emps = dff[dff['PriorityLevel'] == 'Critical']
        st.download_button(
            label="📥 Download Critical-Priority Roster (CSV)",
            data=crit_emps.to_csv(index=False).encode('utf-8'),
            file_name='critical_priority_employees.csv',
            mime='text/csv'
        )


if page == "Executive Summary":
    render_executive_summary(filtered_df)
elif page == "Department Scorecard":
    render_department_scorecard(filtered_df)
elif page == "Engagement Health Overview":
    render_engagement(filtered_df)
elif page == "Burnout Risk Dashboard":
    render_burnout(filtered_df)
elif page == "Role & Career Stage Analysis":
    render_career(filtered_df)
elif page == "Manager Action Panel":
    render_action_panel(filtered_df)
elif page == "Documentation & Export":
    render_documentation(filtered_df)
