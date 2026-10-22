"""Tie 02272-052 parent tract traverse to BLM CadNSDI PLSS: POB = SE cor Sec 23 T3S R16E.
Source: https://gis.blm.gov/arcgis/rest/services/Cadastral/BLM_Natl_PLSS_CadNSDI/MapServer/2"""
import json, math, numpy as np, geopandas as gpd
from shapely.geometry import shape, Point
from shapely.ops import unary_union
from shapely.affinity import translate
from verify.cogo import parse_calls, traverse, compare
from verify.run_columbia import LEGAL, a, b, b_trim, exc, parent, OUT

d = json.load(open("data/real/plss_sections_T3S_R16E_17E.geojson"))
S = {f["properties"]["FRSTDIVID"]: shape(f["geometry"]) for f in d["features"]}
s23, s24, s25, s26 = (S[f"FL290030S0160E0SN{n}0"] for n in (23, 24, 25, 26))
corner = s23.intersection(s24).intersection(s25).intersection(s26)
corner = corner if corner.geom_type == "Point" else corner.centroid
# bearing of S line of Sec 23 westward from the corner
w = (2543516.0, 443194.0)
az_w = math.degrees(math.atan2(w[0] - corner.x, w[1] - corner.y)) % 360
import sys
MODE = sys.argv[1] if len(sys.argv) > 1 else "B"
calls_all = parse_calls(LEGAL)
if MODE == "A":   # POB = SE cor Sec 23, all legs part of figure (does not close, see A results)
    calls, start, ov0 = calls_all, (corner.x, corner.y), {0: az_w, 1: az_w}
else:             # B: commence SE cor Sec 23, W 273.58 (tie) to POB
    tie = calls_all[0]["dist"]; r = math.radians(az_w)
    start = (corner.x + tie * math.sin(r), corner.y + tie * math.cos(r))
    calls, ov0 = calls_all[1:], {0: az_w}
best = None
k = len(ov0)
for R in np.linspace(150, 2500, 236):
    for caz in np.linspace(120, 180, 121):
        o = dict(ov0); o.update({k: caz, k+1: 91.94, k+2: 359.99, k+3: 308.19, k+4: 178.5})
        t = traverse(calls, arc_radius=R, az_override=o)
        if best is None or t["misclosure_ft"] < best[0]["misclosure_ft"]: best = (t, R, caz)
t, R, caz = best
poly = translate(t["polygon"], start[0], start[1])
nearest_gis_vertex = min(parent.exterior.coords, key=lambda p: math.dist(p, start))
# arc comparison: GIS easement east line (02305-005 east edge) vs COGO arc
arc_pts = [Point(p).buffer(0) for p in list(poly.exterior.coords)[3:35]]
arc_line = gpd.GeoSeries([poly.exterior]).iloc[0]
res = dict(mode=MODE, sec_corner=(corner.x, corner.y), pob=start, sec23_south_line_az_w=az_w,
           pob_to_nearest_gis_vertex_ft=math.dist(nearest_gis_vertex, start),
           easement_point_from_legal=(t["points"][k][0] + start[0], t["points"][k][1] + start[1]),
           fitted_radius_ft=R, fitted_chord_az=caz, misclosure_ft=t["misclosure_ft"], precision=t["precision"],
           vs_parent=compare(poly, parent), vs_residual=compare(poly.difference(exc), a),
           )
from shapely.geometry import LineString
arc = LineString(t["points"][k:k+33]); arc = translate(arc, start[0], start[1])
res["cogo_arc_hausdorff_to_052_boundary_ft"] = arc.hausdorff_distance(a.boundary)
res["cogo_arc_hausdorff_to_02305_boundary_ft"] = arc.hausdorff_distance(b.boundary)
json.dump(res, open(OUT / f"plss_tie_results_{MODE}.json", "w"), indent=2, default=float)
print(json.dumps(res, indent=2, default=float))
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize=(9, 9))
gpd.GeoSeries([s23, s24, s25, s26]).boundary.plot(ax=ax, color="k", lw=0.6)
gpd.GeoSeries([parent]).boundary.plot(ax=ax, color="gray", ls=":", label="parent GIS (052+054)")
gpd.GeoSeries([a]).boundary.plot(ax=ax, color="blue", label="02272-052 GIS")
gpd.GeoSeries([b]).boundary.plot(ax=ax, color="red", label="02305-005 GIS")
gpd.GeoSeries([poly]).boundary.plot(ax=ax, color="green", lw=2, label="COGO tied to SE cor Sec 23")
ax.plot(corner.x, corner.y, "k*", ms=14, label="SE cor Sec 23 (BLM CadNSDI)")
x0, y0, x1, y1 = parent.buffer(150).bounds; ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
ax.set_aspect("equal"); ax.legend(fontsize=7)
fig.savefig(OUT / f"cogo_plss_tie_{MODE}.png", dpi=110, bbox_inches="tight")
