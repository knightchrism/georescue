"""Issue detection. Every issue: feature row, feature id, check, severity, message."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import math
import numpy as np
import pandas as pd
import geopandas as gpd
import shapely
from shapely.validation import explain_validity
from pyproj import CRS
from .config import Config


@dataclass
class Issue:
    row: int | None
    feature_id: str
    check: str
    severity: str
    message: str
    geometry_wkt: str | None = None
    other_row: int | None = None
    metric: float | None = None


def _fid(gdf, cfg, i):
    if cfg.id_field and cfg.id_field in gdf.columns:
        return str(gdf.iloc[i][cfg.id_field])
    return f"row:{i}"


def working(gdf: gpd.GeoDataFrame, cfg: Config) -> gpd.GeoDataFrame:
    wc = cfg.working_crs or cfg.expected_crs
    if gdf.crs is None or wc is None:
        return gdf
    c = CRS.from_user_input(wc)
    return gdf if gdf.crs == c else gdf.to_crs(c)


def check_crs(gdf, cfg):
    if gdf.crs is None:
        return [Issue(None, "*", "crs_missing", "error", "dataset has no CRS")]
    if cfg.expected_crs and CRS.from_user_input(cfg.expected_crs) != gdf.crs:
        return [Issue(None, "*", "crs_unexpected", "warning", f"CRS {gdf.crs.to_string()} != expected {cfg.expected_crs}")]
    return []


def check_geometry(gdf, cfg):
    out = []
    g = gdf.geometry.values
    missing = pd.isna(g)
    for i in np.where(missing)[0]:
        out.append(Issue(int(i), _fid(gdf, cfg, i), "geometry_missing", "error", "null geometry"))
    present = ~missing
    empty = np.zeros(len(g), bool); empty[present] = shapely.is_empty(g[present])
    for i in np.where(empty)[0]:
        out.append(Issue(int(i), _fid(gdf, cfg, i), "geometry_empty", "error", "empty geometry"))
    ok = present & ~empty
    invalid = np.zeros(len(g), bool); invalid[ok] = ~shapely.is_valid(g[ok])
    for i in np.where(invalid)[0]:
        out.append(Issue(int(i), _fid(gdf, cfg, i), "geometry_invalid", "error", explain_validity(g[i])))
    return out


def check_duplicate_ids(gdf, cfg):
    if not cfg.id_field:
        return []
    if cfg.id_field not in gdf.columns:
        return [Issue(None, "*", "id_field_missing", "error", f"id field {cfg.id_field!r} not in dataset")]
    s = gdf[cfg.id_field]
    dup = s.duplicated(keep=False) & s.notna() & (s.astype(str).str.strip() != "")
    return [Issue(int(i), str(s.iloc[i]), "duplicate_id", "error", f"id {s.iloc[i]!r} appears {int((s == s.iloc[i]).sum())}x")
            for i in np.where(dup)[0]]


def check_duplicate_geometries(gdf, cfg):
    g = gdf.geometry.values
    ok = ~pd.isna(g)
    keys = pd.Series([None] * len(g), dtype=object)
    keys[ok] = shapely.to_wkb(shapely.normalize(g[ok]), hex=True)
    dup = keys.duplicated(keep=False) & keys.notna()
    out = []
    for key, grp in keys[dup].groupby(keys[dup]):
        rows = list(grp.index)
        for i in rows:
            out.append(Issue(int(i), _fid(gdf, cfg, i), "duplicate_geometry", "warning",
                             f"identical geometry to rows {[r for r in rows if r != i][:5]}"))
    return out


def _type_ok(v, t):
    if t == "str":
        return True
    try:
        if t == "int":
            f = float(v); return f == int(f)
        if t == "float":
            float(v); return True
        if t == "bool":
            return str(v).lower() in {"true", "false", "0", "1", "y", "n", "yes", "no"}
        if t == "date":
            pd.to_datetime(v); return True
    except (ValueError, TypeError):
        return False
    return True


def check_attributes(gdf, cfg):
    out = []
    for name, rule in cfg.fields.items():
        if name not in gdf.columns:
            out.append(Issue(None, "*", "attribute_field_missing", "error", f"required field {name!r} absent"))
            continue
        col = gdf[name]
        for i, v in enumerate(col):
            empty = v is None or (isinstance(v, float) and math.isnan(v)) or (
                isinstance(v, str) and v.strip() == "" and not rule.allow_empty_string)
            if empty:
                if rule.required:
                    out.append(Issue(i, _fid(gdf, cfg, i), "attribute_missing", "error", f"{name} is empty"))
            elif not _type_ok(v, rule.type):
                out.append(Issue(i, _fid(gdf, cfg, i), "attribute_wrong_type", "error", f"{name}={v!r} is not {rule.type}"))
            elif rule.type in ("int", "float") and isinstance(v, str):
                out.append(Issue(i, _fid(gdf, cfg, i), "attribute_wrong_type", "warning", f"{name}={v!r} stored as text, expected {rule.type}"))
    return out


def check_bounds(gdf, cfg):
    if not cfg.bounds or gdf.crs is None:
        return []
    b = cfg.bounds
    g = gdf.to_crs(b.crs).geometry if CRS.from_user_input(b.crs) != gdf.crs else gdf.geometry
    box = shapely.box(b.minx, b.miny, b.maxx, b.maxy)
    out = []
    for i, geom in enumerate(g.values):
        if geom is None or geom.is_empty:
            continue
        geom = shapely.box(*geom.bounds)
        if not box.contains(geom):
            out.append(Issue(i, _fid(gdf, cfg, i), "out_of_bounds", "error" if not box.intersects(geom) else "warning",
                             f"feature bounds {tuple(round(x, 5) for x in geom.bounds)} outside expected extent"))
    return out


def check_topology(gdf, cfg):
    t = cfg.topology
    if not t.enabled:
        return []
    w = working(gdf, cfg)
    g = w.geometry.values
    ok = ~pd.isna(g)
    ok[ok] = ~shapely.is_empty(g[ok])
    idx = np.where(ok)[0]
    geoms = shapely.make_valid(g[idx])
    out = []
    # slivers
    area = shapely.area(geoms); per = shapely.length(geoms)
    comp = np.where(per > 0, 4 * np.pi * area / np.maximum(per, 1e-12) ** 2, 0)
    for k in np.where((area < t.sliver_max_area) | (comp < t.sliver_max_compactness))[0]:
        i = int(idx[k])
        out.append(Issue(i, _fid(gdf, cfg, i), "sliver_polygon", "warning", f"area={area[k]:.2f}, compactness={comp[k]:.3f}", metric=float(area[k])))
    # overlaps: bbox candidates from STRtree, then a cheap DE-9IM interior test,
    # and only then the expensive intersection (adjacent parcels share edges only).
    tree = shapely.STRtree(geoms)
    a, b = tree.query(geoms)  # bbox-only candidate pairs
    m = a < b
    a, b = a[m], b[m]
    if len(a):
        inter_mask = shapely.relate_pattern(geoms[a], geoms[b], "T********")
        a, b = a[inter_mask], b[inter_mask]
        same = shapely.equals(geoms[a], geoms[b])  # identical pairs are reported as duplicate_geometry
        a, b = a[~same], b[~same]
        inter = shapely.intersection(geoms[a], geoms[b])
        ia = shapely.area(inter)
        for k in np.where(ia > t.overlap_min_area)[0]:
            i, j = int(idx[a[k]]), int(idx[b[k]])
            out.append(Issue(j, _fid(gdf, cfg, j), "overlap", "error",
                             f"overlaps row {i} ({_fid(gdf, cfg, i)}) by {ia[k]:.2f} units^2|other_row={i}",
                             shapely.to_wkt(inter[k], rounding_precision=3), other_row=i, metric=float(ia[k])))
    # gaps: small interior holes in the union of the fabric
    if len(geoms):
        u = shapely.union_all(shapely.buffer(geoms, 0))
        polys = shapely.get_parts(u)
        for p in polys:
            for ring in p.interiors:
                h = shapely.Polygon(ring)
                if h.area <= t.gap_max_area:
                    out.append(Issue(None, "*", "gap", "warning", f"gap of {h.area:.2f} units^2 at {h.representative_point().wkt}",
                                     shapely.to_wkt(h, rounding_precision=3), metric=float(h.area)))
    return out


ALL_CHECKS = [check_crs, check_geometry, check_duplicate_ids, check_duplicate_geometries,
              check_attributes, check_bounds, check_topology]


def inspect(gdf: gpd.GeoDataFrame, cfg: Config) -> pd.DataFrame:
    issues = []
    for c in ALL_CHECKS:
        issues += c(gdf, cfg)
    return pd.DataFrame([asdict(x) for x in issues], columns=list(Issue.__dataclass_fields__))


def summarize(gdf, issues: pd.DataFrame) -> dict:
    return {"features": int(len(gdf)), "crs": gdf.crs.to_string() if gdf.crs else None,
            "geometry_types": gdf.geometry.geom_type.value_counts(dropna=False).to_dict(),
            "issues_total": int(len(issues)),
            "issues_by_check": issues["check"].value_counts().to_dict() if len(issues) else {},
            "features_with_issues": int(issues["row"].dropna().nunique()) if len(issues) else 0}
