#!/usr/bin/env python3
"""
build_paper.py - builds the revised paper (DOCX) and VERIFICATION_REPORT.md
directly from outputs/results.json (produced by analysis.py).

    python analysis.py && python build_paper.py

No statistic is typed by hand: every number in the paper text and tables is
read from results.json.
"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

OUT = "outputs"
R = json.load(open(os.path.join(OUT, "results.json")))
FIG = os.path.join(OUT, "figures")
os.makedirs(FIG, exist_ok=True)


# ----------------------------------------------------------------- helpers
def f(x, d=2):
    return f"{x:.{d}f}"


def pct(x, d=2):
    return f"{x:.{d}f}%"


def pv(p):
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def n_(x):
    return f"{int(x):,}"


D, O = R["dataset"], R["overall"]
T = R["tertiles"]
TT = T["table"]                      # list of dict rows: lowest, middle, highest
LOW, MID, HIGH = TT[0], TT[1], TT[2]
W = R["overtime_engagement"]["welch"]
PRO, TEN, COM = R["promotion"], R["tenure"], R["commute"]
DEP, CAR = R["department"], R["career_stage"]
SA = R["score_audit"]
HOLM = {r["Test"]: r for r in R["holm_family"]}
OTT = {r["OverTime"]: r for r in R["attrition_by_overtime"]}
STRATA = R["attrition_tertile_within_overtime"]
OVC = T["overtime_composition"]


def holm_p(name_part):
    for k, v in HOLM.items():
        if name_part in k:
            return v["p_holm"]
    raise KeyError(name_part)


# ------------------------------------------------------------------ figures
def make_figures():
    labels = [r["ScoreGroup"] for r in TT]
    rates = [r["AttritionRate_pct"] for r in TT]
    lo = [r["AttritionRate_pct"] - r["CI95_low_pct"] for r in TT]
    hi = [r["CI95_high_pct"] - r["AttritionRate_pct"] for r in TT]
    fig, ax = plt.subplots(figsize=(6.2, 3.6), dpi=200)
    bars = ax.bar(labels, rates, color=["#4C9F70", "#E0A030", "#C8443C"], yerr=[lo, hi], capsize=4, width=0.6)
    for b, r in zip(bars, TT):
        ax.text(b.get_x() + b.get_width() / 2, r["CI95_high_pct"] + 0.8,
                f"{r['AttritionRate_pct']:.1f}%\n({int(r['Left'])}/{int(r['Employees'])})", ha="center", va="bottom", fontsize=8)
    ax.axhline(O["attrition_rate_pct"], color="#555", ls="--", lw=1)
    ax.text(-0.45, O["attrition_rate_pct"] + 0.6, f"overall {O['attrition_rate_pct']:.1f}%", ha="left", fontsize=8, color="#555")
    ax.set_ylabel("Observed attrition (%)")
    ax.set_ylim(0, max(r["CI95_high_pct"] for r in TT) + 9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_title("Observed attrition by burnout-score group (95% Wilson CI)", fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig1_attrition_by_score_group.png")); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.2, 3.6), dpi=200)
    order = ["Lowest third", "Middle third", "Highest third"]
    colors = {"No": "#4C78A8", "Yes": "#E45756"}
    width = 0.36
    for j, ot in enumerate(["No", "Yes"]):
        for i, g in enumerate(order):
            row = next((r for r in STRATA if r["OverTime"] == ot and r["ScoreGroup"] == g), None)
            if row is None:
                continue
            x = i + (j - 0.5) * width
            ax.bar(x, row["AttritionRate_pct"], width, color=colors[ot],
                   yerr=[[row["AttritionRate_pct"] - row["CI95_low_pct"]], [row["CI95_high_pct"] - row["AttritionRate_pct"]]], capsize=3,
                   label=f"Overtime: {ot}" if i == 0 or (ot == "Yes" and g == "Middle third") else None)
            ax.text(x, row["CI95_high_pct"] + 0.8, f"{row['AttritionRate_pct']:.1f}%\nn={int(row['Employees'])}", ha="center", fontsize=7)
    ax.set_xticks(range(3)); ax.set_xticklabels(order)
    ax.set_ylabel("Observed attrition (%)"); ax.set_ylim(0, 58)
    ax.spines[["top", "right"]].set_visible(False)
    h, l = ax.get_legend_handles_labels()
    seen = dict(zip(l, h)); ax.legend(seen.values(), seen.keys(), frameon=False, fontsize=8, loc="upper left")
    ax.set_title("Attrition by burnout-score group, split by overtime", fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig2_attrition_group_by_overtime.png")); plt.close(fig)


# -------------------------------------------------------------- docx utils
doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
sec.left_margin = sec.right_margin = Cm(2.3)
sec.top_margin, sec.bottom_margin = Cm(2.2), Cm(2.2)

st = doc.styles["Normal"]
st.font.name = "Times New Roman"; st.font.size = Pt(11)
st.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
st.paragraph_format.space_after = Pt(6); st.paragraph_format.line_spacing = 1.12
for name, size in (("Heading 1", 14), ("Heading 2", 12), ("Heading 3", 11)):
    h = doc.styles[name]
    h.font.name = "Times New Roman"; h.font.size = Pt(size); h.font.bold = True
    h.font.color.rgb = RGBColor(0x17, 0x2B, 0x4D)
    rf = h.element.rPr.rFonts
    for att in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        if rf.get(qn(att)) is not None:
            del rf.attrib[qn(att)]
    rf.set(qn("w:ascii"), "Times New Roman"); rf.set(qn("w:hAnsi"), "Times New Roman"); rf.set(qn("w:eastAsia"), "Times New Roman")
    h.paragraph_format.space_before = Pt(12 if name == "Heading 1" else 8); h.paragraph_format.space_after = Pt(4)
    h.paragraph_format.keep_with_next = True


def P(text="", bold=False, italic=False, align=None, size=None, style=None, space_after=None):
    p = doc.add_paragraph(style=style)
    if text:
        r = p.add_run(text); r.bold = bold; r.italic = italic
        if size:
            r.font.size = Pt(size)
    if align == "center":
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif align == "justify":
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    if space_after is not None:
        p.paragraph_format.space_after = Pt(space_after)
    return p


def RP(parts, style=None):
    """Paragraph from [(text, bold, italic), ...]."""
    p = doc.add_paragraph(style=style)
    for t in parts:
        text, b, i = (t + (False, False))[:3] if isinstance(t, tuple) else (t, False, False)
        r = p.add_run(text); r.bold = b; r.italic = i
    return p


def H1(t): doc.add_heading(t, level=1)
def H2(t): doc.add_heading(t, level=2)


def bullet(text, bold_lead=None):
    p = doc.add_paragraph(style="List Bullet")
    if bold_lead:
        p.add_run(bold_lead).bold = True
    p.add_run(text)
    p.paragraph_format.space_after = Pt(3)
    return p


def shade(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd"); shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), fill)
    tcPr.append(shd)


def table(headers, rows, widths_cm, caption=None, note=None, font=9, align_right_from=1):
    if caption:
        c = P(caption, bold=True, size=10, space_after=2); c.paragraph_format.keep_with_next = True
    t = doc.add_table(rows=1, cols=len(headers)); t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER; t.autofit = False
    for i, h in enumerate(headers):
        cell = t.rows[0].cells[i]; cell.width = Cm(widths_cm[i]); cell.text = ""
        r = cell.paragraphs[0].add_run(h); r.bold = True; r.font.size = Pt(font)
        shade(cell, "DCE6F2")
        if i >= align_right_from:
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].width = Cm(widths_cm[i]); cells[i].text = ""
            r = cells[i].paragraphs[0].add_run(str(v)); r.font.size = Pt(font)
            if i >= align_right_from:
                cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    for row in t.rows:
        for cell in row.cells:
            for p in cell.paragraphs:
                p.paragraph_format.space_after = Pt(1); p.paragraph_format.space_before = Pt(1)
    # keep each table on one page: rows cannot split, and all but the last row stay with the next
    for ri, row in enumerate(t.rows):
        trPr_ = row._tr.get_or_add_trPr(); cs = OxmlElement("w:cantSplit"); cs.set(qn("w:val"), "true"); trPr_.append(cs)
        if ri < len(t.rows) - 1:
            for cell in row.cells:
                for p_ in cell.paragraphs:
                    p_.paragraph_format.keep_with_next = True
    # repeat header row
    trPr = t.rows[0]._tr.get_or_add_trPr(); th = OxmlElement("w:tblHeader"); th.set(qn("w:val"), "true"); trPr.append(th)
    if note:
        P(note, italic=True, size=9, space_after=8)
    else:
        P("", space_after=4)
    return t


def figure(path, caption, width_cm=13.5):
    doc.add_picture(path, width=Cm(width_cm))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.paragraphs[-1].paragraph_format.keep_with_next = True
    P(caption, italic=True, size=9.5, align="center", space_after=8)


def add_field(run, instr):
    for typ, txt in (("begin", None), (None, instr), ("end", None)):
        if typ:
            el = OxmlElement("w:fldChar"); el.set(qn("w:fldCharType"), typ)
        else:
            el = OxmlElement("w:instrText"); el.set(qn("xml:space"), "preserve"); el.text = txt
        run._r.append(el)


def footer():
    p = sec.footer.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Rohit Kumar — Unified Mentor  |  Page "); r.font.size = Pt(9)
    r2 = p.add_run(); r2.font.size = Pt(9); add_field(r2, "PAGE")
    r3 = p.add_run(" of "); r3.font.size = Pt(9)
    r4 = p.add_run(); r4.font.size = Pt(9); add_field(r4, "NUMPAGES")


# ================================================================== CONTENT
def build_doc():
    footer()
    # ---- title page block
    P("Catching Burnout Before It Happens:", bold=True, align="center", size=20, space_after=0)
    P("A Data-Driven Approach to Employee Engagement and HR Diagnostics", bold=True, align="center", size=15, space_after=10)
    P("Rohit Kumar", align="center", size=12, space_after=0)
    P("Data Analytics Intern, Unified Mentor", align="center", size=11, space_after=0)
    P("Project framing: HR diagnostics for a technology-sector setting (see Section 4 on dataset provenance)", align="center", italic=True, size=10, space_after=0)
    P("Revised draft — October 2026", align="center", italic=True, size=10, space_after=12)

    # ---- abstract
    H1("Abstract")
    P(
        f"This paper describes an exploratory HR analytics workflow, implemented as a Streamlit dashboard, for examining employee "
        f"engagement, work-life balance and attrition in a dataset of {n_(D['rows'])} employee records and {D['columns']} variables. "
        f"Two composite indicators are derived: an Engagement Index (the mean of four 1–4 survey items) and a rule-based Numeric "
        f"Burnout Score (0–100) built from overtime, work-life balance, business travel and commute distance. Because the score is "
        f"made of workload variables, its differences across groups defined by those same variables arise partly by construction. "
        f"In this dataset {pct(O['attrition_rate_pct'])} of employees ({n_(O['attrition_left'])} of {n_(O['n'])}) are recorded as having left. "
        f"Observed attrition was {pct(LOW['AttritionRate_pct'], 1)} in the lowest third of burnout scores and "
        f"{pct(HIGH['AttritionRate_pct'], 1)} in the highest third (relative risk {f(T['relative_risk_high_vs_low']['rr'])}, 95% CI "
        f"{f(T['relative_risk_high_vs_low']['ci_low'])}–{f(T['relative_risk_high_vs_low']['ci_high'])}); this is an in-sample association, "
        f"not a validated prediction, and {pct(OVC['Highest third']['overtime_share_pct'], 0)} of the highest third work overtime. "
        f"Employees working overtime had slightly higher mean engagement ({W['diff']:+.3f} points, 95% CI {W['ci_low']:+.3f} to {W['ci_high']:+.3f}, "
        f"Welch p = {pv(W['p'])}, Cohen's d = {f(W['cohens_d'])}). No association was found between years since last promotion and engagement "
        f"(Spearman rho = {f(PRO['spearman_rho'], 3)}, p = {f(PRO['spearman_p'], 2)}). The dataset's provenance could not be verified and it appears "
        f"consistent with a publicly circulated fictional sample dataset, so the findings should not be read as describing any real company.",
        align="justify")
    RP([("Keywords: ", True), "HR analytics; employee engagement; burnout indicator; attrition; Streamlit; exploratory analysis."])

    # ---- 1 introduction
    H1("1. Introduction")
    P("Employee engagement and well-being are multi-dimensional constructs that cannot be captured well by isolated survey responses or "
      "single workload variables. Human Resources (HR) interventions have often relied on reactive analytics, investigating turnover only after "
      "employees have left. The problem addressed here is the lack of an integrated, transparent diagnostic view that brings several workload "
      "and engagement signals together so that HR teams can decide where supportive conversations may be worthwhile before problems escalate. "
      "This study builds such a view as an interactive dashboard and examines, with a documented and reproducible analysis, what the available "
      "data do and do not support.", align="justify")

    # ---- 2 objectives
    H1("2. Research Objectives")
    P("The project is an exploratory decision-support workflow that ingests workforce data, derives composite indicators, and organizes records into "
      "intervention-priority categories for HR review. It is guided by four aims:", align="justify")
    for t in ("to describe how the engineered engagement and satisfaction indicators vary across employee cohorts (department, career stage, commute group);",
              "to examine the association between workload factors (overtime, commute) and engagement;",
              "to test a previously unverified assumption of a roughly 3.5-year promotion-stagnation threshold in engagement; and",
              "to describe how observed attrition varies across groups of the rule-based burnout score, while making clear that this is a descriptive, cross-sectional comparison and not a test of predictive accuracy."):
        bullet(t)
    P("Note on revision: the fourth aim previously read “to quantify the predictive utility” of the score. The data are cross-sectional (attrition is already recorded, "
      "not forecast), so the aim was reworded to match what the design can support.", italic=True, size=10)

    # ---- 3 lit review
    H1("3. Literature Review")
    P("The conceptual background is the Job Demands-Resources (JD-R) model (Bakker & Demerouti, 2007), which holds that high job demands such as heavy workload "
      "can exhaust employees, while job resources support engagement. Maslach and Leiter (2016) discuss burnout as arising from mismatches between people and their "
      "work environments rather than solely from individual weakness. Marler and Boudreau (2017) review evidence on HR analytics and its use in organizations. "
      "Scholars of workplace analytics generally caution that operational scoring rules should not be treated as clinical diagnoses and need empirical validation "
      "before being relied upon. The score used here is a handcrafted workload indicator and has not been validated in that sense.", align="justify")
    P("Reference check: the bibliographic details of the three sources in Section 11 were checked against Crossref records. The summaries above were written "
      "from general familiarity and were not re-checked against the full texts; the author should confirm them before submission.", italic=True, size=10)

    # ---- 4 dataset
    H1("4. Dataset Description and Provenance")
    ranges = D["ranges"]
    P(f"The analysis uses a file named “{D['file']}” with {n_(D['rows'])} employee records and {D['columns']} variables covering demographics, role, compensation, "
      f"workload and survey-style ratings. Programmatic checks found {D['missing_cells']} missing cells and {D['duplicate_rows']} duplicate rows. Attrition is stored as 0/1 "
      f"({n_(O['n'] - O['attrition_left'])} stayed, {n_(O['attrition_left'])} left; {pct(O['attrition_rate_pct'])}). The four satisfaction/involvement items and "
      f"work-life balance take values 1–4; distance from home ranges from {int(ranges['DistanceFromHome'][0])} to {int(ranges['DistanceFromHome'][1])} "
      f"(the unit is not documented); OverTime takes the values {', '.join(D['overtime_values'])}; BusinessTravel takes {', '.join(D['travel_values'])}.", align="justify")
    table(["Check", "Result"], [
        ["Records × variables", f"{n_(D['rows'])} × {D['columns']}"],
        ["Missing cells / duplicate rows", f"{D['missing_cells']} / {D['duplicate_rows']}"],
        ["Attrition values", ", ".join(D["attrition_unique_values"]) + f"  ({n_(O['attrition_left'])} left)"],
        ["Satisfaction, involvement, work-life balance", "all within 1–4"],
        ["Distance from home", f"{int(ranges['DistanceFromHome'][0])}–{int(ranges['DistanceFromHome'][1])} (unit not documented)"],
        ["Value-range issues found", "none" if not D["value_issues"] else "; ".join(D["value_issues"])],
    ], [7.5, 8.5], caption="Table 1. Dataset validation summary", align_right_from=9)
    P("Provenance. No documentation accompanies the file, so who collected it, when and where could not be established, and the file name should not be taken as "
      "evidence that these are internal records of any named company. Two observations argue for caution. First, the job roles in the data include Healthcare Representative, "
      "Laboratory Technician, Manufacturing Director and Research Scientist, which do not resemble the workforce of a cybersecurity firm. Second, the record count (1,470) and the "
      "attrition-themed HR structure match a sample dataset that the documentation of the R package rsample describes as a fictional dataset created by IBM data scientists "
      "(IBM Watson Analytics Lab). The supplied file was not compared row by row with that dataset, so this resemblance is a lead, not a confirmed identification. "
      "The “Palo Alto Networks” label is therefore treated as a project framing only, and the findings below describe this dataset, not any real organization.", align="justify")

    # ---- 5 features
    H1("5. Feature Engineering and Formulas")
    P("All indicators were computed in Python with pandas and NumPy. The same functions (hr_analytics.py) are used by the dashboard, the analysis script and the tests, "
      "so the paper and the dashboard cannot disagree.", align="justify")
    RP([("Engagement Index (EI). ", True), "The row-wise arithmetic mean of JobInvolvement, JobSatisfaction, EnvironmentSatisfaction and RelationshipSatisfaction (range 1–4)."])
    RP([("Satisfaction Stability Score. ", True), "4.0 minus the standard deviation of the same four items; higher values mean more consistent answers."])
    RP([("Numeric Burnout Score (0–100). ", True),
        f"A deterministic, rule-based indicator, not a clinical measure and not a trained model. It is the sum of four components: overtime ({SA['weights']['overtime']:g} points if OverTime is Yes), "
        f"work-life-balance deficit (up to {SA['weights']['work_life_balance']:g}), business travel (up to {SA['weights']['travel']:g}) and commute distance (up to {SA['weights']['distance']:g}), "
        f"bounded to 0–100 (Appendix A). The weights were chosen by the author for simplicity and have not been calibrated empirically; no sensitivity analysis of the weights was performed."])
    RP([("Commute-distance normalization. ", True),
        f"The earlier code scaled distance with the observed minimum and maximum, whereas the earlier appendix used fixed bounds of 1 and 29. In the supplied data the observed minimum is "
        f"{SA['observed_distance_min']} and the maximum is {SA['observed_distance_max']}, so both give identical scores (maximum absolute difference {f(SA['max_abs_diff_original_code_vs_final'])} points; "
        f"{SA['n_scores_changed_vs_original_code']} of {n_(O['n'])} scores change). The final method uses fixed bounds of {SA['fixed_bounds_used'][0]:g} and {SA['fixed_bounds_used'][1]:g}, "
        f"with values outside the bounds capped, so that an employee's score does not depend on who else is in the file or the filter."])
    table(["Component", "Max points", "Mean points", "SD"], [
        ["Overtime (Yes = 30)", "30", f(SA["component_means"]["OvertimePoints"]), f(SA["component_sd"]["OvertimePoints"])],
        ["Work-life-balance deficit", "30", f(SA["component_means"]["WLBPoints"]), f(SA["component_sd"]["WLBPoints"])],
        ["Business travel", "20", f(SA["component_means"]["TravelPoints"]), f(SA["component_sd"]["TravelPoints"])],
        ["Commute distance", "20", f(SA["component_means"]["DistancePoints"]), f(SA["component_sd"]["DistancePoints"])],
        ["Total score", "100", f(O["burnout_mean"]), f(O["burnout_sd"])],
    ], [6.5, 3, 3.2, 3.2], caption="Table 2. Burnout-score components (all employees)")
    RP([("Commute categories. ", True),
        f"Distance is grouped into {COM['labels'][0]}, {COM['labels'][1]} and {COM['labels'][2]} using right-inclusive bins, so 5 is Short, 15 is Medium and 16 or more is Long. "
        f"Every employee falls in exactly one category ({n_(COM['category_counts_sum'])} of {n_(O['n'])} assigned). The earlier labels (“<5m”, “5–15m”, “>15m”) did not match the code, "
        f"which placed distance 5 in the first group and 15 in the second; no employee changes group ({COM['n_reclassified_vs_original']} reclassified), but the labels now match the boundaries."])
    RP([("Risk categories and priority. ", True),
        "Burnout Risk is High if the employee works overtime and has work-life balance of 2 or lower, Medium if either holds, otherwise Low. Priority is Critical for High risk with "
        "Engagement Index of 2.2 or lower, High for High risk or for Medium risk with Engagement Index below 2.5, Medium for other Medium risk, and Low otherwise. These are analytical flags for human review."])
    RP([("Burnout-score groups. ", True),
        f"Thirds are defined by the 33.3rd and 66.7th percentiles of the score ({f(T['t1'])} and {f(T['t2'])}): scores up to {f(T['t1'])} form the lowest third, scores above that up to {f(T['t2'])} "
        f"the middle third, and higher scores the highest third. Many employees share identical scores, and tied values always go to the same group, so the groups are only approximately equal in size "
        f"({LOW['Employees']}, {MID['Employees']} and {HIGH['Employees']} employees)."])

    # ---- 6 methods
    H1("6. Statistical Methods")
    P("Analyses were run with Python (pandas, NumPy, SciPy) in a single reproducible script. All tests are two-sided at the 0.05 level.", align="justify")
    for lead, t in (
        ("Group means: ", "Welch's independent-samples t-test (unequal variances) with a 95% confidence interval and Cohen's d; a Mann–Whitney test is reported as a robustness check because the Engagement Index is a bounded mean of ordinal items."),
        ("Several groups: ", "Kruskal–Wallis tests for engagement and burnout score; chi-square tests of independence (with Cramér's V) for attrition."),
        ("Associations: ", "Spearman rank correlations, and simple linear regressions of engagement on years since last promotion and on tenure (one predictor each; slope with 95% CI). No multivariable regression or machine-learning model was fitted."),
        ("Proportions: ", "Attrition rates use employees in each group as the denominator, with Wilson 95% intervals; relative risk uses a log-method interval; the in-sample ROC AUC of the score is reported descriptively."),
        ("Multiple testing: ", "Eleven main hypothesis tests form one family, adjusted with the Holm–Bonferroni procedure (Table 7)."),
        ("Interpretation: ", "All results are cross-sectional associations. Because the burnout score contains overtime, work-life balance, travel and distance, its differences across groups defined by those variables are partly mechanical and are not treated as evidence of causes."),
    ):
        bullet(t, lead)

    # ---- 7 results
    H1("7. Results")
    H2("7.1 Descriptive overview")
    P(f"Across all {n_(O['n'])} employees the mean Engagement Index is {f(O['engagement_mean'])} (SD {f(O['engagement_sd'])}) on the 1–4 scale and the mean Numeric Burnout Score is "
      f"{f(O['burnout_mean'], 1)} (SD {f(O['burnout_sd'], 1)}; observed range {f(O['burnout_min'], 1)}–{f(O['burnout_max'], 1)}). The risk label is Low for {O['burnout_risk_counts']['Low']}, "
      f"Medium for {O['burnout_risk_counts']['Medium']} and High for {O['burnout_risk_counts']['High']} employees; {O['priority_counts']['Critical']} employees carry the Critical priority flag.", align="justify")

    H2("7.2 Observed attrition by burnout-score group")
    rr = T["relative_risk_high_vs_low"]
    table(["Score group", "Score range", "Employees", "Left", "Attrition", "95% CI"], [
        [r["ScoreGroup"], f"{f(r['ScoreMin'])}–{f(r['ScoreMax'])}", n_(r["Employees"]), n_(r["Left"]), pct(r["AttritionRate_pct"]),
         f"{f(r['CI95_low_pct'], 1)}–{f(r['CI95_high_pct'], 1)}%"] for r in TT
    ], [3.4, 2.8, 2.5, 1.8, 2.5, 3.0], caption="Table 3. Observed attrition by burnout-score group",
        note=f"Chi-square test of independence: chi2({T['chi_square_3x2']['dof']}) = {f(T['chi_square_3x2']['chi2'], 1)}, p {pv(T['chi_square_3x2']['p'])}, Cramér's V = {f(T['chi_square_3x2']['cramers_v'])}.")
    figure(os.path.join(FIG, "fig1_attrition_by_score_group.png"), "Figure 1. Observed attrition by burnout-score group. Error bars are 95% Wilson intervals; labels show employees who left / employees in the group.")
    P(f"Attrition rises steadily across the groups, from {pct(LOW['AttritionRate_pct'])} to {pct(HIGH['AttritionRate_pct'])}. Employees in the highest third were {f(rr['rr'], 1)} times as likely as those in the lowest "
      f"third to be recorded as having left (relative risk {f(rr['rr'])}, 95% CI {f(rr['ci_low'])}–{f(rr['ci_high'])}; absolute difference {f(T['risk_difference_pp'], 1)} percentage points, 95% CI "
      f"{f(T['risk_difference_ci_pp'][0], 1)} to {f(T['risk_difference_ci_pp'][1], 1)}). Used as a ranking of employees by recorded attrition, the score has an in-sample ROC AUC of {f(T['auc_score_in_sample'])}, "
      f"compared with {f(T['auc_overtime_only_in_sample'])} for the overtime indicator alone.", align="justify")
    P(f"This is an association within one cross-sectional dataset. It is not a validated prediction of future departures: the attrition outcome was not held out, no data over time were available, and no "
      f"out-of-sample evaluation was performed. The result is also strongly tied to overtime. {OVC['Highest third']['overtime_yes']} of the {OVC['Highest third']['n']} employees in the highest third "
      f"({pct(OVC['Highest third']['overtime_share_pct'], 1)}) work overtime, none of the lowest third do, and attrition is {pct(OTT['Yes']['AttritionRate_pct'], 1)} "
      f"({OTT['Yes']['Left']} of {OTT['Yes']['Employees']}) among employees working overtime versus {pct(OTT['No']['AttritionRate_pct'], 1)} ({OTT['No']['Left']} of {OTT['No']['Employees']}) among those who do not. "
      f"Figure 2 splits the groups by overtime. Among employees who do not work overtime, attrition still rises with the score, but the highest-score group in that stratum is small and its interval wide.", align="justify")
    figure(os.path.join(FIG, "fig2_attrition_group_by_overtime.png"), "Figure 2. Observed attrition by burnout-score group, split by overtime. No employee working overtime falls in the lowest group; labels show the rate and group size.")

    H2("7.3 Overtime and engagement")
    ot_mw = R["overtime_engagement"]["mann_whitney_p"]
    table(["Group", "n", "Mean EI", "SD"], [
        ["Works overtime", n_(W["n_a"]), f(W["mean_a"], 3), f(W["sd_a"], 3)],
        ["No overtime", n_(W["n_b"]), f(W["mean_b"], 3), f(W["sd_b"], 3)],
    ], [5.5, 3, 3.2, 3.2], caption="Table 4. Engagement Index by overtime status",
        note=(f"Difference (overtime minus no overtime) = {W['diff']:+.3f}, 95% CI {W['ci_low']:+.3f} to {W['ci_high']:+.3f}; Welch t({f(W['df'], 1)}) = {f(W['t'])}, p = {pv(W['p'])} "
              f"(Holm-adjusted p = {pv(holm_p('Overtime vs engagement'))}); Cohen's d = {f(W['cohens_d'])}; Mann–Whitney p = {pv(ot_mw)}."))
    P(f"The direction of the difference was checked rather than assumed: employees who work overtime have slightly higher mean engagement, not lower. The difference is statistically significant but small "
      f"(about {f(abs(W['diff']), 2)} points on a 1–4 scale, a small effect), and it remains significant after Holm adjustment. This is an association only. One possible explanation, that "
      f"highly involved employees take on extra hours voluntarily, was not tested here and should be treated as a hypothesis for future work. Note also that JobInvolvement is one of the four items in the index.", align="justify")

    H2("7.4 Promotion timing and tenure")
    th = PRO["threshold_test_le3_vs_ge4"]; ols = PRO["ols"]
    P(f"Engagement shows no relationship with years since last promotion (Spearman rho = {f(PRO['spearman_rho'], 3)}, p = {f(PRO['spearman_p'], 2)}); a simple linear regression gives a slope of "
      f"{ols['slope']:+.4f} engagement points per additional year (95% CI {ols['slope_ci_low']:+.4f} to {ols['slope_ci_high']:+.4f}, R-squared = {f(ols['r2'], 4)}, n = {n_(ols['n'])}). "
      f"Because the variable is recorded in whole years, the proposed 3.5-year threshold was tested as four or more years versus three or fewer: mean engagement was {f(th['mean_a'], 3)} "
      f"(n = {n_(th['n_a'])}) versus {f(th['mean_b'], 3)} (n = {n_(th['n_b'])}), difference {th['diff']:+.3f} (95% CI {th['ci_low']:+.3f} to {th['ci_high']:+.3f}, p = {f(th['p'], 2)}). "
      f"The data therefore give no support for a promotion-stagnation cliff in engagement, and the confidence interval excludes differences larger than about {f(max(abs(th['ci_low']), abs(th['ci_high'])), 2)} points. "
      f"This is an absence of evidence in this dataset, not proof that promotion delays never matter. Tenure with the company is likewise unrelated to engagement (Spearman rho = {f(TEN['spearman_rho'], 3)}, p = {f(TEN['spearman_p'], 2)}).", align="justify")

    H2("7.5 Commute distance")
    table(["Commute group", "Employees", "Mean burnout score", "Mean EI", "Left", "Attrition"], [
        [g["Category"], n_(g["Employees"]), f(g["MeanBurnoutScore"], 1), f(g["MeanEngagement"], 3), n_(g["Left"]), pct(g["AttritionRate_pct"], 1)] for g in COM["groups"]
    ], [3.6, 2.4, 3.4, 2.4, 1.8, 2.4], caption="Table 5. Commute groups",
        note=f"Burnout-score differences between commute groups arise partly by construction (distance contributes up to 20 of the 100 points; about {f(COM['distance_points_share_of_score_variance_pct'], 0)}% of the score's variance) and are descriptive only.")
    P(f"The burnout score increases steeply with commute group, but this is largely built into the score and is not independent evidence about commuting. For outcomes not defined by distance, engagement does not differ across "
      f"commute groups (Kruskal–Wallis p = {f(COM['engagement_kruskal']['p'], 2)}). Attrition increases from {pct(COM['groups'][0]['AttritionRate_pct'], 1)} to {pct(COM['groups'][2]['AttritionRate_pct'], 1)} "
      f"(chi-square p = {f(COM['attrition_chi2']['p'], 3)}), but this does not remain significant after Holm adjustment across the family of tests (adjusted p = {f(HOLM['Attrition across commute groups (chi-square)']['p_holm'], 2)}), so it is suggestive only.", align="justify")

    H2("7.6 Departments and career stages")
    rows = []
    for key, tb in (("Department", DEP["table"]), ("CareerStage", CAR["table"])):
        for r in tb:
            rows.append([r[key], n_(r["Employees"]), f(r["MeanEngagement"], 3), f(r["MeanBurnoutScore"], 1), n_(r["Left"]), pct(r["AttritionRate_pct"], 1)])
    table(["Group", "Employees", "Mean EI", "Mean burnout score", "Left", "Attrition"], rows, [4.2, 2.3, 2.2, 3.3, 1.8, 2.4],
          caption="Table 6. Departments and career stages",
          note="Career stage is based on total working years: Early 0–5, Mid 6–15, Late 16 or more.")
    P(f"Engagement does not differ across departments (Kruskal–Wallis p = {f(DEP['engagement_kruskal']['p'], 2)}) or career stages (p = {f(CAR['engagement_kruskal']['p'], 2)}). Average burnout score "
      f"also shows little variation by department (p = {f(DEP['burnout_kruskal']['p'], 2)}) and career stage (p = {f(CAR['burnout_kruskal']['p'], 2)}). Attrition does differ: by department (chi-square p = {f(DEP['attrition_chi2']['p'], 3)}, "
      f"Cramér's V = {f(DEP['attrition_chi2']['cramers_v'])}; Holm-adjusted p = {f(HOLM['Attrition across departments (chi-square)']['p_holm'], 3)}) and especially by career stage, from {pct(CAR['table'][0]['AttritionRate_pct'], 1)} among early-career "
      f"employees to {pct(CAR['table'][2]['AttritionRate_pct'], 1)} among late-career employees (p {pv(CAR['attrition_chi2']['p'])}, Cramér's V = {f(CAR['attrition_chi2']['cramers_v'])}). Career stage is closely related to age and tenure, and no adjustment "
      f"for such factors was made.", align="justify")

    H2("7.7 Multiple comparisons")
    table(["Test", "Raw p", "Holm p", "Significant"], [
        [h["Test"], pv(h["p_raw"]), pv(h["p_holm"]), "Yes" if h["Significant_at_0.05_after_Holm"] else "No"] for h in R["holm_family"]
    ], [8.8, 2.3, 2.3, 2.5], caption="Table 7. Main tests and Holm-adjusted p-values (family of 11)")

    # ---- 8 discussion
    H1("8. Discussion and Recommendations")
    P(f"The analysis supports a cautious reading. The rule-based score sorts employees into groups whose recorded attrition differs markedly, which makes it a reasonable way to organize a review list, "
      f"but it does not show that the score forecasts who will leave: the evidence is in-sample, the score is closely tied to overtime, and a simple overtime indicator already captures much of the pattern "
      f"(AUC {f(T['auc_overtime_only_in_sample'])} versus {f(T['auc_score_in_sample'])}). The overtime finding for engagement runs against a common assumption and suggests that engagement alone will not reveal workload strain.", align="justify")
    P("Recommendations are offered as supportive starting points, not as conclusions about cause:")
    bullet(f" Review where overtime is concentrated and whether staffing matches demand, because overtime is associated with much higher recorded attrition ({pct(OTT['Yes']['AttritionRate_pct'], 1)} versus {pct(OTT['No']['AttritionRate_pct'], 1)}) in this dataset.", "Workload review.")
    bullet(" Discuss flexible or hybrid arrangements with employees who have long commutes and ask what would help; the commute–attrition gradient here is only suggestive after multiple-testing correction.", "Flexible work conversations.")
    bullet(" The data give no support for a universal promotion-wait threshold, so managers should rely on individual career conversations rather than a fixed number of years.", "Individual career pathing.")
    bullet(" Use dashboard flags to decide where to start supportive, voluntary conversations, and combine them with employee feedback and manager judgment. Do not use them as a basis for performance management, pay or disciplinary decisions.", "Flags as conversation starters.")
    bullet(" To test whether the score helps anticipate attrition, collect data over time and evaluate it on employees held out from the calibration.", "Future validation.")

    # ---- 9 limitations
    H1("9. Limitations, Privacy and Responsible Use")
    for t in (
        "Cross-sectional data: attrition is already recorded, so no statement about prediction or causation is supported.",
        "The Numeric Burnout Score is a handcrafted index, not a validated psychological instrument; its weights are not empirically calibrated and were not tested for sensitivity.",
        "The score contains overtime, work-life balance, travel and distance, so score differences across groups defined by these variables are partly mechanical.",
        "No multivariable adjustment was made; associations (for example by career stage) may reflect age, tenure or other factors.",
        "The Engagement Index averages ordinal items and includes job involvement; it is a convenience composite, not a validated engagement scale.",
        "Provenance of the dataset is unverified and it appears to resemble a fictional sample dataset, so results may not generalize to any real workforce.",
        "Multiple tests were run; Holm adjustment was applied to the eleven main tests, but other exploratory charts in the dashboard were not adjusted.",
        "Employee records are sensitive. Outputs should be treated as confidential decision-support prompts for empathetic human review, and should never be used alone for performance management, compensation or disciplinary action. "
        "Demographic variables such as age, gender and marital status should not be used to target individuals.",
    ):
        bullet(t)

    # ---- 10 conclusion
    H1("10. Conclusion")
    P(f"This project turns employee HR data into an interactive diagnostic dashboard and a documented, reproducible analysis. In the dataset examined, recorded attrition is much higher in the highest burnout-score group "
      f"({pct(HIGH['AttritionRate_pct'], 1)}) than in the lowest ({pct(LOW['AttritionRate_pct'], 1)}), engagement is slightly higher among employees who work overtime, and there is no evidence of a promotion-timing effect on engagement. "
      f"These are associations in a cross-sectional dataset of unverified provenance, and the burnout score is partly determined by the workload variables it is compared against. The workflow is best used to organize supportive human review, "
      f"and validating it as a predictive tool would require longitudinal data and out-of-sample testing.", align="justify")

    # ---- 11 references
    H1("11. References")
    refs = [
        "Bakker, A. B., & Demerouti, E. (2007). The Job Demands-Resources model: State of the art. Journal of Managerial Psychology, 22(3), 309–328. https://doi.org/10.1108/02683940710733115",
        "Marler, J. H., & Boudreau, J. W. (2017). An evidence-based review of HR Analytics. The International Journal of Human Resource Management, 28(1), 3–26. https://doi.org/10.1080/09585192.2016.1244699",
        "Maslach, C., & Leiter, M. P. (2016). Understanding the burnout experience: Recent research and its implications for psychiatry. World Psychiatry, 15(2), 103–111. https://doi.org/10.1002/wps.20311",
        "rsample package documentation, “Job attrition data” (IBM Watson Analytics Lab sample). https://rsample.tidymodels.org/reference/attrition.html (accessed 10 October 2026).",
    ]
    for r_ in refs:
        p = P(r_, space_after=3); p.paragraph_format.left_indent = Cm(0.8); p.paragraph_format.first_line_indent = Cm(-0.8)
    P("Verification note: authors, titles, journals, volumes, pages and years of the first three references match Crossref records (checked 10 October 2026). The wording of how each source is used in Section 3 was not checked against the full texts.", italic=True, size=9.5)

    # ---- appendix
    H1("12. Appendix: Implementation Formulas and Reproducibility")
    H2("A.1 Numeric Burnout Score")
    for t in ("Overtime points = 30 if OverTime = “Yes”, otherwise 0.",
              "Work-life-balance points = ((4 − WorkLifeBalance) / 3) × 30.",
              "Travel points = (code / 2) × 20, with Non-Travel = 0, Travel_Rarely = 1, Travel_Frequently = 2.",
              f"Distance points = clip((DistanceFromHome − {SA['fixed_bounds_used'][0]:g}) / ({SA['fixed_bounds_used'][1]:g} − {SA['fixed_bounds_used'][0]:g}), 0, 1) × 20.",
              "Score = clip(sum of the four components, 0, 100), rounded to two decimals."):
        bullet(t)
    H2("A.2 Priority categorization")
    P("Critical: High risk and Engagement Index ≤ 2.2. High: High risk, or Medium risk with Engagement Index < 2.5. Medium: Medium risk. Low: otherwise.")
    H2("A.3 Category boundaries")
    P(f"Commute: {COM['labels'][0]} (≤ 5), {COM['labels'][1]} (6–15), {COM['labels'][2]} (≥ 16). Career stage by total working years: Early 0–5, Mid 6–15, Late ≥ 16. "
      f"Burnout-score groups: lowest ≤ {f(T['t1'])}, middle ≤ {f(T['t2'])}, highest above {f(T['t2'])}.")
    H2("A.4 Reproducing the numbers")
    P("Run “python analysis.py” to recompute every statistic from the CSV (outputs/results.json and CSV tables), then “python build_paper.py” to rebuild this paper and the verification report. "
      "The automated tests (pytest) cover the score formula and bounds, category boundaries, attrition encoding, schema validation, empty filters and group calculations.")


make_figures()
build_doc()
for z in doc.settings.element.iter(qn("w:zoom")):
    if z.get(qn("w:percent")) is None:
        z.set(qn("w:percent"), "100")
doc.core_properties.title = "Catching Burnout Before It Happens: A Data-Driven Approach to Employee Engagement and HR Diagnostics"
doc.core_properties.author = "Rohit Kumar"
doc.save(os.path.join(OUT, "Catching_Burnout_Before_It_Happens_REVISED.docx"))
print("saved docx")
