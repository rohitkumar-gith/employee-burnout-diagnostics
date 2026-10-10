"""Capture the headline metric values app.py would display on the Executive
Summary (default filters), using the stand-in modules from smoke_app_with_stubs.
Writes outputs/dashboard_metrics.json so the verification report can compare
the dashboard's numbers with the paper's numbers. Not a rendered-UI check."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smoke_app_with_stubs as sm

ROOT = sm.ROOT
os.chdir(ROOT)
st = sm.build_streamlit("Executive Summary")
plotly, px, go = sm.build_plotly()
captured = {}
class Rec:
    def __init__(self): pass
orig_metric = st.metric
import types
def metric(label, value, *a, **k):
    captured[label] = value
# columns() returns MagicMocks whose .metric must also record
def columns(spec, **k):
    n = spec if isinstance(spec, int) else len(spec)
    out = []
    for _ in range(n):
        m = sm.MagicMock(); m.metric = metric; out.append(m)
    return out
st.columns = columns; st.metric = metric
sys.modules.update({"streamlit": st, "plotly": plotly, "plotly.express": px, "plotly.graph_objects": go})
import runpy
runpy.run_path(os.path.join(ROOT, "app.py"), run_name="__main__")
os.makedirs("outputs", exist_ok=True)
json.dump(captured, open("outputs/dashboard_metrics.json", "w"), indent=2)
print(json.dumps(captured, indent=2))
