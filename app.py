import tempfile, os, json
from pathlib import Path
import streamlit as st
from georescue import pipeline, io

st.set_page_config("GeoRescue", layout="wide")
st.title("GeoRescue — parcel QA & repair")
up = st.file_uploader("Dataset (GeoPackage, GeoJSON, zipped shapefile)", type=["gpkg", "geojson", "json", "zip"])
cfg = st.file_uploader("Rules YAML (optional)", type=["yaml", "yml"])
src = os.environ.get("GEORESCUE_DEMO") if not up else None
if up or src:
    d = Path(tempfile.mkdtemp())
    if up:
        src = d / up.name; src.write_bytes(up.getvalue())
    cp = None
    if cfg:
        cp = d / "rules.yaml"; cp.write_bytes(cfg.getvalue())
    elif os.environ.get("GEORESCUE_DEMO_CONFIG"):
        cp = os.environ["GEORESCUE_DEMO_CONFIG"]
    with st.spinner("Inspecting & repairing..."):
        res = pipeline.run_repair(src, d / "out", cp)
    s = res["summary"]
    c = st.columns(3)
    c[0].metric("Features", s["features"]); c[1].metric("Issues", s["issues_total"]); c[2].metric("Features w/ issues", s["features_with_issues"])
    st.subheader("Issues by check"); st.bar_chart(s["issues_by_check"])
    st.subheader("Map preview (first 2,000 features)")
    g = io.load(src).head(2000).to_crs(4326)
    st.map(g.geometry.representative_point().get_coordinates().rename(columns={"x": "lon", "y": "lat"}))
    st.subheader("Downloads")
    for k, p in res["outputs"].items():
        st.download_button(k, Path(p).read_bytes(), file_name=k)
