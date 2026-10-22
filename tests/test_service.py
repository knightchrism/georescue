import json
import geopandas as gpd
from shapely.geometry import box, Polygon
from georescue import service, publish


def _setup(tmp_path):
    g = gpd.GeoDataFrame({"RE": ["A", "B", "C", "D"]}, geometry=[
        box(0, 0, 0.001, 0.001), box(0.0002, 0.0002, 0.0004, 0.0004),            # B fully inside A -> contained_parcel
        box(0.002, 0, 0.003, 0.001), Polygon([(0.004, 0), (0.005, 0.001), (0.005, 0), (0.004, 0.001)])], crs=4326)  # D bow-tie invalid
    g["geometry"] = g.geometry.translate(-81.6, 30.3)   # Jacksonville, so EPSG:2236 is valid
    data = tmp_path / "p.geojson"; g.to_file(data, driver="GeoJSON")
    cfg = tmp_path / "c.yaml"
    cfg.write_text(f"name: t\nid_field: RE\nexpected_crs: EPSG:4326\nworking_crs: EPSG:2236\n"
                   f"service: {{data_path: {data}, max_age_hours: 1000, pao: false, clerk: false, write_corrected: false}}\n")
    return cfg


def test_run_writes_manifest_latest_and_only_safe_repairs(tmp_path):
    cfg = _setup(tmp_path); out = tmp_path / "out"
    m = service.run(str(cfg), str(out), log=lambda *a: None)
    st = {s["name"]: s["status"] for s in m["steps"]}
    assert st["fetch"] == "skipped" and st["inspect"] == "ok" and st["safe_repair"] == "ok"
    latest = out / "latest"
    assert (latest / "manifest.json").exists() and (out / "runs" / m["run_id"] / "manifest.json").exists()
    v = json.loads((latest / "verdicts.json").read_text())
    assert any(x["check"] == "contained_parcel" and x["direction"] == "cut smaller from larger" and x["status"] == "proposed" for x in v)
    import pandas as pd
    log = pd.read_csv(latest / "changelog.csv")
    applied = log[log.applied.astype(bool)]
    assert set(applied.action) <= {"make_valid"}          # nothing but invalid-geometry repair is auto-applied
    assert (log.check == "contained_parcel").any() and not log[log.check == "contained_parcel"].applied.astype(bool).any()


def test_publish_site(tmp_path):
    cfg = _setup(tmp_path); out = tmp_path / "out"
    m = service.run(str(cfg), str(out), log=lambda *a: None)
    r = publish.publish(str(out / "latest"), str(tmp_path / "site"), str(out / "runs"))
    s = tmp_path / "site"
    assert (s / "index.html").exists() and (s / "history.html").exists() and (s / "data" / "issues.json").exists()
    assert r["cases"] >= 1 and len(list((s / "cases").glob("*.html"))) == r["cases"]
    assert "contained_parcel" in (s / "index.html").read_text()
    assert m["run_id"] in (s / "history.html").read_text()
