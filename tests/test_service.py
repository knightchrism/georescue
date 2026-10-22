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


def test_publish_refuses_empty_run(tmp_path):
    import json, pytest
    from georescue import publish as pub
    L = tmp_path / "latest"; L.mkdir()
    (L / "manifest.json").write_text(json.dumps({"steps": [{"name": "fetch", "status": "error", "error": "x"}, {"name": "inspect", "status": "error"}]}))
    site = tmp_path / "site"; site.mkdir(); (site / "index.html").write_text("good")
    with pytest.raises(pub.NotPublishable):
        pub.publish(str(L), str(site), str(tmp_path / "runs"))
    assert (site / "index.html").read_text() == "good"


def test_published_site_has_no_owner_names():
    """The committed public site must not contain owner fields or known owner names."""
    import json, re
    from pathlib import Path
    site = Path("site")
    if not (site / "index.html").exists():
        import pytest; pytest.skip("no published site")
    import hashlib
    bad_h = {'74b75149cbe6e496', '6df23ccc3ac208e5', 'cf38ea632d17b28e', 'a5146c9a626dff2b', 'd20b4ad6e953b622', 'dc7c1a6c18b099a4'}  # sha256 prefixes of known surnames (names themselves not stored)
    class _B:
        @staticmethod
        def search(t):
            return next((w for w in re.findall(r'[A-Za-z]+', t) if hashlib.sha256(w.lower().encode()).hexdigest()[:16] in bad_h), None)
    bad = _B()
    for f in site.rglob("*"):
        if f.suffix in (".html", ".json", ".geojson"):
            t = f.read_text()
            assert not bad.search(t), f
            assert not re.search(r'"(owner|owners|LNAMEOWNER|DirectName|IndirectName|grantor|grantee|mail\w*)"\s*:\s*"[A-Z]', t), f
    assert "not authoritative" in (site / "index.html").read_text()
    assert (site / "terms.html").exists()


def test_redactor_replaces_names():
    from georescue.redact import Redactor
    r = Redactor({"001542 0010": {"DOE JOHN Q"}}, surname_pids={"001542 0010"})
    assert r.text("Doe's lot; DOE JOHN Q owns 001542 0010") == "Owner of 001542 0010 lot; Owner of 001542 0010 owns 001542 0010"
    assert r.obj({"owner": "DOE JOHN Q", "orb": "19870-841"}) == {"orb": "19870-841"}
