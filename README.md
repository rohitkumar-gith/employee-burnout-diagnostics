# 🛡️ HR Diagnostics & Retention Dashboard 
**Predicting burnout before it happens.**

Hello! 👋 Welcome to my Data Analytics internship project, developed during my time with Unified Mentor. 

## 💡 The Story Behind the Project
In high-pressure cybersecurity environments like Palo Alto Networks, employee burnout isn't just a buzzword—it is a silent retention killer. Too often, HR interventions are purely reactive; by the time a manager realizes an employee is exhausted, that person has already decided to leave. 

I built this enterprise-grade Streamlit application to change that. 

Instead of just looking at historical attrition, this dashboard acts as an early-warning system. By weaving together data on work-life balance, commute times, overtime hours, and job satisfaction, it helps HR leaders proactively identify the employees who need support *today*, so they don't lose them *tomorrow*.

## ✨ What It Actually Does
I designed this dashboard to be a highly actionable tool for managers, not just a collection of charts. 

* **🔥 The Burnout Risk Engine:** A custom 0-100 `NumericBurnoutScore` that mathematically weights the hidden stressors of a job (like long commutes combined with frequent overtime).
* **🚨 Smart Manager Action Panel:** An algorithmic priority system that automatically flags "Critical" employees and generates dynamic, plain-English recommendations (e.g., *"High burnout detected: Recommend auditing workload capacity immediately"*).
* **⚖️ Satisfaction Stability:** It doesn't just measure if someone is happy; it measures how *consistently* happy they are across different aspects of their environment.
* **🔍 Deep-Dive Rosters:** Every chart is backed by an interactive drill-down table, allowing managers to see exactly who makes up the data and export targeted CSV reports with one click.

## 🛠️ How It Was Built
I wanted this application to be as fast as it is insightful, which meant optimizing the backend for enterprise-scale data.
* **Python & Streamlit:** For the core application architecture and reactive UI.
* **Pandas & NumPy:** For heavy data manipulation, missing value handling, and vectorized metric engineering (no slow `for-loops` here!).
* **Plotly (Express & Graph Objects):** For the interactive, enterprise-styled visualizations (including Gauge charts and Correlation Matrices).
* **Statsmodels:** To power the OLS trendlines in the career stagnation analysis.

## 🚀 Want to try it out?
If you want to run this dashboard locally on your machine, it's super easy! 

1. **Clone this repository:**
   ```bash
   git clone [https://github.com/rohitkumar-gith/employee-burnout-diagnostics.git](https://github.com/rohitkumar-gith/employee-burnout-diagnostics.git)