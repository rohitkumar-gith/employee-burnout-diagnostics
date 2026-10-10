"""
Smoke test of app.py's page logic using STAND-IN streamlit/plotly modules.

This is NOT a real Streamlit run: no browser, no rendering. It only executes
every page's Python/pandas code path to catch NameErrors, KeyErrors and pandas
errors. Real verification needs `streamlit run app.py` in an environment where
streamlit, plotly and statsmodels are installed.

Run:  python tests/smoke_app_with_stubs.py
"""
import os
import runpy
import sys
import types
from unittest.mock import MagicMock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PAGES = ["Executive Summary", "Department Scorecard", "Engagement Health Overview",
         "Burnout Risk Dashboard", "Role & Career Stage Analysis", "Manager Action Panel",
         "Documentation & Export"]


class Stop(Exception):
    pass


def build_streamlit(page, overrides=None):
    overrides = overrides or {}
    st = MagicMock(name="streamlit")
    st.cache_data = lambda f=None, **k: (f if f else (lambda g: g))

    def multiselect(label, options=None, default=None, **k):
        return overrides.get(label, default if default is not None else [])
    def slider(label, min_value=None, max_value=None, value=None, **k):
        return overrides.get(label, value)
    def checkbox(label, value=False, **k):
        return overrides.get(label, value)
    def columns(spec, **k):
        n = spec if isinstance(spec, int) else len(spec)
        return [MagicMock() for _ in range(n)]
    def tabs(labels):
        return [MagicMock() for _ in labels]
    def selectbox(label, options=None, **k):
        return list(options)[0]
    def stop():
        raise Stop()
    st.sidebar.multiselect = multiselect
    st.sidebar.slider = slider
    st.sidebar.checkbox = checkbox
    st.sidebar.radio = lambda label, options, **k: page
    st.sidebar.file_uploader = lambda *a, **k: None
    st.columns, st.tabs, st.selectbox, st.stop = columns, tabs, selectbox, stop
    return st


def build_plotly():
    px, go = MagicMock(name="px"), MagicMock(name="go")
    plotly = types.ModuleType("plotly"); plotly.express = px; plotly.graph_objects = go
    return plotly, px, go


def run(page, overrides=None):
    st = build_streamlit(page, overrides)
    plotly, px, go = build_plotly()
    sys.modules.update({"streamlit": st, "plotly": plotly,
                        "plotly.express": px, "plotly.graph_objects": go})
    try:
        runpy.run_path(os.path.join(ROOT, "app.py"), run_name="__main__")
        return "ok"
    except Stop:
        return "stopped (st.stop)"


if __name__ == "__main__":
    os.chdir(ROOT)
    failures = 0
    for p in PAGES:
        try:
            print(f"{p:35s} -> {run(p)}")
        except Exception as e:  # noqa
            failures += 1
            print(f"{p:35s} -> FAILED: {type(e).__name__}: {e}")
    # an empty filter must stop cleanly with a warning, not crash
    try:
        print(f"{'Empty filter result':35s} -> {run('Executive Summary', {'Department': []})}")
    except Exception as e:  # noqa
        failures += 1
        print(f"Empty filter -> FAILED: {type(e).__name__}: {e}")
    # a narrow filter (overtime only, high burnout only) must still render
    for ov in ({"Show Overtime Employees Only": True}, {"Burnout Risk": ["High"]}):
        for p in ("Executive Summary", "Burnout Risk Dashboard", "Manager Action Panel", "Role & Career Stage Analysis"):
            try:
                print(f"{p + ' ' + str(list(ov))[:28]:35s} -> {run(p, ov)}")
            except Exception as e:  # noqa
                failures += 1
                print(f"{p} {ov} -> FAILED: {type(e).__name__}: {e}")
    sys.exit(1 if failures else 0)
