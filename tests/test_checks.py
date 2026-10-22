import geopandas as gpd, pytest, shapely
from shapely.geometry import box, Polygon
from georescue.config import Config
from georescue import checks, repair, pipeline

CFG = Config.load("configs/parcels_example.yaml")
bowtie = Polygon([(0, 0), (10, 10), (10, 0), (0, 10)])

def mk(rows, crs="EPSG:3857"):
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=crs)

def base():
    return [dict(PID="A", ACRES="1.5", geometry=box(0, 0, 10, 10)), dict(PID="B", ACRES=2.0, geometry=box(10, 0, 20, 10))]

def kinds(g, cfg=CFG):
    return checks.inspect(g, cfg)["check"].value_counts().to_dict()

def test_clean():
    k = kinds(mk(base())); k.pop("attribute_wrong_type")  # "1.5" text
    assert k == {}

def test_invalid_and_repair():
    g = mk(base() + [dict(PID="C", ACRES=1.0, geometry=box(30,0,40,10).union(bowtie.buffer(0)) if False else Polygon([(30,0),(40,10),(40,0),(30,10)]))])
    assert kinds(g)["geometry_invalid"] == 1
    fixed, log = repair.repair(g, CFG)
    r = log[log.check == "geometry_invalid"].iloc[0]
    assert r.applied and r.post_valid and r.feature_id == "C"
    assert fixed.geometry.is_valid.all()

def test_empty_missing():
    g = mk(base() + [dict(PID="E", ACRES=1.0, geometry=Polygon()), dict(PID="M", ACRES=1.0, geometry=None)])
    k = kinds(g); assert k["geometry_empty"] == 1 and k["geometry_missing"] == 1

def test_duplicate_ids_and_geoms():
    g = mk(base() + [dict(PID="A", ACRES=2.0, geometry=box(10, 0, 20, 10))])
    k = kinds(g); assert k["duplicate_id"] == 2 and k["duplicate_geometry"] == 2

def test_exact_dup_dropped():
    g = mk(base() + [dict(PID="B", ACRES=2.0, geometry=box(10, 0, 20, 10))])
    fixed, log = repair.repair(g, CFG)
    assert len(fixed) == 2 and (log.action == "drop_feature").sum() == 1

def test_attributes():
    g = mk([dict(PID="", ACRES="abc", geometry=box(0, 0, 1, 1))])
    k = kinds(g); assert k["attribute_missing"] == 1 and k["attribute_wrong_type"] == 1

def test_coerce_logged():
    fixed, log = repair.repair(mk(base()), CFG)
    r = log[log.action == "coerce_type"].iloc[0]
    assert r.before == "'1.5'" and r.after == "1.5" and fixed.iloc[0].ACRES == 1.5

def test_crs():
    assert kinds(mk(base(), crs=None)).get("crs_missing") == 1
    assert kinds(mk(base(), crs="EPSG:32617")).get("crs_unexpected") == 1
    fixed, log = repair.repair(mk(base(), crs=None), CFG)
    assert fixed.crs.to_epsg() == 3857 and "assign_crs" in set(log.action)

def test_bounds():
    g = mk(base() + [dict(PID="F", ACRES=1.0, geometry=box(1e6, 1e6, 1e6 + 10, 1e6 + 10))])
    assert kinds(g)["out_of_bounds"] == 1

def test_overlap_and_trim():
    g = mk([dict(PID="A", ACRES=1.0, geometry=box(0, 0, 10, 10)), dict(PID="B", ACRES=1.0, geometry=box(9, 0, 20, 10))])
    assert kinds(g)["overlap"] == 1
    fixed, log = repair.repair(g, CFG)
    assert (log.action == "trim_overlap").sum() == 1
    assert checks.inspect(fixed.drop(columns="_src_row"), CFG)["check"].tolist().count("overlap") == 0

def test_gap_and_sliver():
    g = mk([dict(PID="A", ACRES=1.0, geometry=box(0, 0, 10, 10)), dict(PID="B", ACRES=1.0, geometry=box(10.5, 0, 20, 10)),
            dict(PID="C", ACRES=1.0, geometry=box(0, 10, 20, 20)), dict(PID="D", ACRES=1.0, geometry=box(0, -10, 20, 0)),
            dict(PID="S", ACRES=1.0, geometry=box(30, 0, 30.1, 10))])
    k = kinds(g); assert k["gap"] == 1 and k["sliver_polygon"] == 1

def test_config_validation():
    with pytest.raises(Exception):
        Config.model_validate({"expected_crs": "NOT_A_CRS"})
    with pytest.raises(Exception):
        Config.model_validate({"bounds": {"minx": 1, "miny": 0, "maxx": 0, "maxy": 1}})

def test_pipeline_outputs(tmp_path):
    g = mk(base() + [dict(PID="C", ACRES=1.0, geometry=Polygon([(30,0),(40,10),(40,0),(30,10)]))])
    src = tmp_path / "in.geojson"; g.to_file(src)
    res = pipeline.run_repair(src, tmp_path / "out", "configs/parcels_example.yaml")
    for p in res["outputs"].values():
        assert open(p, "rb").read()
    import pandas as pd
    d = pd.read_csv(res["outputs"]["diff.csv"])
    assert {"geometry", "attribute"} <= set(d.change)


# --- MCP inspect filters ---
from georescue.mcp_server import filter_issues

def _iss():
    g = mk(base() + [dict(PID="C", ACRES=1.0, geometry=Polygon([(30,0),(40,10),(40,0),(30,10)])),
                     dict(PID="D", ACRES=1.0, geometry=box(5, 0, 15, 10))])
    return checks.inspect(g, CFG)

def test_filter_check_severity():
    iss = _iss()
    r = filter_issues(iss, {}, check=["geometry_invalid"])
    assert r["matched"] == 1 and r["issues"][0]["check"] == "geometry_invalid"
    assert "geometry_wkt" not in r["issues"][0]
    r = filter_issues(iss, {}, severity=["error"])
    assert all(x["severity"] == "error" for x in r["issues"]) and r["matched"] == (iss.severity == "error").sum()

def test_filter_paging_and_wkt():
    iss = _iss(); n = len(iss)
    a = filter_issues(iss, {}, limit=2, offset=0)["issues"]
    b = filter_issues(iss, {}, limit=2, offset=2)["issues"]
    assert len(a) == 2 and a != b and filter_issues(iss, {}, limit=10, offset=n)["issues"] == []
    r = filter_issues(iss, {}, check=["overlap"], include_wkt=True)
    assert r["matched"] >= 1 and r["issues"][0]["geometry_wkt"].startswith(("POLYGON", "MULTIPOLYGON"))


# --- overlap trim ---
def _ov(cfg):
    big = dict(PID="BIG", ACRES=1.0, geometry=box(0, 0, 100, 100))
    small = dict(PID="SMALL", ACRES=1.0, geometry=box(98, 0, 110, 10))   # 2x10 = 20 overlap
    return mk([big, small]), cfg

def _cfg(**kw):
    c = CFG.model_copy(deep=True); c.topology.overlap_min_area = 1.0
    for k, v in kw.items(): setattr(c.repair, k, v)
    return c

def test_overlap_trim_smaller():
    g, cfg = _ov(_cfg(trim_overlaps_below_area=50))
    fixed, log = repair.repair(g, cfg)
    r = log[log.action == "trim_overlap"].iloc[0]
    assert r.feature_id == "SMALL" and r.applied and r.post_valid
    assert r.before_area == pytest.approx(120) and r.after_area == pytest.approx(100)
    assert fixed.geometry.iloc[0].equals(box(0, 0, 100, 100))
    assert shapely.intersection(fixed.geometry.iloc[0], fixed.geometry.iloc[1]).area < 1e-6
    assert "overlap" not in kinds(fixed.drop(columns="_src_row"), cfg)

def test_overlap_above_max_flagged():
    g, cfg = _ov(_cfg(trim_overlaps_below_area=10))
    fixed, log = repair.repair(g, cfg)
    r = log[log.check == "overlap"].iloc[0]
    assert r.action == "flag_only" and not r.applied
    assert fixed.geometry.iloc[1].equals(box(98, 0, 110, 10))

def test_contained_parcel_cut_from_larger_not_trimmed():
    big = dict(PID="BIG", ACRES=4.0, geometry=box(100, 0, 140, 40)); small = dict(PID="SM", ACRES=0.5, geometry=box(110, 10, 120, 20))
    g = mk(base() + [big, small])
    iss = checks.inspect(g, CFG)
    c = iss[iss.check == "contained_parcel"]
    assert len(c) == 1 and c.iloc[0].feature_id == "BIG" and "cut smaller from larger" in c.iloc[0].message
    assert (iss.check == "overlap").sum() == 0
    cfg = CFG.model_copy(deep=True); cfg.repair.trim_overlaps_below_area = 1e9   # even aggressive trimming must not delete SM
    fixed, log = repair.repair(g, cfg)
    assert fixed.geometry.iloc[3].area == 100 and fixed.geometry.iloc[2].area == 1600     # default: propose only
    cfg.repair.cut_contained_from_container = True
    fixed, log = repair.repair(g, cfg)
    assert fixed.geometry.iloc[3].area == 100 and fixed.geometry.iloc[2].area == 1500
    assert log[log.check == "contained_parcel"].iloc[0].action == "cut_contained"
