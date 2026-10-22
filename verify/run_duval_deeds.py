"""Duval deed-vs-GIS check: OCR'd deeds in data/deeds/duval/ocr -> COGO traverses (verify/cogo.py),
best-fit placed on GIS (no PLSS/monument tie available), overlay PNGs + verdicts JSON."""
import json, math, re, itertools
import numpy as np, geopandas as gpd, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from shapely.geometry import Polygon, box
from shapely import affinity
from verify.cogo import parse_full, walk, compare, azimuth_full
from pathlib import Path
OCR = Path("data/deeds/duval/ocr"); OUT = Path("out/duval/verify")
IDS = ["001542 0010", "001531 5300", "013030 0010", "013030 0300", "004307 0320", "004307 0230", "001542 0100"]

def words_to_symbols(t):
    t = re.sub(r"\s+", " ", t)
    return re.sub(r"(?i)\b(north|south)\s+(\d{1,3})\s+degrees,?\s+(\d{1,2})\s+minutes,?\s+(\d{1,2})\s+seconds,?\s+(east|west)",
                  lambda m: f"{m[1][0].upper()} {m[2]}°{m[3]}'{m[4]}\" {m[5][0].upper()}", t)

def tolerant_calls(text):
    """Line-only parser for OCR'd deeds: per 'thence' segment, a bearing (N/North/SOUT*, ° or ' separators,
    OCR fixes) plus the nearest 'X feet' within the segment; 'continue along said line' reuses the last bearing.
    Returns (tie, figure) split at the first 'point of beginning'."""
    t = re.sub(r"\s+", " ", text).replace("°(0", "°10").replace("(AGE", "PAGE")
    B = r"\b(N|S|NORTH|SOUT\w*)\s*(\d{1,3})\s*°\s*(\d{1,2})\s*['°’]\s*(\d{1,2})\s*[\"”]?\s*(E|W|EAST|WEST)\b"
    tie, fig, seen, last = [], [], bool(re.match(r"(?i)begin", t)), None
    for seg in re.split(r"(?i)thence\s+", t)[1:]:
        m = re.search(B, seg, re.I); d = re.search(r"([\d,]+\.\d+)\s*feet", seg, re.I)
        if d:
            if m:
                az = azimuth_full(m[1][0].upper(), int(m[2]), int(m[3]), float(m[4]), m[5][0].upper())
            elif re.search(r"(?i)continue", seg) and last is not None: az = last
            else: az = None
            if az is not None:
                (fig if seen else tie).append(dict(kind="line", az=az, dist=float(d[1].replace(",", "")))); last = az
        if re.search(r"(?i)point of beginning", seg): seen = True
    return tie, fig

def legal(name, start, end):
    t = words_to_symbols((OCR / f"{name}.txt").read_text()); i = t.lower().find(start.lower())
    return re.sub(r"(?i)\bfeet\b", "feet", t[i:t.lower().find(end.lower(), i) + len(end)])  # cogo regex expects lowercase "fe"

def load():
    g = gpd.read_file("data/real/duval_parcels.geojson", where="RE IN (%s)" % ",".join(f"'{i}'" for i in IDS))
    return {r.RE: r.geometry for r in g.to_crs(2236).itertuples()}

def fit(rec, target, span=150, step=10, rots=np.arange(-1.5, 1.51, 0.25)):
    """Grid-search rotation + translation maximizing IoU of record polygon with target GIS polygon."""
    best = (-1, None)
    c0 = rec.centroid; ct = target.centroid
    for r in rots:
        p = affinity.rotate(rec, r, origin=c0)
        base = affinity.translate(p, ct.x - c0.x, ct.y - c0.y)
        for dx, dy in itertools.product(range(-span, span + 1, step), repeat=2):
            q = affinity.translate(base, dx, dy); iou = q.intersection(target).area / q.union(target).area
            if iou > best[0]: best = (iou, q, dict(rot_deg=float(r), dx=dx, dy=dy))
    return best

def closure(calls, pts):
    mis = math.dist(pts[0], pts[-1]); per = sum(c["dist"] for c in calls)
    return dict(n_calls=len(calls), perimeter_ft=round(per, 2), misclosure_ft=round(mis, 3),
                precision=f"1:{int(per / mis)}" if mis > 1e-6 else "exact")

def plot(fn, title, layers, rec_layers):
    fig, ax = plt.subplots(figsize=(8, 8))
    for (lbl, g, col) in layers: gpd.GeoSeries([g]).plot(ax=ax, facecolor=col, edgecolor="k", alpha=.35, lw=.8); ax.plot([], [], color=col, lw=6, alpha=.5, label=lbl)
    for (lbl, g, col) in rec_layers: gpd.GeoSeries([g]).boundary.plot(ax=ax, color=col, lw=2.2, ls="--"); ax.plot([], [], color=col, ls="--", label=lbl)
    ax.set_title(title, fontsize=9); ax.legend(fontsize=7, loc="best"); ax.set_aspect("equal"); ax.set_xlabel("EPSG:2236 ft")
    fig.savefig(OUT / fn, dpi=130, bbox_inches="tight"); plt.close(fig); return str(OUT / fn)

G = load(); A = lambda g: round(g.area / 43560, 3); res = {}

# ---- Case 1: OwnerA 001542 0010 vs OwnerB 001531 5300 (ORB 19870-841) ----
c19 = sum(tolerant_calls(legal("ORB_19870_841", "Begin at the Southwest corner", "containing 7.83 acres")), [])  # "Begin at" => all calls are figure calls
p19, _ = walk(c19, (0.0, 0.0)); r19 = Polygon(p19)
t17, c17 = tolerant_calls(legal("ORB_17966_196", "FOR A POINT OF REFERENCE", "CONTAINING 3.41 ACRES"))
sieg, owner_b = G["001542 0010"], G["001531 5300"]
iou, f19, prm = fit(r19, sieg)
iou_b, f19b, prm_b = fit(r19, sieg.difference(owner_b))  # hypothesis: OwnerA GIS = record + OwnerB
res["owner_a_001542_0010_vs_owner_b_001531_5300"] = dict(
    deed="ORB 19870-841 (WD 2021, OwnerC -> OwnerA)", has_bearings=True,
    closure=closure(c19, p19), acres_record_cogo=A(r19), acres_record_stated=7.83, acres_gis_owner_a=A(sieg),
    acres_gis_owner_b=A(owner_b), fit=dict(iou=round(iou, 3), **prm, note="no monument tie; rotation+translation best fit to GIS"),
    vs_gis=compare(f19, sieg),
    fit_to_gis_minus_owner_b=dict(iou=round(iou_b, 3), **prm_b, vs=compare(f19b, sieg.difference(owner_b)),
                               owner_b_inside_record_fraction=round(owner_b.intersection(f19b).area / owner_b.area, 3)), gis_excess_outside_record_ac=A(sieg.difference(f19)),
    owner_b_inside_record_fraction=round(owner_b.intersection(f19).area / owner_b.area, 3),
    owner_b_inside_gis_owner_a_fraction=round(owner_b.intersection(sieg).area / owner_b.area, 3),
    gis_owner_a_minus_owner_b_ac=A(sieg.difference(owner_b)),
    parent_17966_196=dict(calls_parsed=len(c17), closure=closure(c17, walk(c17, (0, 0))[0]), acres_cogo=A(Polygon(walk(c17, (0, 0))[0])), stated_acres=3.41, note="3.41 ac piece of Tract 8 (folio 001542-0100); OCR of bearings partly garbled; superseded by 19870-841 'All of Tract 8'"),
)
plot_s = plot("deed_owner_a_overlay.png", f"OwnerA 001542 0010: GIS {A(sieg)} ac vs record COGO {A(r19)} ac (best-fit IoU {iou:.2f})",
              [("GIS OwnerA 001542 0010", sieg, "tab:blue"), ("GIS OwnerB 001531 5300", owner_b, "tab:orange")],
              [("Record ORB 19870-841 (fit to GIS)", f19, "red"), ("Record (fit to GIS minus OwnerB)", f19b, "black")])

# ---- Case 2: Patriot Ridge 013030 0010 vs OwnerD 013030 0300 (ORB 13639-288 / 20536-187) ----
tie, cl = parse_full(legal("ORB_13639_288", "COMMENCE AT THE INTERSECTION", "TO THE POINT OF BEGINNING. 25 FOOT"))
# figure calls: N75W 240, S65W 20 to lake, [meander 344 ft, no bearing], N42E 120 to POB
pob = (0.0, 0.0); pts, _ = walk(cl[:2], pob)
last = cl[2]; r = math.radians(last["az"]); C = (pob[0] - last["dist"] * math.sin(r), pob[1] - last["dist"] * math.cos(r))
rl = Polygon(pts + [C]); chord = math.dist(pts[-1], C)
pat, lock = G["013030 0010"], G["013030 0300"]
iou2, fl, prm2 = fit(rl, lock)
res["patriot_013030_0010_vs_owner_d_013030_0300"] = dict(
    deeds=dict(owner_d="ORB 13639-288 (WD 2006, metes & bounds w/ lake meander)", patriot="ORB 20536-187 (WD 2022, plat ref Tracts 12-13 Blk 1 PB 5-93)"),
    patriot_has_bearings=False, owner_d_has_bearings="partial (one 344 ft meander call has no bearing)",
    patriot_exception_text="Less and except ... Official Records Book 13639, Page 288 ...",
    owner_d_tie_calls=len(tie), owner_d_figure_calls_with_bearing=len(cl),
    meander_chord_ft=round(chord, 1), meander_record_ft=344.0,
    acres_record_cogo_chorded=A(rl), acres_gis_owner_d=A(lock), acres_gis_patriot=A(pat),
    fit=dict(iou=round(iou2, 3), **prm2), vs_gis=compare(fl, lock),
    owner_d_inside_patriot_gis_fraction=round(lock.intersection(pat).area / lock.area, 3))
plot_p = plot("deed_patriot_owner_d_overlay.png", f"Patriot 013030 0010 ({A(pat)} ac) vs OwnerD 013030 0300 ({A(lock)} ac); record (lake chorded) {A(rl)} ac",
              [("GIS Patriot Ridge 013030 0010", pat, "tab:green"), ("GIS OwnerD 013030 0300", lock, "tab:purple")],
              [("Record ORB 13639-288 (fit, meander as chord)", fl, "red")])

# ---- Case 3: City 004307 0320 vs OwnerF 004307 0230 (ORB 13934-1037) ----
city, star = G["004307 0320"], G["004307 0230"]
res["city_004307_0320_vs_owner_f_004307_0230"] = dict(
    deed="ORB 13934-1037 (Tax Deed 2007, TD# 99-1006, to City of Jacksonville)", has_bearings=False,
    legal="07-1S-26E DINSMORE FARMS S/D PT PVT RD LYING E OF O/R 4690-669, 4886-64, 5528-1903, LYING SOUTH OF O/R 4321-590, 4886-64, 5554-2032, 6460-2252 RECD O/R 2384-383",
    acres_stated=None, acres_gis_city=A(city), acres_gis_owner_f=A(star),
    owner_f_inside_city_fraction=round(star.intersection(city).area / star.area, 3),
    owner_f_deed="not supplied")
plot_c = plot("deed_city_owner_f_overlay.png", f"City 004307 0320 ({A(city)} ac, tax deed: 'PT PVT RD', no bearings) vs OwnerF 004307 0230 ({A(star)} ac)",
              [("GIS City 004307 0320", city, "tab:gray"), ("GIS OwnerF 004307 0230", star, "tab:red")], [])
res["_pngs"] = [plot_s, plot_p, plot_c]
# traverse export for the web (EPSG:2236 vertices in call order, best-fit placement)
def _brg(az):
    az %= 360; q = ("N", "E") if az < 90 else ("S", "E") if az < 180 else ("S", "W") if az < 270 else ("N", "W")
    a = {"NE": az, "SE": 180 - az, "SW": az - 180, "NW": 360 - az}[q[0] + q[1]]
    d = int(a); m = int((a - d) * 60); sec = round(((a - d) * 60 - m) * 60)
    if sec == 60: m, sec = m + 1, 0
    return f"{q[0]} {d}°{m:02d}'{sec:02d}\" {q[1]}"
mc = [dict(label=f"{_brg(c['az'])}  {c['dist']:.2f} ft") for c in c19]
lc = [dict(label=f"{_brg(cl[0]['az'])}  240.00 ft"), dict(label=f"{_brg(cl[1]['az'])}  20.00 ft ± to lake"),
      dict(label=f"lake meander 344.00 ft ± (no bearing; drawn as {chord:.1f} ft chord)"), dict(label=f"{_brg(cl[2]['az'])}  120.00 ft to POB")]
trav = {"001542 0010": dict(orb="ORB 19870-841", vertices=list(f19b.exterior.coords), calls=mc,
                            closure=res["owner_a_001542_0010_vs_owner_b_001531_5300"]["closure"], acres=A(r19)),
        "013030 0300": dict(orb="ORB 13639-288", vertices=list(fl.exterior.coords), calls=lc,
                            closure=dict(note="closes by construction: meander call has no bearing"), acres=A(rl))}
json.dump(trav, open(OUT / "deed_traverses_2236.json", "w"), indent=1, default=float)
json.dump(res, open(OUT / "deed_cogo_duval.json", "w"), indent=2, default=float)
print(json.dumps(res, indent=1, default=float))
