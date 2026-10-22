"""Prototype COGO: parse (abbreviated or full) metes-and-bounds legal descriptions
into a traverse polygon, report closure, compare with GIS polygons."""
import math, re
from shapely.geometry import Polygon, LineString
from shapely.ops import unary_union

CARD = {"N": 0, "NE": 45, "E": 90, "SE": 135, "S": 180, "SW": 225, "W": 270, "NW": 315}
# full form: N 12°34'56" E 123.45 FT
FULL = re.compile(r"([NS])\s*(\d+)\s*(?:°|DEG)\s*(\d+)?\s*['’]?\s*(\d+(?:\.\d+)?)?\s*[\"”]?\s*([EW])\s*,?\s*(\d+(?:\.\d+)?)\s*FT", re.I)
ABBR = re.compile(r"\b(?:RUN\s+|CONT\s+)?(NE|NW|SE|SW|N|S|E|W)\b(?:\s+ALONG\s+(ARC OF CURVE|R/W))?\s+(\d+(?:\.\d+)?)\s*FT", re.I)

def azimuth_full(ns, d, m, s, ew):
    a = float(d) + float(m or 0) / 60 + float(s or 0) / 3600
    return {("N","E"): a, ("S","E"): 180 - a, ("S","W"): 180 + a, ("N","W"): 360 - a}[(ns.upper(), ew.upper())]

def parse_calls(text):
    """Returns list of dict(az, dist, kind, exact). exact=False for cardinal-only calls."""
    t = text.upper()
    t = t.split(" EX ")[0]  # exceptions handled separately
    calls = []
    for m in FULL.finditer(t):
        calls.append(dict(az=azimuth_full(*m.groups()[:5]), dist=float(m.group(6)), kind="line", exact=True, pos=m.start()))
    if not calls:
        for m in ABBR.finditer(t):
            kind = "arc" if m.group(2) and "ARC" in m.group(2) else "line"
            calls.append(dict(az=CARD[m.group(1)], dist=float(m.group(3)), kind=kind, exact=False, pos=m.start(), raw=m.group(0)))
    return sorted(calls, key=lambda c: c["pos"])

def traverse(calls, start=(0.0, 0.0), arc_radius=None, arc_sweep_sign=1, az_override=None):
    """Walk calls. arc with arc_radius -> sampled arc whose chord bearing = call az.
    az_override: {index: azimuth} to substitute fitted bearings for cardinal-only calls."""
    pts = [start]; x, y = start
    for i, c in enumerate(calls):
        az = (az_override or {}).get(i, c["az"])
        if c["kind"] == "arc" and arc_radius:
            L, R = c["dist"], arc_radius; delta = L / R
            chord = 2 * R * math.sin(delta / 2)
            a0 = math.radians(az) - arc_sweep_sign * delta / 2
            for k in range(1, 17):
                f = k / 16; ang = a0 + arc_sweep_sign * delta * f
                # point along arc: integrate tangents
            # sample by stepping tangents
            n = 32; step = L / n; xx, yy = x, y
            for k in range(n):
                ang = a0 + arc_sweep_sign * delta * (k + 0.5) / n
                xx += step * math.sin(ang); yy += step * math.cos(ang); pts.append((xx, yy))
            x, y = xx, yy
        else:
            r = math.radians(az); x += c["dist"] * math.sin(r); y += c["dist"] * math.cos(r); pts.append((x, y))
    perim = sum(c["dist"] for c in calls)
    mis = math.dist(pts[0], pts[-1])
    return dict(points=pts, misclosure_ft=mis, perimeter_ft=perim,
                precision=f"1:{int(perim / mis) if mis > 1e-9 else 'inf'}",
                polygon=Polygon(pts))

def compare(trav_poly, gis_poly):
    return dict(trav_acres=trav_poly.area / 43560, gis_acres=gis_poly.area / 43560,
                hausdorff_ft=trav_poly.exterior.hausdorff_distance(gis_poly.exterior),
                sym_diff_sqft=trav_poly.symmetric_difference(gis_poly).area,
                iou=trav_poly.intersection(gis_poly).area / unary_union([trav_poly, gis_poly]).area)
