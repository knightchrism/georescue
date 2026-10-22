"""Evidence-based check of the 02305-005 / 02272-052 overlap (Columbia Co. FL).
Legal desc of 23-3S-16-02272-052 from https://search.ccpafl.com/parcel/02272052163S23 ."""
import json, math, pathlib
import numpy as np, geopandas as gpd
from shapely.ops import unary_union
from shapely.affinity import translate
from verify.cogo import parse_calls, traverse, compare

OUT = pathlib.Path("out/columbia/verify"); OUT.mkdir(parents=True, exist_ok=True)
LEGAL = ("BEG SE COR, RUN W 273.58 FT CONT W 81.06 FT TO EAST R/W OF A 60 FT EASEMENT, SE ALONG ARC OF CURVE "
         "297.63 FT, E 386.30 FT, N 534.40 FT TO S R/W CR-250, NW ALONG R/W 569.78 FT, S 596.21 FT TO POB, "
         "EX 2.36 AC DESC ORB 960-85.")
src = gpd.read_file("data/real/columbia_parcels.geojson").to_crs(2238)
cor = gpd.read_file("out/columbia/corrected.gpkg").to_crs(2238)
g = lambda df, p: df[df.PARCELNO == p].geometry.iloc[0]
A, B, EXC = "23-3S-16-02272-052", "26-3S-16-02305-005", "24-3S-16-02272-054"
a, b, b_trim, exc = g(src, A), g(src, B), g(cor, B), g(src, EXC)
parent = unary_union([a, exc])  # 4.64 + 2.36 = 7.00 ac ("FOR 7 AC" in WD 960/87)

def main():
    calls = parse_calls(LEGAL)
    res = {"calls": [c["raw"] for c in calls]}
    r0 = traverse(calls)
    res["cardinal_only"] = dict(misclosure_ft=r0["misclosure_ft"], precision=r0["precision"], acres=r0["polygon"].area / 43560)

    # Interpretation: leg 0 (W 273.58) is a commencement tie; POB of the closed figure is after it.
    # Bearings are not in the record (abbreviated PA legal) -> substitute GIS-measured bearings (circular!).
    body = calls[1:]
    gis_az = {0: 267.75, 2: 91.94, 3: 359.99, 4: 308.19, 5: 178.5}   # from GIS edges of parent
    def run(R, chord_az):
        o = dict(gis_az); o[1] = chord_az
        return traverse(body, arc_radius=R, arc_sweep_sign=1, az_override=o)
    best = None
    for R in np.linspace(200, 1200, 201):
        for caz in np.linspace(140, 170, 61):
            t = run(R, caz)
            if best is None or t["misclosure_ft"] < best[0]["misclosure_ft"]: best = (t, R, caz)
    t, R, caz = best
    # place: POB = NW-most-west corner of residual on the north side (start of W leg) from GIS
    pob = min(a.exterior.coords, key=lambda p: math.dist(p, (2544518, 443249)))
    poly = translate(t["polygon"], pob[0], pob[1])
    res["fitted"] = dict(radius_ft=R, chord_az=caz, misclosure_ft=t["misclosure_ft"], precision=t["precision"],
                         note="bearings borrowed from GIS; closure is NOT independent evidence")
    res["vs_parent_gis"] = compare(poly, parent)
    res["vs_residual_gis"] = compare(poly.difference(exc), a)
    # overlap analysis: which side of the arc does the deed put the strip?
    ov = a.intersection(b)
    res["overlap_sqft"] = ov.area
    res["overlap_inside_cogo_parcel_sqft"] = ov.intersection(poly).area
    res["acres"] = dict(A_gis=a.area / 43560, A_deed=4.64, parent_gis=parent.area / 43560, parent_deed=7.0,
                        exc_gis=exc.area / 43560, exc_deed=2.36, B_gis=b.area / 43560, B_trim=b_trim.area / 43560, B_pa=0.23)
    json.dump(res, open(OUT / "cogo_results.json", "w"), indent=2, default=float)
    print(json.dumps(res, indent=2, default=float))

    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(14, 7))
    for axx, zoom in zip(ax, [None, ov.buffer(40).bounds]):
        gpd.GeoSeries([parent]).boundary.plot(ax=axx, color="gray", ls=":")
        gpd.GeoSeries([a]).boundary.plot(ax=axx, color="blue", label="02272-052 GIS")
        gpd.GeoSeries([b]).boundary.plot(ax=axx, color="red", label="02305-005 GIS")
        gpd.GeoSeries([b_trim]).boundary.plot(ax=axx, color="orange", ls="--", label="02305-005 trimmed")
        gpd.GeoSeries([poly]).boundary.plot(ax=axx, color="green", lw=2, label="COGO (fitted)")
        gpd.GeoSeries([ov]).plot(ax=axx, color="magenta")
        if zoom: axx.set_xlim(zoom[0], zoom[2]); axx.set_ylim(zoom[1], zoom[3])
        axx.set_aspect("equal"); axx.legend(fontsize=7)
    fig.savefig(OUT / "cogo_vs_gis.png", dpi=110, bbox_inches="tight")


if __name__ == "__main__":
    main()