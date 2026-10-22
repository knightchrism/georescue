"""Rebuild 02272-052 parent tract from OCR'd ORB 923/1637 Exhibit A, tied to BLM PLSS
NE cor Sec 26 (= SE cor Sec 23), basis-of-bearing rotated to the PLSS section line."""
import json, math, re, geopandas as gpd
from shapely.geometry import Polygon, LineString, Point
from verify.cogo import parse_full, walk, compare
from verify.run_columbia import a, b, b_trim, exc, parent, OUT
from verify.run_plss import corner, az_w

t = open("data/deeds/ocr/ORB_923_1637.txt").read()
i = t.find("Commence"); legal = t[i:t.find("Columbia County, Florida.", i)]
tie, calls = parse_full(legal)
rot = az_w - tie[0]["az"]            # deed basis -> PLSS/grid
for c in tie + calls:
    for k in ("az", "chord_az"):
        if c.get(k) is not None: c[k] += rot
tp, _ = walk(tie, (corner.x, corner.y)); pob = tp[-1]
pts, idx = walk(calls, pob)
mis = math.dist(pts[0], pts[-1]); perim = sum(c["dist"] for c in calls)
poly = Polygon(pts)
arc = LineString(pts[idx[1][0]:idx[1][1] + 1])          # shared arc: E line of 60 ft easement
ov = a.intersection(b)
def side_dist(geom_line, ref):  # mean / max distance from points of the record arc within overlap zone
    zone = ov.buffer(15)
    sample = [arc.interpolate(f, normalized=True) for f in [k / 400 for k in range(401)]]
    sample = [p for p in sample if zone.contains(p)]
    ds = [p.distance(ref) for p in sample]
    return dict(n=len(ds), mean_ft=sum(ds) / len(ds) if ds else None, max_ft=max(ds) if ds else None)
# the two candidate GIS lines in the overlap: 052's chorded west edge, 02305-005's fine east edge
line052 = a.boundary.intersection(ov.buffer(15)); line305 = b.boundary.intersection(ov.buffer(15))
res = dict(rotation_deg=rot, pob=pob, pob_to_gis_vertex_ft=min(math.dist(pob, p) for p in parent.exterior.coords),
           misclosure_ft=mis, precision=f"1:{int(perim / mis)}", perimeter_ft=perim,
           acres_record=poly.area / 43560, acres_deed_total=7.0,
           vs_parent=compare(poly, parent), vs_residual=compare(poly.difference(exc), a),
           residual_acres_record_minus_gis_exc=poly.difference(exc).area / 43560,
           arc_to_052_line=side_dist(arc, line052), arc_to_02305_line=side_dist(arc, line305),
           arc_hausdorff_whole_to_02305_boundary=arc.hausdorff_distance(b.boundary),
           overlap_area_inside_record_parcel_sqft=ov.intersection(poly).area, overlap_sqft=ov.area,
           record_parcel_overlap_with_02305_sqft=poly.intersection(b).area,
           record_parcel_overlap_with_02305_trimmed_sqft=poly.intersection(b_trim).area)
json.dump(res, open(OUT / "deed_cogo_results.json", "w"), indent=2, default=float)
print(json.dumps(res, indent=2, default=float))
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
fig, ax = plt.subplots(1, 2, figsize=(15, 8))
for axx, bb in zip(ax, [parent.buffer(120).bounds, ov.buffer(30).bounds]):
    gpd.GeoSeries([a]).boundary.plot(ax=axx, color="blue", label="02272-052 GIS")
    gpd.GeoSeries([b]).boundary.plot(ax=axx, color="red", label="02305-005 GIS")
    gpd.GeoSeries([b_trim]).boundary.plot(ax=axx, color="orange", ls="--", label="02305-005 trimmed")
    gpd.GeoSeries([exc]).boundary.plot(ax=axx, color="gray", ls=":", label="02272-054 GIS (exception)")
    gpd.GeoSeries([poly]).boundary.plot(ax=axx, color="green", lw=2, label="Record (ORB 923/1637) COGO")
    gpd.GeoSeries([ov]).plot(ax=axx, color="magenta", alpha=.6)
    axx.plot(corner.x, corner.y, "k*", ms=12); axx.set_xlim(bb[0], bb[2]); axx.set_ylim(bb[1], bb[3])
    axx.set_aspect("equal"); axx.legend(fontsize=7)
fig.savefig(OUT / "deed_cogo_vs_gis.png", dpi=110, bbox_inches="tight")

# --- rigid best-fit (translation only) of the record figure to GIS parent: removes PLSS-corner datum error
from shapely.affinity import translate as _tr
import numpy as np
best = max(((poly.intersection(_tr(parent, -dx, -dy)).area, dx, dy) for dx in np.arange(-60, 61, 2) for dy in np.arange(-60, 61, 2)))
_, dx, dy = best
for dd in [1, .25]:
    best = max(((poly.intersection(_tr(parent, -(dx + i), -(dy + j))).area, dx + i, dy + j) for i in np.arange(-2*dd, 2*dd + 1e-9, dd/2) for j in np.arange(-2*dd, 2*dd + 1e-9, dd/2)))
    _, dx, dy = best
pf, arcf = _tr(poly, dx, dy), _tr(arc, dx, dy)
zone = ov.buffer(15)
samp = [arcf.interpolate(k / 2000, normalized=True) for k in range(2001)]
samp = [p for p in samp if zone.contains(p)]
d052 = [p.distance(line052) for p in samp]; d305 = [p.distance(line305) for p in samp]
fit = dict(shift_ft=(float(dx), float(dy), float(math.hypot(dx, dy))), vs_parent=compare(pf, parent),
           vs_residual=compare(pf.difference(exc), a), residual_acres=pf.difference(exc).area / 43560,
           arc_hausdorff_to_02305_east_line=arcf.hausdorff_distance(LineString(b.exterior.coords[:41])),
           overlap_zone_samples=len(samp),
           arc_to_052_line_mean_max=(float(np.mean(d052)), float(np.max(d052))),
           arc_to_02305_line_mean_max=(float(np.mean(d305)), float(np.max(d305))),
           overlap_sqft_inside_record_parcel=ov.intersection(pf).area,
           record_parcel_vs_02305_orig_overlap_sqft=pf.intersection(b).area,
           record_parcel_vs_02305_trim_overlap_sqft=pf.intersection(b_trim).area)
res["translation_fit"] = fit
json.dump(res, open(OUT / "deed_cogo_results.json", "w"), indent=2, default=float)
print(json.dumps(fit, indent=2, default=float))
fig, ax = plt.subplots(figsize=(8, 8)); bb = ov.buffer(30).bounds
for g_, c_, l_ in [(a, "blue", "02272-052 GIS"), (b, "red", "02305-005 GIS"), (b_trim, "orange", "02305-005 trimmed"), (pf, "green", "Record COGO, best-fit shift")]:
    gpd.GeoSeries([g_]).boundary.plot(ax=ax, color=c_, label=l_, lw=2 if c_ == "green" else 1)
gpd.GeoSeries([ov]).plot(ax=ax, color="magenta", alpha=.6)
ax.set_xlim(bb[0], bb[2]); ax.set_ylim(bb[1], bb[3]); ax.set_aspect("equal"); ax.legend(fontsize=7)
ax.set_title(f"Record arc (R=296.58, Δ=57°29'58\") after {math.hypot(dx,dy):.1f} ft shift")
fig.savefig(OUT / "deed_arc_overlap_zoom.png", dpi=120, bbox_inches="tight")
