"""Propose & apply repairs to a COPY. Every change is logged; nothing is silent."""
from __future__ import annotations
import numpy as np
import pandas as pd
import geopandas as gpd
import shapely
from pyproj import CRS
from .config import Config
from . import checks

LOG_COLS = ["feature_id", "row", "check", "action", "before", "after", "reason", "post_valid", "applied", "before_area", "after_area"]


def _w(g, n=200):
    if g is None:
        return None
    s = shapely.to_wkt(g, rounding_precision=6)
    return s if len(s) <= n else s[:n] + "..."


def _polygonal(g):
    if g.geom_type in ("Polygon", "MultiPolygon"):
        return g
    parts = [p for p in shapely.get_parts(g) if p.geom_type in ("Polygon", "MultiPolygon")]
    return shapely.union_all(parts) if parts else shapely.Polygon()


def repair(gdf: gpd.GeoDataFrame, cfg: Config, issues: pd.DataFrame | None = None):
    r = cfg.repair
    if issues is None:
        issues = checks.inspect(gdf, cfg)
    out = gdf.copy()
    log = []
    fid = lambda i: checks._fid(gdf, cfg, i)
    if out.crs is None and cfg.expected_crs:
        log.append(dict(feature_id="*", row=None, check="crs_missing", action="assign_crs", before=None,
                        after=cfg.expected_crs, reason="dataset CRS missing; config.expected_crs assumed",
                        post_valid=True, applied=r.assign_crs_if_missing))
        if r.assign_crs_if_missing:
            out = out.set_crs(cfg.expected_crs)
    for _, iss in issues.iterrows():
        i = None if pd.isna(iss["row"]) else int(iss["row"])
        c = iss["check"]
        if c == "geometry_invalid":
            before = out.geometry.iloc[i]
            after = _polygonal(shapely.make_valid(before, method="structure"))
            valid = bool(after.is_valid and not after.is_empty)
            ok = r.fix_invalid and valid
            if ok:
                out.loc[i, out.geometry.name] = after
            log.append(dict(feature_id=fid(i), row=i, check=c, action="make_valid", before=_w(before), after=_w(after),
                            reason=iss["message"], post_valid=valid, applied=ok))
        elif c in ("geometry_empty", "geometry_missing"):
            log.append(dict(feature_id=fid(i), row=i, check=c, action="drop_feature" if r.drop_empty_geometries else "flag_only",
                            before=None, after=None, reason=iss["message"], post_valid=None, applied=r.drop_empty_geometries))
        elif c == "attribute_wrong_type" and r.coerce_types:
            field = iss["message"].split("=")[0]
            rule = cfg.fields[field]
            v = out.at[i, field]
            try:
                nv = {"int": lambda x: int(float(x)), "float": float}.get(rule.type, lambda x: x)(v)
                ok = rule.type in ("int", "float")
            except (ValueError, TypeError):
                nv, ok = v, False
            if ok:
                out[field] = out[field].astype(object); out.at[i, field] = nv
            log.append(dict(feature_id=fid(i), row=i, check=c, action="coerce_type" if ok else "flag_only",
                            before=repr(v), after=repr(nv), reason=iss["message"], post_valid=ok, applied=ok))
        elif c == "duplicate_geometry" and r.drop_exact_duplicates:
            pass  # handled below
        elif c == "overlap" and r.trim_overlaps_below_area > 0:
            area = float(iss["metric"])
            other = int(iss["message"].split("other_row=")[1])
            if area > r.trim_overlaps_below_area:
                log.append(dict(feature_id=fid(i), row=i, check=c, action="flag_only", before=None, after=None,
                                reason=iss["message"] + f" (above trim max {r.trim_overlaps_below_area})", post_valid=None, applied=False))
                continue
            w = checks.working(out, cfg)
            gi, go = w.geometry.iloc[i], w.geometry.iloc[other]
            # trim from the smaller parcel (or the issue row if trim_overlap_from == "row")
            t, keep = (i, go) if r.trim_overlap_from == "row" or gi.area <= go.area else (other, gi)
            before = w.geometry.iloc[t]
            after = _polygonal(shapely.make_valid(before.difference(keep)))
            valid = bool(after.is_valid and not after.is_empty)
            if valid:
                out.loc[t, out.geometry.name] = gpd.GeoSeries([after], crs=w.crs).to_crs(out.crs).iloc[0]
            log.append(dict(feature_id=fid(t), row=t, check=c, action="trim_overlap", before=_w(before), after=_w(after),
                            reason=iss["message"] + f"; trimmed from smaller parcel {fid(t)}, kept {fid(other if t == i else i)}",
                            post_valid=valid, applied=valid, before_area=round(before.area, 3), after_area=round(after.area, 3)))
        else:
            log.append(dict(feature_id=iss["feature_id"], row=i, check=c, action="flag_only", before=None, after=None,
                            reason=iss["message"], post_valid=None, applied=False))
    drop = set()
    if r.drop_empty_geometries:
        drop |= {int(x) for x in issues.loc[issues.check.isin(["geometry_empty", "geometry_missing"]), "row"]}
    if r.drop_exact_duplicates:
        d = issues[issues.check == "duplicate_geometry"]
        attrs = [c for c in gdf.columns if c != gdf.geometry.name]
        dups = gdf.loc[sorted({int(x) for x in d.row})]
        keyed = dups[attrs].astype(str).agg("|".join, axis=1) + dups.geometry.normalize().to_wkb().astype(str)
        for i in keyed[keyed.duplicated(keep="first")].index:
            drop.add(int(i))
            log.append(dict(feature_id=fid(i), row=i, check="duplicate_geometry", action="drop_feature", before=None, after=None,
                            reason="exact duplicate (geometry + attributes)", post_valid=True, applied=True))
    out["_src_row"] = np.arange(len(gdf))
    out = out.drop(index=sorted(drop))
    return out, pd.DataFrame(log, columns=LOG_COLS)


def _changed(a, b) -> bool:
    """Value change, including text->number coercion; numpy vs python scalars are not a change."""
    na, nb = isinstance(a, (int, float, np.number)) and not isinstance(a, bool), isinstance(b, (int, float, np.number)) and not isinstance(b, bool)
    if na and nb:
        return float(a) != float(b)
    if na != nb:
        return True
    return str(a) != str(b)


def diff(original: gpd.GeoDataFrame, corrected: gpd.GeoDataFrame) -> pd.DataFrame:
    rows = []
    kept = set(corrected["_src_row"])
    for i in range(len(original)):
        if i not in kept:
            rows.append(dict(row=i, change="removed", detail=""))
    oc = original.to_crs(corrected.crs) if original.crs and corrected.crs and original.crs != corrected.crs else original
    for _, f in corrected.iterrows():
        i = int(f["_src_row"]); o = oc.iloc[i]
        go, gn = o.geometry, f.geometry
        if not ((go is None and gn is None) or (go is not None and gn is not None and go.equals_exact(gn, 0))):
            da = (gn.area if gn is not None else 0) - (go.area if go is not None else 0)
            rows.append(dict(row=i, change="geometry", detail=f"area delta {da:.6g}"))
        for c in original.columns:
            if c == original.geometry.name:
                continue
            a, b = o[c], f[c]
            if not (pd.isna(a) and pd.isna(b)) and _changed(a, b):
                rows.append(dict(row=i, change="attribute", detail=f"{c}: {a!r} -> {b!r}"))
    return pd.DataFrame(rows, columns=["row", "change", "detail"])
