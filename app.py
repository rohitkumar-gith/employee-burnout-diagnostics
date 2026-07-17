"""
Employee Engagement, Satisfaction, and Burnout Diagnostic Analysis
Palo Alto Networks HR Analytics Dashboard (Enterprise Edition)

Requirements:
pip install streamlit pandas plotly statsmodels numpy
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from typing import List, Optional

# ==============================================================================
# PAGE CONFIGURATION
# ==============================================================================
st.set_page_config(
    page_title="HR Diagnostics | Palo Alto Networks",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# DATA PROCESSING & FEATURE ENGINEERING (PHASE 1 - OPTIMIZED)
# ==============================================================================
@st.cache_data
def load_and_process_data() -> pd.DataFrame:
    """
    Loads the dataset and engineers advanced HR metrics.
    Optimized using Vectorization (np.select) and Categorical memory mapping.
    """
    # Load the raw dataset
    df = pd.read_csv("Palo Alto Networks.csv")
    
    # 1. Missing Value Handling & Data Validation
    numeric_cols = df.select_dtypes(include=np.number).columns
    categorical_cols = df.select_dtypes(exclude=np.number).columns
    for col in numeric_cols:
        df[col] = df[col].fillna(df[col].median())
    for col in categorical_cols:
        if not df[col].mode().empty:
            df[col] = df[col].fillna(df[col].mode()[0])
            
    # OPTIMIZATION: Convert string objects to Categoricals for faster filtering and lower memory usage
    cat_cast_cols = ['Department', 'JobRole', 'BusinessTravel', 'Gender', 'MaritalStatus', 'OverTime', 'EducationField']
    for col in cat_cast_cols:
        if col in df.columns:
            df[col] = df[col].astype('category')
    
    # 2. Base Index Construction
    sat_cols = ['JobInvolvement', 'JobSatisfaction', 'EnvironmentSatisfaction', 'RelationshipSatisfaction']
    df['EngagementIndex'] = df[sat_cols].mean(axis=1)
    
    # 3. Satisfaction Stability Score
    df['SatisfactionStabilityScore'] = 4.0 - df[sat_cols].std(axis=1).fillna(0)
    
    # 4. Work-Life Balance Index
    df['WorkLifeBalanceIndex'] = df['WorkLifeBalance'] / 4.0
    
    # 5. Advanced Workload Stress Indicator
    travel_map = {'Non-Travel': 0, 'Travel_Rarely': 1, 'Travel_Frequently': 2}
    overtime_map = {'No': 0, 'Yes': 1}
    df['WorkloadStressIndicator'] = df['BusinessTravel'].map(travel_map).astype(float) + (df['OverTime'].map(overtime_map).astype(float) * 2)
    
    # 6. Commute Category
    df['CommuteCategory'] = pd.cut(
        df['DistanceFromHome'], 
        bins=[-1, 5, 15, 50], 
        labels=['Short (<5m)', 'Medium (5-15m)', 'Long (>15m)']
    )
    
    # 7. Career Stage
    df['CareerStage'] = pd.cut(
        df['TotalWorkingYears'], 
        bins=[-1, 5, 15, 50], 
        labels=['Early Career', 'Mid Career', 'Late Career']
    )
    
    # 8. Numeric Burnout Risk Score 0-100
    max_dist = df['DistanceFromHome'].max()
    min_dist = df['DistanceFromHome'].min()
    
    overtime_score = (df['OverTime'] == 'Yes').astype(float) * 30.0
    wlb_score = ((4.0 - df['WorkLifeBalance']) / 3.0) * 30.0
    travel_score = (df['BusinessTravel'].map(travel_map).astype(float) / 2.0) * 20.0
    distance_score = ((df['DistanceFromHome'] - min_dist) / (max_dist - min_dist + 1e-9)) * 20.0
    
    df['NumericBurnoutScore'] = (overtime_score + wlb_score + travel_score + distance_score).clip(0, 100).round(2)
    
    # 9. Burnout Risk Categorization (OPTIMIZED: Vectorized instead of apply)
    cond_burnout_high = (df['OverTime'] == 'Yes') & (df['WorkLifeBalance'] <= 2)
    cond_burnout_med = (df['OverTime'] == 'Yes') | (df['WorkLifeBalance'] <= 2)
    df['BurnoutRisk'] = np.select([cond_burnout_high, cond_burnout_med], ['High', 'Medium'], default='Low')
    df['BurnoutRisk'] = df['BurnoutRisk'].astype('category')
    
    # 10. Priority Level (OPTIMIZED: Vectorized instead of apply)
    cond_pri_crit = (df['BurnoutRisk'] == 'High') & (df['EngagementIndex'] <= 2.2)
    cond_pri_high = (df['BurnoutRisk'] == 'High') | ((df['BurnoutRisk'] == 'Medium') & (df['EngagementIndex'] < 2.5))
    cond_pri_med = (df['BurnoutRisk'] == 'Medium')
    df['PriorityLevel'] = np.select([cond_pri_crit, cond_pri_high, cond_pri_med], ['Critical', 'High', 'Medium'], default='Low')
    df['PriorityLevel'] = df['PriorityLevel'].astype('category')
    
    # Contextual Labeling
    df['Attrition_Label'] = df['Attrition'].map({1: 'Left Company', 0: 'Stayed'}).astype('category')
    df['Attrition_Flag'] = df['Attrition']
    
    return df

df = load_and_process_data()

# Clean columns for the drill-down tables
roster_cols = [
    'Department', 'JobRole', 'PriorityLevel', 'EngagementIndex', 
    'NumericBurnoutScore', 'WorkLifeBalance', 'OverTime', 'YearsAtCompany'
]

# ==============================================================================
# SIDEBAR NAVIGATION & ADVANCED FILTERS
# ==============================================================================
st.sidebar.markdown("### 🛡️ Palo Alto HR Analytics")
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

# Extract unique values efficiently for filters
dept_opts = df['Department'].unique().tolist()
selected_dept = st.sidebar.multiselect("Department", options=dept_opts, default=dept_opts)

avail_roles = df[df['Department'].isin(selected_dept)]['JobRole'].unique().tolist() if selected_dept else df['JobRole'].unique().tolist()
selected_roles = st.sidebar.multiselect("Job Role", options=avail_roles, default=avail_roles)

burnout_opts = df['BurnoutRisk'].unique().tolist()
burnout_filter = st.sidebar.multiselect("Burnout Risk", options=burnout_opts, default=burnout_opts)

priority_opts = df['PriorityLevel'].unique().tolist()
priority_filter = st.sidebar.multiselect("Priority Level", options=priority_opts, default=priority_opts)

career_opts = df['CareerStage'].dropna().unique().tolist()
career_filter = st.sidebar.multiselect("Career Stage", options=career_opts, default=career_opts)

commute_opts = df['CommuteCategory'].dropna().unique().tolist()
commute_filter = st.sidebar.multiselect("Commute Category", options=commute_opts, default=commute_opts)

gender_opts = df['Gender'].unique().tolist()
gender_filter = st.sidebar.multiselect("Gender", options=gender_opts, default=gender_opts)

marital_opts = df['MaritalStatus'].unique().tolist()
marital_filter = st.sidebar.multiselect("Marital Status", options=marital_opts, default=marital_opts)

edu_opts = sorted(df['Education'].unique().tolist())
edu_filter = st.sidebar.multiselect("Education Level (1-5)", options=edu_opts, default=edu_opts)

travel_opts = df['BusinessTravel'].unique().tolist()
travel_filter = st.sidebar.multiselect("Business Travel", options=travel_opts, default=travel_opts)

overtime_toggle = st.sidebar.checkbox("Show Overtime Employees Only", value=False)
engagement_threshold = st.sidebar.slider("Max Engagement Score", min_value=1.0, max_value=4.0, value=4.0, step=0.1)

min_tenure = int(df['YearsAtCompany'].min())
max_tenure = int(df['YearsAtCompany'].max())
tenure_range = st.sidebar.slider("Tenure Range (Years at Company)", min_value=min_tenure, max_value=max_tenure, value=(min_tenure, max_tenure))

# Optimized Boolean Masking for Filters
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


# ==============================================================================
# UI HELPER FUNCTIONS
# ==============================================================================
def render_drill_down(dataframe: pd.DataFrame, title: str, filter_col: Optional[str] = None, filter_options: Optional[List[str]] = None) -> None:
    """Generates the reusable employee drill-down component."""
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
        st.dataframe(display_df[roster_cols].sort_values(by="EngagementIndex"), hide_index=True, width="stretch")

def render_insights_engine(dff: pd.DataFrame) -> None:
    """Dynamically generates business insights based on the current filtered dataset."""
    st.markdown("---")
    st.subheader("🧠 Auto-Generated Business Insights")
    
    insights = []
    
    if not dff.empty:
        highest_burnout_dept = dff.groupby('Department', observed=True)['NumericBurnoutScore'].mean().idxmax()
        insights.append(f"**{highest_burnout_dept}** department is currently experiencing the highest average burnout score.")
    
    if not dff.empty:
        highest_eng_dept = dff.groupby('Department', observed=True)['EngagementIndex'].mean().idxmax()
        insights.append(f"**{highest_eng_dept}** department maintains the highest average engagement levels.")
    
    ot_eng = dff[dff['OverTime']=='Yes']['EngagementIndex'].mean()
    no_ot_eng = dff[dff['OverTime']=='No']['EngagementIndex'].mean()
    if pd.notna(ot_eng) and pd.notna(no_ot_eng) and no_ot_eng > 0:
        diff = ((no_ot_eng - ot_eng) / no_ot_eng) * 100
        if diff > 0:
            insights.append(f"Employees working overtime show a **{diff:.1f}% decrease** in engagement compared to non-overtime peers.")
    
    long_commute_burnout = dff[dff['CommuteCategory']=='Long (>15m)']['NumericBurnoutScore'].mean()
    short_commute_burnout = dff[dff['CommuteCategory']=='Short (<5m)']['NumericBurnoutScore'].mean()
    if pd.notna(long_commute_burnout) and pd.notna(short_commute_burnout):
        insights.append(f"Long commutes (>15m) correlate with an average burnout score of **{long_commute_burnout:.1f}**, compared to **{short_commute_burnout:.1f}** for short commutes.")
        
    attrition_rate = dff['Attrition_Flag'].mean() * 100
    if pd.notna(attrition_rate):
        insights.append(f"The current attrition rate for the filtered segment sits at **{attrition_rate:.1f}%**.")
    
    for i, insight in enumerate(insights):
        st.markdown(f"{i+1}. {insight}")


# ==============================================================================
# PAGE 1: EXECUTIVE SUMMARY
# ==============================================================================
def render_executive_summary(dff: pd.DataFrame) -> None:
    st.title("📈 Executive Summary")
    st.markdown("High-level overview of organizational health and key risk metrics.")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Workforce", f"{len(dff):,}")
    c2.metric("Avg Engagement", f"{dff['EngagementIndex'].mean():.2f} / 4.0")
    c3.metric("Avg Burnout Score", f"{dff['NumericBurnoutScore'].mean():.1f} / 100")
    c4.metric("Avg Satisfaction", f"{dff['JobSatisfaction'].mean():.2f} / 4.0")
    
    st.write("") # Spacing
    
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Avg Work-Life Balance", f"{dff['WorkLifeBalance'].mean():.2f} / 4.0")
    c6.metric("Attrition Rate", f"{(dff['Attrition_Flag'].mean() * 100):.1f}%")
    c7.metric("Critical Employees", len(dff[dff['PriorityLevel'] == 'Critical']))
    c8.metric("Avg Monthly Income", f"${dff['MonthlyIncome'].mean():,.0f}")
    
    st.markdown("---")
    
    st.subheader("🏆 Department Rankings & Risks")
    rank_c1, rank_c2, rank_c3, rank_c4 = st.columns(4)
    
    with rank_c1:
        top_risk_dept = dff.groupby('Department', observed=True)['NumericBurnoutScore'].mean().idxmax()
        st.error(f"**Top Risk Dept:**\n\n{top_risk_dept}")
    with rank_c2:
        low_eng_dept = dff.groupby('Department', observed=True)['EngagementIndex'].mean().idxmin()
        st.warning(f"**Lowest Engagement:**\n\n{low_eng_dept}")
    with rank_c3:
        high_attr_dept = dff.groupby('Department', observed=True)['Attrition_Flag'].mean().idxmax()
        st.error(f"**Highest Attrition:**\n\n{high_attr_dept}")
    with rank_c4:
        top_role = dff.groupby('JobRole', observed=True)['NumericBurnoutScore'].mean().idxmax()
        st.warning(f"**Top Risk Role:**\n\n{top_role}")
        
    st.markdown("---")
    
    st.subheader("📊 Organization-Wide Distributions")
    dist_c1, dist_c2, dist_c3 = st.columns(3)
    
    with dist_c1:
        fig_pie = px.pie(dff, names='PriorityLevel', hole=0.4, title="Priority Distribution",
                         color='PriorityLevel',
                         color_discrete_map={"Critical": "#8B0000", "High": "#EF553B", "Medium": "#FFA15A", "Low": "#00CC96"})
        fig_pie.update_layout(template="plotly_white", margin=dict(t=40, b=10))
        st.plotly_chart(fig_pie, width="stretch")
        
    with dist_c2:
        fig_b_dist = px.histogram(dff, x="NumericBurnoutScore", nbins=20, title="Burnout Score Distribution",
                                  color_discrete_sequence=["#EF553B"], template="plotly_white")
        fig_b_dist.update_layout(yaxis_title="Count", xaxis_title="Burnout Score", margin=dict(t=40, b=10))
        st.plotly_chart(fig_b_dist, width="stretch")
        
    with dist_c3:
        fig_e_dist = px.histogram(dff, x="EngagementIndex", nbins=15, title="Engagement Distribution",
                                  color_discrete_sequence=["#1F77B4"], template="plotly_white")
        fig_e_dist.update_layout(yaxis_title="Count", xaxis_title="Engagement Score", margin=dict(t=40, b=10))
        st.plotly_chart(fig_e_dist, width="stretch")
        
    render_insights_engine(dff)

# ==============================================================================
# PAGE 2: DEPARTMENT SCORECARD
# ==============================================================================
def render_department_scorecard(dff: pd.DataFrame) -> None:
    st.title("🏢 Department Scorecard")
    st.markdown("Comprehensive breakdown of key HR metrics isolated by department.")
    
    scorecard = dff.groupby("Department", observed=True).agg(
        Employee_Count=("Age", "count"),
        Avg_Engagement=("EngagementIndex", "mean"),
        Avg_Burnout=("NumericBurnoutScore", "mean"),
        Avg_Satisfaction=("JobSatisfaction", "mean"),
        Avg_WLB=("WorkLifeBalance", "mean"),
        Attrition_Rate=("Attrition_Flag", "mean"),
        Critical_Employees=("PriorityLevel", lambda x: (x == 'Critical').sum())
    ).reset_index()
    
    scorecard['Attrition_Rate (%)'] = (scorecard['Attrition_Rate'] * 100).round(1)
    scorecard['Priority_Score'] = (scorecard['Avg_Burnout'] / scorecard['Avg_Engagement']).round(2)
    scorecard.drop(columns=['Attrition_Rate'], inplace=True)
    
    for col in ['Avg_Engagement', 'Avg_Burnout', 'Avg_Satisfaction', 'Avg_WLB']:
        scorecard[col] = scorecard[col].round(2)
        
    st.markdown("---")
    
    styled_df = scorecard.style.background_gradient(
        subset=['Avg_Burnout', 'Attrition_Rate (%)', 'Priority_Score', 'Critical_Employees'], cmap='Reds'
    ).background_gradient(
        subset=['Avg_Engagement', 'Avg_Satisfaction', 'Avg_WLB'], cmap='Greens'
    )
    
    st.dataframe(styled_df, width="stretch", hide_index=True)
    
    st.markdown("---")
    st.info("💡 **Note on Priority Score:** Priority Score is calculated as `Average Burnout / Average Engagement`. Higher values indicate a severe imbalance requiring immediate HR attention.")
    
    render_insights_engine(dff)

# ==============================================================================
# PAGE 3: ENGAGEMENT HEALTH OVERVIEW
# ==============================================================================
def render_engagement(dff: pd.DataFrame) -> None:
    st.title("📊 Engagement Health Overview")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Employees", len(dff))
    col2.metric("Avg Engagement", f"{dff['EngagementIndex'].mean():.2f} / 4.0")
    col3.metric("Avg Job Satisfaction", f"{dff['JobSatisfaction'].mean():.2f} / 4.0")
    col4.metric("Avg WLB Index", f"{dff['WorkLifeBalanceIndex'].mean()*100:.0f}%")
    col5.metric("Avg Burnout Score", f"{dff['NumericBurnoutScore'].mean():.1f}")
    st.markdown("---")
    
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Organization Engagement Level")
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = dff['EngagementIndex'].mean(),
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "Average Engagement"},
            gauge = {
                'axis': {'range': [1, 4]},
                'bar': {'color': "#1F77B4"},
                'steps': [
                    {'range': [1, 2], 'color': "#FFCCCB"},
                    {'range': [2, 3], 'color': "#FFFFE0"},
                    {'range': [3, 4], 'color': "#E0FFFF"}]
            }))
        fig_gauge.update_layout(template="plotly_white", height=350, margin=dict(t=40, b=10))
        st.plotly_chart(fig_gauge, width="stretch")
        
    with c2:
        st.subheader("Satisfaction Distribution")
        fig_eng = px.histogram(dff, x="EngagementIndex", nbins=10, color="Department", 
                               opacity=0.8, color_discrete_sequence=px.colors.qualitative.Set2,
                               template="plotly_white", height=350)
        fig_eng.update_layout(yaxis_title="Number of Employees", xaxis_title="Engagement Score (1-4)", bargap=0.1, margin=dict(t=40, b=10))
        st.plotly_chart(fig_eng, width="stretch")

    c3, c4 = st.columns([1, 2.2]) 
    
    with c3:
        st.subheader("Department Ranking")
        dept_eng = dff.groupby('Department', observed=True)['EngagementIndex'].mean().sort_values().reset_index()
        fig_rank = px.bar(dept_eng, x='EngagementIndex', y='Department', orientation='h', 
                          color='EngagementIndex', color_continuous_scale="Blues", template="plotly_white")
        fig_rank.update_layout(xaxis_title="Avg Engagement Score", yaxis_title="", coloraxis_showscale=False)
        fig_rank.update_xaxes(range=[1.5, 4.0])
        st.plotly_chart(fig_rank, width="stretch")

    with c4:
        st.subheader("Comprehensive Driver Correlation Matrix")
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
        
        st.plotly_chart(fig_corr, width="stretch")

    st.markdown("---")
    
    st.subheader("🚪 Advanced Attrition Analytics")
    attr_c1, attr_c2, attr_c3 = st.columns(3)
    
    with attr_c1:
        st.write("**Attrition by Department**")
        fig_attr_dept = px.histogram(dff, x="Department", color="Attrition_Label", barmode="group",
                                     color_discrete_map={"Left Company": "#EF553B", "Stayed": "#636EFA"}, template="plotly_white")
        fig_attr_dept.update_layout(yaxis_title="Count", margin=dict(t=20, b=10))
        st.plotly_chart(fig_attr_dept, width="stretch")
        
        st.write("**Attrition by Job Level**")
        fig_attr_lvl = px.histogram(dff, x="JobLevel", color="Attrition_Label", barmode="group",
                                    color_discrete_map={"Left Company": "#EF553B", "Stayed": "#636EFA"}, template="plotly_white")
        fig_attr_lvl.update_layout(yaxis_title="Count", margin=dict(t=20, b=10))
        st.plotly_chart(fig_attr_lvl, width="stretch")

    with attr_c2:
        st.write("**Attrition by Burnout Risk**")
        fig_attr_burn = px.histogram(dff, x="BurnoutRisk", color="Attrition_Label", barmode="group",
                                     category_orders={"BurnoutRisk": ["Low", "Medium", "High"]},
                                     color_discrete_map={"Left Company": "#EF553B", "Stayed": "#636EFA"}, template="plotly_white")
        fig_attr_burn.update_layout(yaxis_title="Count", margin=dict(t=20, b=10))
        st.plotly_chart(fig_attr_burn, width="stretch")
        
        st.write("**Attrition by Career Stage**")
        fig_attr_stage = px.histogram(dff, x="CareerStage", color="Attrition_Label", barmode="group",
                                      color_discrete_map={"Left Company": "#EF553B", "Stayed": "#636EFA"}, template="plotly_white")
        fig_attr_stage.update_layout(yaxis_title="Count", margin=dict(t=20, b=10))
        st.plotly_chart(fig_attr_stage, width="stretch")
        
    with attr_c3:
        st.write("**Attrition by Work Life Balance**")
        fig_attr_wlb = px.histogram(dff, x="WorkLifeBalance", color="Attrition_Label", barmode="group",
                                    color_discrete_map={"Left Company": "#EF553B", "Stayed": "#636EFA"}, template="plotly_white")
        fig_attr_wlb.update_layout(yaxis_title="Count", margin=dict(t=20, b=10))
        st.plotly_chart(fig_attr_wlb, width="stretch")
        
        st.write("**Attrition by Overtime**")
        fig_attr_ot = px.histogram(dff, x="OverTime", color="Attrition_Label", barmode="group",
                                   color_discrete_map={"Left Company": "#EF553B", "Stayed": "#636EFA"}, template="plotly_white")
        fig_attr_ot.update_layout(yaxis_title="Count", margin=dict(t=20, b=10))
        st.plotly_chart(fig_attr_ot, width="stretch")

    st.markdown("---")

    st.subheader("⚖️ Satisfaction Stability Dashboard")
    stab_c1, stab_c2 = st.columns(2)
    
    with stab_c1:
        st.write(f"**Average Stability Score:** {dff['SatisfactionStabilityScore'].mean():.2f} / 4.0")
        fig_stab_dist = px.histogram(dff, x="SatisfactionStabilityScore", nbins=15, title="Stability Score Distribution",
                                     template="plotly_white", color_discrete_sequence=["#8c564b"])
        fig_stab_dist.update_layout(yaxis_title="Count", margin=dict(t=30, b=10))
        st.plotly_chart(fig_stab_dist, width="stretch")
        
        fig_stab_dept = px.box(dff, x="Department", y="SatisfactionStabilityScore", color="Department",
                               title="Stability by Department", template="plotly_white")
        fig_stab_dept.update_layout(margin=dict(t=30, b=10))
        st.plotly_chart(fig_stab_dept, width="stretch")
        
    with stab_c2:
        fig_stab_burn = px.scatter(dff, x="NumericBurnoutScore", y="SatisfactionStabilityScore", color="BurnoutRisk",
                                   trendline="ols", title="Stability vs. Burnout", template="plotly_white", opacity=0.6)
        fig_stab_burn.update_layout(margin=dict(t=30, b=10))
        st.plotly_chart(fig_stab_burn, width="stretch")
        
        fig_stab_attr = px.violin(dff, x="Attrition_Label", y="SatisfactionStabilityScore", color="Attrition_Label",
                                  box=True, title="Stability vs. Attrition", color_discrete_map={"Left Company": "#EF553B", "Stayed": "#636EFA"},
                                  template="plotly_white")
        fig_stab_attr.update_layout(margin=dict(t=30, b=10))
        st.plotly_chart(fig_stab_attr, width="stretch")

    render_drill_down(dff, "Attrition & Engagement", "Attrition_Label", dff['Attrition_Label'].dropna().unique().tolist())
    render_insights_engine(dff)

# ==============================================================================
# PAGE 4: BURNOUT RISK DASHBOARD
# ==============================================================================
def render_burnout(dff: pd.DataFrame) -> None:
    st.title("🔥 Burnout Risk Dashboard")
    
    high_risk = len(dff[dff['BurnoutRisk'] == 'High'])
    st.metric(f"Employees at HIGH Burnout Risk", high_risk, delta_color="inverse")
    st.markdown("---")
    
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Burnout Risk by Department")
        fig_burnout = px.histogram(dff, x="Department", color="BurnoutRisk", barmode="group",
                                   category_orders={"BurnoutRisk": ["Low", "Medium", "High"]},
                                   color_discrete_map={"Low": "#00CC96", "Medium": "#FFA15A", "High": "#EF553B"},
                                   template="plotly_white")
        fig_burnout.update_layout(yaxis_title="Employee Count", bargroupgap=0.1)
        st.plotly_chart(fig_burnout, width="stretch")
        
    with c2:
        st.subheader("Burnout Score Distribution")
        fig_b_dist = px.histogram(dff, x="NumericBurnoutScore", nbins=20, marginal="box", 
                                  color_discrete_sequence=["#EF553B"], template="plotly_white")
        st.plotly_chart(fig_b_dist, width="stretch")

    c3, c4 = st.columns(2)
    with c3:
        st.subheader("Commute vs. Burnout Score")
        fig_commute = px.box(dff, x="CommuteCategory", y="NumericBurnoutScore", color="CommuteCategory",
                             template="plotly_white", category_orders={"CommuteCategory": ["Short (<5m)", "Medium (5-15m)", "Long (>15m)"]})
        fig_commute.update_layout(showlegend=False)
        st.plotly_chart(fig_commute, width="stretch")

    with c4:
        st.subheader("Travel Frequency vs. Engagement")
        fig_travel = px.box(dff, x="BusinessTravel", y="EngagementIndex", color="BusinessTravel", template="plotly_white")
        st.plotly_chart(fig_travel, width="stretch")
        
    st.markdown("---")
    
    st.subheader("⚖️ Work-Life Balance Analytics")
    wlb_c1, wlb_c2, wlb_c3 = st.columns(3)
    
    with wlb_c1:
        st.write(f"**Average WLB Score:** {dff['WorkLifeBalance'].mean():.2f} / 4.0")
        fig_wlb_dist = px.histogram(dff, x="WorkLifeBalance", nbins=4, template="plotly_white", color_discrete_sequence=["#9467bd"])
        fig_wlb_dist.update_layout(yaxis_title="Count", margin=dict(t=30, b=10))
        st.plotly_chart(fig_wlb_dist, width="stretch")
        
        fig_wlb_dept = px.box(dff, x="Department", y="WorkLifeBalance", color="Department", title="WLB by Department", template="plotly_white")
        fig_wlb_dept.update_layout(margin=dict(t=30, b=10))
        st.plotly_chart(fig_wlb_dept, width="stretch")
        
    with wlb_c2:
        st.write("**Workload Stress vs WLB Heatmap**")
        fig_stress = px.density_heatmap(dff, x="WorkloadStressIndicator", y="WorkLifeBalance", 
                                        text_auto=True, color_continuous_scale="Reds", template="plotly_white")
        fig_stress.update_layout(xaxis_title="Workload Stress (0=Low)", yaxis_title="WLB (1=Poor)", margin=dict(t=30, b=10))
        st.plotly_chart(fig_stress, width="stretch")
        
        fig_wlb_attr = px.histogram(dff, x="WorkLifeBalance", color="Attrition_Label", barmode="group",
                                    title="WLB vs Attrition", color_discrete_map={"Left Company": "#EF553B", "Stayed": "#636EFA"}, template="plotly_white")
        fig_wlb_attr.update_layout(yaxis_title="Count", margin=dict(t=30, b=10))
        st.plotly_chart(fig_wlb_attr, width="stretch")
        
    with wlb_c3:
        fig_wlb_burn = px.scatter(dff, x="WorkLifeBalance", y="NumericBurnoutScore", color="BurnoutRisk",
                                  title="WLB vs Burnout Score", template="plotly_white", opacity=0.6)
        fig_wlb_burn.update_layout(margin=dict(t=30, b=10))
        st.plotly_chart(fig_wlb_burn, width="stretch")
        
        fig_wlb_role = px.box(dff, x="WorkLifeBalance", y="JobRole", orientation="h", color="JobRole",
                              title="WLB by Job Role", template="plotly_white")
        fig_wlb_role.update_layout(showlegend=False, margin=dict(t=30, b=10))
        st.plotly_chart(fig_wlb_role, width="stretch")

    render_drill_down(dff, "Burnout Roster", "BurnoutRisk", ["High", "Medium", "Low"])
    render_insights_engine(dff)

# ==============================================================================
# PAGE 5: ROLE & CAREER STAGE ANALYSIS
# ==============================================================================
def render_career(dff: pd.DataFrame) -> None:
    st.title("📈 Role & Career Stage Analysis")
    st.markdown("---")
    
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Average Engagement by Job Role")
        role_eng_df = dff.groupby('JobRole', observed=True)['EngagementIndex'].mean().reset_index().sort_values('EngagementIndex')
        fig_role = px.bar(role_eng_df, x="EngagementIndex", y="JobRole", orientation='h', 
                          color="EngagementIndex", color_continuous_scale="Blues", template="plotly_white")
        fig_role.update_layout(xaxis_title="Avg Engagement Score", yaxis_title="", coloraxis_showscale=False)
        fig_role.update_xaxes(range=[2.0, 3.5]) 
        st.plotly_chart(fig_role, width="stretch")
        
    with c2:
        st.subheader("Engagement by Job Level")
        fig_lvl = px.box(dff, x="JobLevel", y="EngagementIndex", color="JobLevel", template="plotly_white")
        st.plotly_chart(fig_lvl, width="stretch")

    c3, c4 = st.columns(2)
    with c3:
        st.subheader("Tenure vs Engagement Trends")
        tenure_df = dff.groupby('YearsAtCompany')['EngagementIndex'].mean().reset_index()
        fig_tenure = px.line(tenure_df, x="YearsAtCompany", y="EngagementIndex", markers=True, 
                             template="plotly_white", line_shape="spline")
        fig_tenure.update_layout(xaxis_title="Years at Company", yaxis_title="Avg Engagement Score")
        st.plotly_chart(fig_tenure, width="stretch")

    with c4:
        st.subheader("Career Stage Analysis")
        fig_stage = px.histogram(dff, x="CareerStage", y="EngagementIndex", histfunc="avg", 
                                 color="CareerStage", template="plotly_white")
        fig_stage.update_layout(yaxis_title="Avg Engagement Score", showlegend=False)
        st.plotly_chart(fig_stage, width="stretch")

    c5, c6 = st.columns(2)
    with c5:
        st.subheader("Years in Current Role vs. Engagement")
        fig_in_role = px.scatter(dff, x="YearsInCurrentRole", y="EngagementIndex", color="BurnoutRisk", 
                                 trendline="ols", template="plotly_white", opacity=0.6)
        st.plotly_chart(fig_in_role, width="stretch")
        
    with c6:
        st.subheader("Promotion Stagnation Analysis")
        fig_promo = px.scatter(dff, x="YearsSinceLastPromotion", y="EngagementIndex", color="PriorityLevel",
                               template="plotly_white", opacity=0.6,
                               color_discrete_map={"Critical": "#8B0000", "High": "#EF553B", "Medium": "#FFA15A", "Low": "#00CC96"})
        st.plotly_chart(fig_promo, width="stretch")

    render_drill_down(dff, "Job Roles", "JobRole", dff['JobRole'].unique().tolist())
    render_insights_engine(dff)

# ==============================================================================
# PAGE 6: MANAGER ACTION PANEL
# ==============================================================================
def render_action_panel(dff: pd.DataFrame) -> None:
    st.title("🚨 Manager Action Panel")
    st.markdown("Algorithmic prioritization for HR interventions based on Burnout and Engagement signals.")
    st.markdown("---")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.error(f"🔴 Critical Priority: {len(dff[dff['PriorityLevel'] == 'Critical'])}")
    c2.warning(f"🟠 High Priority: {len(dff[dff['PriorityLevel'] == 'High'])}")
    c3.info(f"🟡 Medium Priority: {len(dff[dff['PriorityLevel'] == 'Medium'])}")
    c4.success(f"🟢 Low Priority: {len(dff[dff['PriorityLevel'] == 'Low'])}")
    
    st.markdown("---")
    
    st.subheader("🤖 Dynamic HR Recommendations")
    avg_burnout = dff['NumericBurnoutScore'].mean()
    avg_eng = dff['EngagementIndex'].mean()
    avg_promo = dff['YearsSinceLastPromotion'].mean()
    avg_wlb = dff['WorkLifeBalance'].mean()
    attr_rate = dff['Attrition_Flag'].mean() * 100
    
    if dff.empty:
        st.info("No data available for recommendations based on current filters.")
    else:
        if avg_burnout > 70:
            st.error(f"🚨 **High Burnout Detected ({avg_burnout:.1f}/100):** Recommend reducing mandatory overtime and auditing workload capacity immediately.")
        if avg_eng < 2.5:
            st.warning(f"⚠️ **Low Engagement ({avg_eng:.2f}/4.0):** Recommend initiating 1-on-1 manager coaching and conducting satisfaction pulse surveys.")
        if avg_promo > 3:
            st.info(f"ℹ️ **Promotion Stagnation:** Employees average {avg_promo:.1f} years since last promotion. Recommend comprehensive career pathing review.")
        if avg_wlb < 2.5:
            st.warning(f"⚠️ **Poor Work-Life Balance ({avg_wlb:.2f}/4.0):** Recommend implementing flexible work arrangements or hybrid schedules.")
        if attr_rate > 15:
            st.error(f"🚨 **High Flight Risk ({attr_rate:.1f}%):** Attrition is critically high. Recommend immediate retention interviews for top performers.")
        if avg_burnout <= 70 and avg_eng >= 2.5 and attr_rate <= 15:
            st.success("✅ **Healthy Segment:** The current filtered workforce segment is stable. Continue standard HR monitoring.")
            
    st.markdown("---")
    
    st.subheader("⚠️ Top 20 Employees at Risk (Prediction Engine)")
    
    risk_cols = ['Department', 'JobRole', 'NumericBurnoutScore', 'PriorityLevel', 'EngagementIndex', 
                 'YearsAtCompany', 'YearsSinceLastPromotion', 'OverTime', 'WorkLifeBalance']
                 
    risk_df = dff.sort_values(by='NumericBurnoutScore', ascending=False).head(20)[risk_cols]
    
    if not risk_df.empty:
        styled_risk = risk_df.style.background_gradient(subset=['NumericBurnoutScore'], cmap='Reds') \
                                   .background_gradient(subset=['EngagementIndex', 'WorkLifeBalance'], cmap='Reds_r')
        st.dataframe(styled_risk, hide_index=True, width="stretch")
        
        csv_risk = risk_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Top 20 Risk Interventions (CSV)",
            data=csv_risk,
            file_name='top_20_risk_employees.csv',
            mime='text/csv',
        )
    else:
        st.success("No employees found in the current filter.")
        
    st.markdown("---")
    
    st.subheader("All High & Medium Priority Interventions")
    action_df = dff[dff['PriorityLevel'].isin(['High', 'Medium'])].sort_values(by='NumericBurnoutScore', ascending=False)
    if not action_df.empty:
        st.dataframe(action_df[roster_cols], hide_index=True, width="stretch")
        
        csv_all = action_df[roster_cols].to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Full Action List (CSV)",
            data=csv_all,
            file_name='all_interventions.csv',
            mime='text/csv',
        )
        
    render_insights_engine(dff)

# ==============================================================================
# PAGE 7: DOCUMENTATION & EXPORTS
# ==============================================================================
def render_documentation(dff: pd.DataFrame) -> None:
    st.title("📚 Project Documentation & Bulk Export")
    
    tab1, tab2 = st.tabs(["📄 Documentation & Scope", "💾 Bulk Data Export"])
    
    with tab1:
        st.markdown("""
        ### Employee Engagement, Satisfaction, and Burnout Diagnostic Analysis
        **Organization:** Palo Alto Networks
        
        #### 1. Executive Summary
        This enterprise-grade application shifts HR analytics from reactive attrition reporting to proactive retention strategy. By synthesizing Work-Life Balance, Overtime, Commute, and Job Satisfaction, the application surfaces a `NumericBurnoutScore` and a contextual `EngagementIndex`. These metrics fuel an automated Manager Action Panel, pinpointing employees at highest risk of burnout before attrition occurs.
        
        #### 2. Project Architecture
        - **Data Ingestion:** Processed from `Palo Alto Networks.csv`.
        - **Feature Engineering:** Dynamic normalization of stress factors, stability indices, and priority flagging.
        - **UI Layer:** Streamlit with modular routing.
        - **Visualization:** Plotly Express & Graph Objects (Enterprise `plotly_white` theme).
        
        #### 3. Installation Guide & Dependencies
        ```text
        # requirements.txt
        streamlit==1.32.0
        pandas==2.2.0
        plotly==5.19.0
        statsmodels==0.14.1
        numpy==1.26.4
        ```
        *Note: `statsmodels` is required for rendering OLS trendlines in the Career Stage Analysis scatter plots.*
        
        #### 4. Future Scope
        - Integration with real-time HRIS APIs (e.g., Workday, BambooHR).
        - Predictive ML models (XGBoost) for attrition forecasting.
        - Natural Language query processing for non-technical HR managers.
        """)
        
    with tab2:
        st.subheader("Generate & Download Reports")
        st.write("Generate customized CSV reports based on current global filter settings.")
        
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
            label="📥 Download Critical Employee Roster (CSV)",
            data=crit_emps.to_csv(index=False).encode('utf-8'),
            file_name='critical_employees.csv',
            mime='text/csv'
        )

# ==============================================================================
# APP ROUTER
# ==============================================================================
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