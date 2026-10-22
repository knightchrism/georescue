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
                hausdorff_ft=trav_poly.boundary.hausdorff_distance(gis_poly.boundary),
                sym_diff_sqft=trav_poly.symmetric_difference(gis_poly).area,
                iou=trav_poly.intersection(gis_poly).area / unary_union([trav_poly, gis_poly]).area)


# ---------------- full metes-and-bounds with curves ----------------
BRG = r"([NS])\s*(\d{1,3})\s*[°*]\s*(\d{1,2})\s*['’‘`]\s*(\d{1,2}(?:\.\d+)?)\s*[\"”“]?\s*([EW])"
CONCAVE = {"NORTH": 0, "NORTHEAST": 45, "EAST": 90, "SOUTHEAST": 135, "SOUTH": 180, "SOUTHWEST": 225, "WEST": 270, "NORTHWEST": 315}

def _az(m):
    return azimuth_full(m[0], m[1], m[2], m[3], m[4])

def clean_ocr(t):
    t = re.sub(r"\s+", " ", t)
    t = t.replace("°°", "°").replace("’", "'").replace("‘", "'")
    t = re.sub(r"(\d)°(\d\d)°(\d\d)", r"\1°\2'\3", t)    # 87°58°04 -> 87°58'04
    t = re.sub(r"(\d)'(\d\d)°", r"\1'\2\"", t)
    return t

def parse_full(text):
    """Split on 'thence'; each segment -> line call (bearing + distance) or curve call.
    Curve data (radius, central angle, chord bearing/length, concavity) may be stated in the
    preceding segment ('said point being on a curve ...') and applied to the next 'along the arc' call.
    Returns (commencement_calls, figure_calls)."""
    t = clean_ocr(text)
    segs = re.split(r"(?i);?\s*thence\s+", t)
    calls, pending, tie, seen_pob = [], None, [], False
    for s in segs:
        cur = None
        if re.search(r"(?i)curve", s) and re.search(r"(?i)radius", s):
            R = float(re.search(r"(?i)radius of ([\d.,]+)", s).group(1).replace(",", ""))
            ca = re.search(r"(?i)central angle of (\d+)\s*[°*]\s*(\d+)\s*['\"]?\s*(\d+)", s)
            delta = float(ca.group(1)) + float(ca.group(2)) / 60 + float(ca.group(3)) / 3600 if ca else None
            cb = re.search(r"(?i)chord having a bearing of\s*" + BRG, s)
            cl = re.search(r"(?i)chord length of ([\d.]+)", s)
            cc = re.search(r"(?i)concave (?:to|90) the (\w+)", s)
            pending = dict(R=R, delta=delta, chord_az=_az(cb.groups()) if cb else None,
                           chord=float(cl.group(1)) if cl else None,
                           concave=CONCAVE.get(cc.group(1).upper()) if cc else None)
        arc = re.search(r"(?i)arc (?:distance )?(?:of )?([\d.]+)\s*f", s)
        if arc and re.search(r"(?i)along", s) and pending:
            cur = dict(kind="arc", dist=float(arc.group(1)), **pending)
            if not re.search(r"(?i)still along a curve", s): pending = None
            # 'still along a curve having radius .. central angle' -> continuing curve without chord
            if re.search(r"(?i)continue.*still along a curve", s):
                ca = re.search(r"(?i)central angle of (\d+)\s*[°*]\s*(\d+)\s*['\"]?\s*(\d+)", s)
                cur.update(delta=float(ca.group(1)) + float(ca.group(2)) / 60 + float(ca.group(3)) / 3600,
                           chord_az=None, chord=None, continuing=True)
        else:
            m = re.search(BRG + r".{0,70}?([\d,]+\.\d+)\s*fe", s)
            if m and not re.search(r"(?i)chord having", s[:m.start() + 1]):
                cur = dict(kind="line", az=_az(m.groups()[:5]), dist=float(m.group(6).replace(",", "")))
        if cur:
            (calls if seen_pob else tie).append(cur)
        if re.search(r"(?i)point of beginning", s) and not seen_pob: seen_pob = True
    return tie, calls

def walk(calls, start, n=48):
    """Walk calls; arcs use chord bearing/length when given, else continue tangent from previous arc.
    Turn direction from concavity side relative to travel. Returns points, per-call vertex indices."""
    pts, x, y = [start], *start
    last_tan = None; idx = []
    for c in calls:
        i0 = len(pts) - 1
        if c["kind"] == "line":
            r = math.radians(c["az"]); x += c["dist"] * math.sin(r); y += c["dist"] * math.cos(r); pts.append((x, y))
            last_tan = c["az"]
        else:
            R, L = c["R"], c["dist"]; d = L / R
            if c.get("chord_az") is not None:
                ca = c["chord_az"]
                side = ((c["concave"] - ca) + 360) % 360 if c.get("concave") is not None else 90
                sign = 1 if side < 180 else -1   # concave to the right of travel -> turning right (+az)
                a0 = math.radians(ca) - sign * d / 2
            else:
                sign = c.get("sign", last_sign); a0 = math.radians(last_tan)
            for k in range(n):
                ang = a0 + sign * d * (k + 0.5) / n
                x += L / n * math.sin(ang); y += L / n * math.cos(ang); pts.append((x, y))
            last_tan = math.degrees(a0 + sign * d); last_sign = sign
        idx.append((i0, len(pts) - 1))
    return pts, idx
