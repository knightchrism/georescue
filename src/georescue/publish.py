"""`georescue publish`: static dashboard (HTML + MapLibre GL + JSON) from out/latest -> site/ (GitHub Pages ready).
No server, no API keys. Basemap: CARTO Dark Matter vector style (© CARTO, © OpenStreetMap contributors)."""
from __future__ import annotations
import html, json, shutil
from pathlib import Path
import pandas as pd

ML_CSS = "https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css"
ML_JS = "https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"
STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
ATTR = '© <a href="https://carto.com/attributions">CARTO</a> © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
SITE_URL = "https://knightchrism.github.io/georescue/"
E = html.escape
COLORS = {"contained_parcel": "#ff4d6d", "overlap": "#ff9f1c", "geometry_invalid": "#b388ff", "gap": "#4cc9f0",
          "sliver_polygon": "#80ffdb", "attribute_missing": "#8d99ae"}
ORDER = list(COLORS)

LOGO = '<img class=logo src="{up}assets/logo-mark-flat.svg" alt="" width=30 height=30>'

CSS = """:root{--bg:#f5f6f8;--fg:#1d2430;--mut:#5d6878;--card:#fff;--line:#e2e5ea;--acc:#ff4d6d;--acc2:#4cc9f0;--hdr:#111827}
[data-theme=dark]{--bg:#0d1117;--fg:#e6edf3;--mut:#8b96a5;--card:#161b22;--line:#2a313b;--hdr:#010409}
*{box-sizing:border-box}body{font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:0;color:var(--fg);background:var(--bg);line-height:1.5}
a{color:var(--acc2)}header{background:var(--hdr);color:#fff;padding:10px 24px;display:flex;align-items:center;gap:18px;flex-wrap:wrap;position:sticky;top:0;z-index:10}
.brand{display:flex;align-items:center;gap:8px;font-weight:800;font-size:19px;letter-spacing:.3px;color:#fff;text-decoration:none}@font-face{font-family:'Exo 2';src:url(fonts/Exo2-VariableFont_wght.ttf) format('truetype');font-weight:100 900;font-display:swap}.brand .wm{font-family:'Exo 2',Rajdhani,system-ui,sans-serif;font-weight:600;letter-spacing:.5px;background:linear-gradient(90deg,#f4f8ff,#9fe9ff);-webkit-background-clip:text;background-clip:text;color:transparent}.logo{filter:drop-shadow(0 0 4px #2ee6ff88)}
.logo{width:28px;height:28px;color:#fff}nav{display:flex;gap:16px;flex:1;flex-wrap:wrap}nav a{color:#c9d4e0;text-decoration:none;font-size:14px}nav a:hover{color:#fff}
#tt{background:none;border:1px solid #3a4452;color:#fff;border-radius:16px;padding:3px 10px;cursor:pointer}
main{padding:20px 24px;max-width:1240px;margin:auto}h2{margin:28px 0 10px;font-size:20px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin:14px 0}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px}.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 14px}
.kpi b{display:block;font-size:24px;font-variant-numeric:tabular-nums}.kpi span{font-size:12px;color:var(--mut)}
.hero{display:grid;grid-template-columns:1.1fr 1fr;gap:22px;align-items:start}@media(max-width:860px){.hero{grid-template-columns:1fr}}
.eyebrow{text-transform:uppercase;font-size:12px;letter-spacing:1.5px;color:var(--acc);font-weight:700}.hero h1{font-size:34px;line-height:1.15;margin:6px 0 14px}
.big{display:flex;gap:14px;flex-wrap:wrap}.big div{flex:1;min-width:120px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px}
.big b{font-size:34px;display:block;font-variant-numeric:tabular-nums}.big small{color:var(--mut)}.gis b{color:#ff9f1c}.deed b{color:#38d39f}.REDACTED b{color:var(--acc)}
.counters{display:flex;gap:26px;flex-wrap:wrap;margin:18px 0}.counters b{font-size:30px;color:var(--acc2);font-variant-numeric:tabular-nums}.counters span{display:block;font-size:12px;color:var(--mut)}
.steps{counter-reset:s;list-style:none;padding:0;margin:0}.steps li{counter-increment:s;position:relative;padding:4px 0 12px 40px;border-left:2px solid var(--line);margin-left:14px}
.steps li:before{content:counter(s);position:absolute;left:-15px;top:0;width:28px;height:28px;border-radius:50%;background:var(--acc);color:#fff;font-weight:700;display:grid;place-items:center;font-size:13px}
.steps li:last-child{border-color:transparent}.steps b{display:block}
.ba{position:relative;width:100%;aspect-ratio:1/1;border-radius:12px;overflow:hidden;background:#0b1320;border:1px solid var(--line);user-select:none}
.ba svg{position:absolute;inset:0;width:100%;height:100%}.ba .after{clip-path:inset(0 0 0 15%)}.ba input{position:absolute;inset:auto 0 8px 0;width:92%;margin:auto;left:4%}
.ba .bar{position:absolute;top:0;bottom:0;left:15%;width:2px;background:#fff;box-shadow:0 0 8px #fff;pointer-events:none}
.ba .lab{position:absolute;top:8px;font-size:12px;background:#000a;color:#fff;padding:2px 8px;border-radius:8px}.ba .l{left:8px}.ba .r{right:8px}
#map,.tmap{height:520px;border-radius:12px;border:1px solid var(--line)}.legend{display:flex;gap:12px;flex-wrap:wrap;font-size:12px;margin:8px 0}.legend i{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:4px;vertical-align:-1px}
.maplibregl-popup-content{background:#161b22;color:#e6edf3;border-radius:10px;box-shadow:0 6px 24px #0008}.maplibregl-popup-tip{border-top-color:#161b22!important}
.pop b{font-size:14px}.pop a{display:inline-block;margin-top:6px;background:var(--acc);color:#fff;padding:3px 10px;border-radius:8px;text-decoration:none}
table{border-collapse:collapse;width:100%;font-size:13px}th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}th{background:var(--card);position:sticky;top:0}
.tbl{max-height:520px;overflow:auto;border:1px solid var(--line);border-radius:10px;background:var(--card)}input[type=search],select{padding:6px 8px;margin:0 6px 8px 0;background:var(--card);color:var(--fg);border:1px solid var(--line);border-radius:8px}
.badge{padding:2px 8px;border-radius:10px;font-size:11px;color:#fff;font-weight:600}.high{background:#2e9e64}.medium{background:#c18a1d}.low{background:#b23a48}
img.fig{max-width:100%;border-radius:10px;border:1px solid var(--line);background:#fff}
.tctl{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:8px 0}.btn{background:var(--acc);border:0;color:#fff;padding:7px 16px;border-radius:20px;font-weight:700;cursor:pointer}
.call{font-family:ui-monospace,Menlo,monospace;background:var(--card);border:1px solid var(--line);padding:4px 10px;border-radius:8px}.closure{color:#38d39f;font-weight:700}
footer{font-size:12px;color:var(--mut);padding:18px 24px;border-top:1px solid var(--line);max-width:1240px;margin:auto}code{background:var(--line);padding:1px 5px;border-radius:4px}
@media(max-width:600px){main{padding:12px}.hero h1{font-size:26px}.big b{font-size:26px}#map,.tmap{height:380px}header{flex-wrap:wrap;gap:6px}header nav{display:flex;flex-wrap:wrap;gap:4px 14px;order:3;flex:1 0 100%}.brand .wm{font-size:17px}header nav a{display:inline;padding:0}}"""

THEME_JS = """<script>(function(){const k='gr-theme',d=document.documentElement,s=localStorage.getItem(k)||(matchMedia('(prefers-color-scheme: light)').matches?'light':'dark');d.dataset.theme=s;
addEventListener('DOMContentLoaded',()=>{const b=document.getElementById('tt');if(b){b.textContent=s=='dark'?'☀ light':'☾ dark';b.onclick=()=>{const n=d.dataset.theme=='dark'?'light':'dark';d.dataset.theme=n;localStorage.setItem(k,n);b.textContent=n=='dark'?'☀ light':'☾ dark'}}})})()</script>"""

FOOT = ("Data: City of Jacksonville / Duval Property Appraiser parcels (maps.coj.net CityBiz/Parcels); Duval Property Appraiser "
        "(paopropertysearch.coj.net); Duval Clerk of Courts Official Records (or.duvalclerk.com). Basemap " + ATTR + ". "
        "Map library: MapLibre GL JS (BSD-3-Clause). Deed outlines are COGO traverses best-fit to GIS, not surveys; "
        "all fixes except invalid-geometry repair are proposals for review.")


def page(title, body, depth=0, head="", desc="Evidence-based parcel overlap resolution"):
    up = "../" * depth
    return f"""<!doctype html><html lang=en data-theme=dark><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>{E(title)} · GeoRescue</title><meta name=description content="{E(desc)}">
<meta property=og:title content="GeoRescue · {E(title)}"><meta property=og:description content="{E(desc)}"><meta property=og:image content="{SITE_URL}assets/og.png">
<meta property=og:type content=website><meta name=twitter:card content=summary_large_image><link rel=icon href="{up}assets/favicon.svg" type="image/svg+xml"><link rel=icon href="{up}assets/favicon.ico" sizes=any><link rel=apple-touch-icon href="{up}assets/apple-touch-icon.png"><meta property=og:image:width content=1200><meta property=og:image:height content=630>
<link rel=stylesheet href="{up}assets/style.css">{THEME_JS}{head}</head><body>
<header><a class=brand href="{up}index.html">{LOGO.format(up=up)}<span class=wm>GeoRescue</span></a><nav><a href="{up}index.html">Dashboard</a><a href="{up}index.html#map-sec">Map</a><a href="{up}cases.html">Case files</a><a href="{up}history.html">Run history</a></nav><button id=tt>☀ light</button></header>
<main>{body}</main><footer>{FOOT}</footer></body></html>"""


# ---------- geometry helpers ----------
def _to_wgs(coords):
    from pyproj import Transformer
    t = Transformer.from_crs(2236, 4326, always_xy=True)
    return [list(map(lambda v: round(v, 7), t.transform(x, y))) for x, y in coords]


def _svg_paths(geoms, bounds, size=500, pad=0.06):
    x0, y0, x1, y1 = bounds; s = max(x1 - x0, y1 - y0) * (1 + 2 * pad); cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    f = lambda x, y: (round((x - cx + s / 2) / s * size, 1), round((cy + s / 2 - y) / s * size, 1))
    out = []
    for g in geoms:
        polys = getattr(g, "geoms", [g]); d = ""
        for p in polys:
            pts = [f(*c) for c in p.exterior.coords]; d += "M" + "L".join(f"{a},{b}" for a, b in pts) + "Z"
        out.append(d)
    return out


def _deed_index(vdir: Path):
    out = {}
    vf, cf = vdir / "deed_verdicts.json", vdir / "deed_cogo_duval.json"
    if not vf.exists(): return out
    v = json.loads(vf.read_text()); c = json.loads(cf.read_text()) if cf.exists() else {}
    keys = {"REDACTED_001542_0010_vs_REDACTED_001531_5300": ("001542 0010", "001531 5300", "deed_REDACTED_overlay.png", "001542 0010"),
            "patriot_013030_0010_vs_REDACTED_013030_0300": ("013030 0010", "013030 0300", "deed_patriot_REDACTED_overlay.png", "013030 0300"),
            "city_004307_0320_vs_REDACTED_004307_0230": ("004307 0320", "004307 0230", "deed_city_REDACTED_overlay.png", None)}
    for k, (a, b, png, tr) in keys.items():
        if k in v: out[(a, b)] = dict(verdict=v[k], cogo=c.get(k, {}), png=png, traverse_parcel=tr)
    return out


def _primary(checks):
    cs = [c for c in (checks or "").split(",") if c]
    return next((c for c in ORDER if c in cs), cs[0] if cs else "other")


def _og_image(dst: Path, n_parcels, n_cases):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return False
    im = Image.new("RGB", (1200, 630), "#0d1117"); d = ImageDraw.Draw(im)
    for i in range(0, 1200, 40): d.line([(i, 0), (i - 300, 630)], fill="#131a23", width=1)
    d.polygon([(780, 170), (1000, 110), (1120, 190), (1110, 470), (900, 530), (770, 450)], outline="#ff9f1c", width=6)
    d.polygon([(800, 300), (1090, 270), (1085, 460), (900, 510), (790, 440)], outline="#38d39f", width=6)
    d.ellipse([(925, 205), (955, 235)], fill="#ff4d6d")
    def font(sz, bold=True):
        for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
            try: return ImageFont.truetype(p, sz)
            except OSError: pass
        return ImageFont.load_default()
    d.text((70, 150), "Geo", font=font(96), fill="#ffffff"); d.text((70 + d.textlength("Geo", font=font(96)), 150), "Rescue", font=font(96), fill="#ff4d6d")
    d.text((74, 280), "Parcel overlaps resolved from deeds,", font=font(36, False), fill="#c9d4e0")
    d.text((74, 326), "not heuristics.", font=font(36, False), fill="#c9d4e0")
    d.text((74, 430), f"{n_parcels:,} parcels checked · {n_cases} overlap case files", font=font(28), fill="#4cc9f0")
    d.text((74, 540), "Duval County, FL · static demo", font=font(22, False), fill="#8b96a5")
    im.save(dst); return True


def publish(latest="out/latest", site="site", runs="out/runs", include_coj_imagery=False) -> dict:
    import geopandas as gpd
    L, S = Path(latest), Path(site)
    if S.exists(): shutil.rmtree(S)
    for d in ("data", "assets", "cases", "img"): (S / d).mkdir(parents=True, exist_ok=True)
    (S / "assets" / "style.css").write_text(CSS); (S / ".nojekyll").write_text("")
    B = Path(__file__).resolve().parents[2] / "brand"
    for f in ("logo-mark.svg", "logo-mark-flat.svg", "logo-horizontal.svg", "logo-stacked.svg", "favicon.svg", "favicon.ico",
              "apple-touch-icon.png", "logo-mark-512.png", "logo-mark-192.png", "logo-mark-32.png", "og.png"):
        if (B / f).exists(): shutil.copy2(B / f, S / "assets" / f)
    fnt = Path("/usr/share/fonts/truetype/sand-box/google/Exo 2/Exo2-VariableFont_wght.ttf")
    if fnt.exists(): (S / "assets" / "fonts").mkdir(exist_ok=True); shutil.copy2(fnt, S / "assets" / "fonts" / fnt.name)
    man = json.loads((L / "manifest.json").read_text())
    summ = json.loads((L / "summary.json").read_text()) if (L / "summary.json").exists() else {}
    iss = pd.read_csv(L / "issues.csv") if (L / "issues.csv").exists() else pd.DataFrame(columns=["feature_id", "check", "severity", "message"])
    cols = [c for c in ["feature_id", "check", "severity", "message", "metric"] if c in iss.columns]
    recs = iss[cols].astype(object).where(iss[cols].notna(), "").to_dict("records")
    for r in recs: r["message"] = str(r["message"]).split("|")[0][:240]
    (S / "data" / "issues.json").write_text(json.dumps(recs))
    shutil.copy2(L / "manifest.json", S / "data" / "manifest.json")
    verdicts = json.loads((L / "verdicts.json").read_text()) if (L / "verdicts.json").exists() else []
    deeds = _deed_index(L / "verify")
    imgsrc = L / "verify" if include_coj_imagery else L / "verify" / "v1"
    case_of = {}
    for v in verdicts:
        for p in v["parcels"]: case_of.setdefault(p, v["case_id"])

    # ---- flagged parcels (small web copy) + heat points, bounds ----
    fg = None; bounds = [-82.06, 30.10, -81.32, 30.60]
    if (L / "flagged.geojson").exists():
        fg = gpd.read_file(L / "flagged.geojson")
        if fg.crs is None: fg = fg.set_crs(4326)
        fg["geometry"] = fg.geometry.simplify(1e-5, preserve_topology=True)
        fg["kind"] = fg["checks"].map(_primary); fg["case"] = fg["fid"].map(lambda f: case_of.get(f, ""))
        fg.to_file(S / "data" / "flagged.geojson", driver="GeoJSON", COORDINATE_PRECISION=6)
        pts = fg[["fid", "kind"]].copy(); pts["geometry"] = fg.geometry.representative_point()
        gpd.GeoDataFrame(pts, geometry="geometry", crs=4326).to_file(S / "data" / "flagged_pts.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)
        if len(fg): bounds = [round(v, 5) for v in fg.total_bounds]

    by = summ.get("issues_by_check") or iss["check"].value_counts().to_dict()
    n_par = int(summ.get("features", 0) or 0); n_ov = sum(1 for v in verdicts); n_deed = len(deeds)
    kpis = "".join(f"<div class=kpi><b data-n={n}>{n:,}</b><span><i style='display:inline-block;width:8px;height:8px;border-radius:2px;background:{COLORS.get(k, '#888')}'></i> {E(k)}</span></div>" for k, n in sorted(by.items(), key=lambda x: -x[1]))
    if not (S / "assets" / "og.png").exists(): _og_image(S / "assets" / "og.png", n_par, n_ov)

    # ---- hero: REDACTED vs REDACTED ----
    hero = ""
    sb = deeds.get(("001542 0010", "001531 5300"))
    trav_path = L / "verify" / "deed_traverses_2236.json"
    for src in [Path("out/duval/verify/deed_traverses_2236.json")]:  # pull from the run's verify output if missing/stale
        if src.exists() and (not trav_path.exists() or src.stat().st_mtime > trav_path.stat().st_mtime):
            trav_path.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src, trav_path)
    travs = json.loads(trav_path.read_text()) if trav_path.exists() else {}
    if sb and fg is not None and "001542 0010" in travs:
        c = sb["cogo"]; g2236 = fg.set_index("fid").to_crs(2236).geometry
        sieg, REDACTED = g2236.get("001542 0010"), g2236.get("001531 5300")
        from shapely.geometry import Polygon
        rec = Polygon(travs["001542 0010"]["vertices"])
        if sieg is not None and REDACTED is not None:
            bnd = sieg.union(REDACTED).bounds
            ps, pb, pr = _svg_paths([sieg, REDACTED, rec], bnd)
            grid = "".join(f"<line x1={i} y1=0 x2={i} y2=500 stroke='#ffffff08'/><line x1=0 y1={i} x2=500 y2={i} stroke='#ffffff08'/>" for i in range(0, 501, 50))
            before = f"<svg viewBox='0 0 500 500'>{grid}<path d='{ps}' fill='#ff9f1c33' stroke='#ff9f1c' stroke-width=2.5/><path d='{pb}' fill='#ff4d6d55' stroke='#ff4d6d' stroke-width=2 stroke-dasharray='5 4'/></svg>"
            after = f"<svg viewBox='0 0 500 500' class=after style='background:#0b1320'>{grid}<defs><pattern id=hx width=8 height=8 patternUnits=userSpaceOnUse patternTransform='rotate(45)'><line x1=0 y1=0 x2=0 y2=8 stroke='#ff4d6d88' stroke-width=2/></pattern></defs><path d='{ps}' fill='none' stroke='#ff9f1c66' stroke-width=1 stroke-dasharray='3 4'/><path d='{pb}' fill='url(#hx)' stroke='#ff4d6d' stroke-width=1.5 stroke-dasharray='5 4'/><path d='{pr}' fill='#38d39f40' stroke='#38d39f' stroke-width=3.5/><text x=490 y=52 text-anchor=end fill='#cbd5e1' font-size=12 font-family=sans-serif>green = deed tract · hatched = REDACTED excluded</text></svg>"
            cl = travs["001542 0010"]["closure"]
            case_id = case_of.get("001542 0010", "")
            hero = f"""<section class=hero><div><div class=eyebrow>Featured case · Duval County, FL</div>
<h1>The county map gave REDACTED 2.6 acres the deed never conveyed.</h1>
<div class=big><div class=gis><small>GIS polygon</small><b data-n={c.get('acres_gis_REDACTED', 10.59)} data-d=2>{c.get('acres_gis_REDACTED', 10.59)}</b><small>acres · 001542 0010</small></div>
<div class=deed><small>Deed traverse</small><b data-n={c.get('acres_record_cogo', 7.96):.2f} data-d=2>{c.get('acres_record_cogo', 7.96):.2f}</b><small>acres · ORB 19870-841</small></div>
<div class=REDACTED><small>REDACTED lot inside</small><b data-n={c.get('acres_gis_REDACTED', 2.48):.2f} data-d=2>{c.get('acres_gis_REDACTED', 2.48):.2f}</b><small>acres · 001531 5300</small></div></div>
<div class=counters><div><b data-n={n_par}>{n_par:,}</b><span>parcels checked</span></div><div><b data-n={n_ov}>{n_ov}</b><span>overlaps found</span></div><div><b data-n={n_deed}>{n_deed}</b><span>deed-checked</span></div></div>
<div class=card><h3 style=margin-top:0>How we proved it</h3><ol class=steps>
<li><b>Flagged</b>REDACTED's 2.48 ac lot sits 100% inside REDACTED's polygon — a <code>contained_parcel</code>, not an edge sliver.</li>
<li><b>Appraiser mismatch</b>REDACTED's legal says 7.83 ac; GIS says 10.59 ac. REDACTED is Lot 3 of a 2003 plat.</li>
<li><b>Deed pulled</b>Official Records 19870-841 (2021 warranty deed), OCR'd and parsed call by call.</li>
<li><b>Traverse closes {E(cl.get('precision', ''))}</b>{cl.get('n_calls', '')} calls, misclosure {cl.get('misclosure_ft', '')} ft. Fits GIS-minus-REDACTED at IoU {c.get('fit_to_gis_minus_REDACTED', {}).get('iou', '')}; 0% of REDACTED inside the deed.</li>
<li><b>Verdict proposed for review</b>Cut REDACTED from REDACTED (cut smaller from larger) — high confidence, not auto-applied. <a href="cases/{case_id}.html">Open the case file →</a></li></ol></div></div>
<div><div class=ba id=ba>{before}{after}<div class=bar></div><span class='lab l'>Before · GIS</span><span class='lab r'>After · deed</span><input type=range min=0 max=100 value=15 aria-label="before/after"></div>
<p style="font-size:12px;color:var(--mut)">Drag the handle to compare. Before: orange = county GIS polygon for REDACTED, red dashed = REDACTED lot inside it. After: green = REDACTED's deed tract (7.96 ac, best-fit COGO traverse, not a survey), red hatching = REDACTED lot excluded from REDACTED.</p></div></section>
<script>(()=>{{const b=document.getElementById('ba'),r=b.querySelector('input'),a=b.querySelector('.after'),bar=b.querySelector('.bar');r.oninput=()=>{{a.style.clipPath=`inset(0 0 0 ${{r.value}}%)`;bar.style.left=r.value+'%'}};bar.style.left='15%'}})()</script>"""

    legend = "".join(f"<span><i style='background:{c}'></i>{k}</span>" for k, c in COLORS.items())
    checks = sorted(iss["check"].dropna().unique()) if len(iss) else []
    steps = "".join(f"<tr><td>{E(s['name'])}</td><td>{E(s['status'])}</td><td>{s.get('seconds', '')}</td><td>{E(s.get('reason') or s.get('error') or '')}</td></tr>" for s in man["steps"])
    color_expr = json.dumps(["match", ["get", "kind"], *sum(([k, v] for k, v in COLORS.items()), []), "#8d99ae"])
    body = f"""{hero}<h2>Latest run</h2><p style="color:var(--mut)">Run <code>{E(man['run_id'])}</code> · {E(man.get('dataset', ''))} · finished {E(man.get('finished', ''))}<br><small>{E(man['policy'])}</small></p>
<div class=kpis><div class=kpi><b data-n={n_par}>{n_par:,}</b><span>parcels</span></div><div class=kpi><b data-n={n_ov}>{n_ov}</b><span>overlap case files</span></div>{kpis}</div>
<h2 id=map-sec>Flagged parcels</h2><div class=legend>{legend}<span style="color:var(--mut)">· heatmap at low zoom, click a parcel</span></div><div id=map></div>
<h2>Issues</h2><input type=search id=q placeholder="search id / message"><select id=chk><option value="">all checks</option>{''.join(f'<option>{E(c)}</option>' for c in checks)}</select><span id=cnt></span>
<div class=tbl><table><thead><tr><th>feature</th><th>check</th><th>severity</th><th>message</th><th>metric</th></tr></thead><tbody id=tb></tbody></table></div>
<h2>Pipeline steps</h2><div class=tbl><table><tr><th>step</th><th>status</th><th>s</th><th>note</th></tr>{steps}</table></div>
<script src="{ML_JS}"></script><script>
// animated counters
const io=new IntersectionObserver(es=>es.forEach(e=>{{if(!e.isIntersecting)return;const el=e.target,n=+el.dataset.n,d=+(el.dataset.d||0),t0=performance.now();io.unobserve(el);
(function f(t){{const k=Math.min(1,(t-t0)/1400),v=n*(1-Math.pow(1-k,3));el.textContent=v.toLocaleString(undefined,{{minimumFractionDigits:d,maximumFractionDigits:d}});if(k<1)requestAnimationFrame(f)}})(t0)}}));
document.querySelectorAll('[data-n]').forEach(el=>io.observe(el));
// map
const m=new maplibregl.Map({{container:'map',style:'{STYLE}',bounds:{json.dumps([[bounds[0], bounds[1]], [bounds[2], bounds[3]]])},fitBoundsOptions:{{padding:30}},attributionControl:{{compact:true}}}});
m.addControl(new maplibregl.NavigationControl());
m.on('load',()=>{{const C={color_expr};
m.addSource('pts',{{type:'geojson',data:'data/flagged_pts.geojson'}});m.addSource('fl',{{type:'geojson',data:'data/flagged.geojson'}});
m.addLayer({{id:'heat',type:'heatmap',source:'pts',maxzoom:14,paint:{{'heatmap-radius':['interpolate',['linear'],['zoom'],8,6,13,22],'heatmap-intensity':['interpolate',['linear'],['zoom'],8,.6,13,1.4],
'heatmap-opacity':['interpolate',['linear'],['zoom'],11,.9,14,0],'heatmap-color':['interpolate',['linear'],['heatmap-density'],0,'rgba(0,0,0,0)',.2,'#3a0ca3',.45,'#7209b7',.7,'#f72585',1,'#ffd166']}}}});
m.addLayer({{id:'fill',type:'fill',source:'fl',minzoom:11,paint:{{'fill-color':C,'fill-opacity':['interpolate',['linear'],['zoom'],11,0,13,.28]}}}});
m.addLayer({{id:'glow',type:'line',source:'fl',minzoom:11,paint:{{'line-color':C,'line-width':7,'line-blur':6,'line-opacity':.55}}}});
m.addLayer({{id:'line',type:'line',source:'fl',minzoom:11,paint:{{'line-color':C,'line-width':1.4}}}});
m.on('click','fill',e=>{{const f=e.features[0],p=f.properties;const b=new maplibregl.LngLatBounds();(f.geometry.type=='Polygon'?[f.geometry.coordinates]:f.geometry.coordinates).forEach(pl=>pl[0].forEach(c=>b.extend(c)));
m.fitBounds(b,{{padding:80,maxZoom:18,duration:1400}});new maplibregl.Popup({{offset:8}}).setLngLat(b.getCenter()).setHTML(`<div class=pop><b>${{p.fid}}</b><br>${{p.checks.replaceAll(',',' · ')}}`+(p.case?`<br><a href="cases/${{p.case}}.html">Case file →</a>`:'')+'</div>').addTo(m)}});
m.on('mouseenter','fill',()=>m.getCanvas().style.cursor='pointer');m.on('mouseleave','fill',()=>m.getCanvas().style.cursor='')}});
// table
let D=[];const tb=document.getElementById('tb');function draw(){{const q=document.getElementById('q').value.toLowerCase(),c=document.getElementById('chk').value;
const r=D.filter(x=>(!c||x.check==c)&&(!q||(x.feature_id+' '+x.message).toLowerCase().includes(q)));document.getElementById('cnt').textContent=r.length+' rows';
tb.innerHTML=r.slice(0,1000).map(x=>`<tr><td>${{x.feature_id}}</td><td>${{x.check}}</td><td>${{x.severity}}</td><td>${{x.message}}</td><td>${{x.metric===''?'':(+x.metric).toFixed(3)}}</td></tr>`).join('')}}
fetch('data/issues.json').then(r=>r.json()).then(d=>{{D=d;draw()}});document.getElementById('q').oninput=draw;document.getElementById('chk').onchange=draw;</script>"""
    (S / "index.html").write_text(page("Dashboard", body, head=f'<link rel=stylesheet href="{ML_CSS}">'))

    # ---- case pages ----
    rows = []
    fgi = fg.set_index("fid") if fg is not None and len(fg) else None
    for v in verdicts:
        a, b = v["parcels"]; d = deeds.get((a, b)); conf = (d["verdict"]["confidence"] if d else v["confidence"])
        rows.append(f"<tr><td><a href='cases/{v['case_id']}.html'>{E(a)} × {E(b)}</a></td><td>{E(v['check'])}</td><td>{v.get('overlap_sqft') or ''}</td>"
                    f"<td>{E(d['verdict']['verdict'] if d else v['proposal'])}</td><td><span class='badge {conf.split()[0]}'>{E(conf)}</span></td><td>{'deed-verified' if d else 'first-pass'}</td></tr>")
        cb = [f"<div class=card><div class=eyebrow>{E(v['check'])} · {'deed-verified' if d else 'first-pass'}</div><h2 style=margin-top:4px>{E(d['verdict']['verdict'] if d else v['proposal'])}</h2>"
              f"<p><span class='badge {conf.split()[0]}'>{E(conf)}</span> · status: <b>proposed</b> (not applied) · overlap {v.get('overlap_sqft') or '?'} sq ft</p><p>{E(v['rationale'])}</p></div>"]
        cb.append("<div class=card><h3>Parcels & ORB references</h3><table><tr><th>parcel</th><th>owner (PA)</th><th>ORB book-page</th></tr>" + "".join(
            f"<tr><td><a href='https://paopropertysearch.coj.net/Basic/Detail.aspx?RE={p.replace(' ', '')}'>{E(p)}</a></td><td>{E(str((v.get('owners') or {}).get(p) or ''))}</td><td>{E(', '.join((v.get('orb_refs') or {}).get(p) or []))}</td></tr>" for p in (a, b)) + "</table></div>")
        head = ""
        if d:
            tp = d.get("traverse_parcel"); tr = travs.get(tp) if tp else None
            if tr and fgi is not None:
                verts = _to_wgs(tr["vertices"]); gis = {}
                for p in (a, b):
                    if p in fgi.index:
                        g = fgi.loc[p].geometry; g = g.iloc[0] if hasattr(g, "iloc") else g
                        gis[p] = json.loads(gpd.GeoSeries([g]).to_json())["features"][0]["geometry"]
                cl = tr["closure"]; clt = f"Closure {cl['precision']} · misclosure {cl['misclosure_ft']} ft · {tr['acres']} ac" if "precision" in cl else f"{cl.get('note', '')} · {tr['acres']} ac"
                data = dict(verts=verts, calls=[c["label"] for c in tr["calls"]], gis=gis, closure=clt, orb=tr["orb"])
                head = f'<link rel=stylesheet href="{ML_CSS}">'
                cb.append(f"""<div class=card><h3>Deed traverse · {E(tr['orb'])}</h3><div class=tctl><button class=btn id=play>▶ Play</button><span class=call id=call>—</span><span id=clo></span></div>
<div class=tmap id=tmap></div><p style="font-size:12px;color:var(--mut)">Green = deed calls drawn segment by segment (best-fit placement, no monument tie); orange/red = GIS outlines.</p></div>
<script src="{ML_JS}"></script><script>const T={json.dumps(data)};
const bb=new maplibregl.LngLatBounds();T.verts.forEach(c=>bb.extend(c));Object.values(T.gis).forEach(g=>(g.type=='Polygon'?[g.coordinates]:g.coordinates).forEach(p=>p[0].forEach(c=>bb.extend(c))));
const tm=new maplibregl.Map({{container:'tmap',style:'{STYLE}',bounds:bb,fitBoundsOptions:{{padding:40}},attributionControl:{{compact:true}}}});
const fc=c=>({{type:'FeatureCollection',features:c}});let raf;
tm.on('load',()=>{{const cols=['#ff9f1c','#ff4d6d'];Object.entries(T.gis).forEach(([k,g],i)=>{{tm.addSource('g'+i,{{type:'geojson',data:{{type:'Feature',geometry:g,properties:{{}}}}}});
tm.addLayer({{id:'gf'+i,type:'fill',source:'g'+i,paint:{{'fill-color':cols[i%2],'fill-opacity':.12}}}});tm.addLayer({{id:'gl'+i,type:'line',source:'g'+i,paint:{{'line-color':cols[i%2],'line-width':2,'line-dasharray':i?[2,2]:[1,0]}}}})}});
tm.addSource('tr',{{type:'geojson',data:fc([])}});tm.addSource('v',{{type:'geojson',data:fc([])}});
tm.addLayer({{id:'trg',type:'line',source:'tr',paint:{{'line-color':'#38d39f','line-width':10,'line-blur':8,'line-opacity':.5}}}});
tm.addLayer({{id:'trl',type:'line',source:'tr',paint:{{'line-color':'#38d39f','line-width':3}}}});
tm.addLayer({{id:'v',type:'circle',source:'v',paint:{{'circle-radius':5,'circle-color':'#fff','circle-stroke-color':'#38d39f','circle-stroke-width':2}}}});
document.getElementById('play').onclick=play;setTimeout(play,600)}});
function play(){{cancelAnimationFrame(raf);const V=T.verts,n=V.length-1,dur=1100;let t0=performance.now();document.getElementById('clo').textContent='';document.getElementById('play').textContent='↻ Replay';
(function step(t){{const k=Math.min(n,(t-t0)/dur),i=Math.floor(k),f=k-i;const pts=V.slice(0,i+1);if(i<n)pts.push([V[i][0]+(V[i+1][0]-V[i][0])*f,V[i][1]+(V[i+1][1]-V[i][1])*f]);
tm.getSource('tr').setData(fc([{{type:'Feature',geometry:{{type:'LineString',coordinates:pts}},properties:{{}}}}]));
tm.getSource('v').setData(fc(pts.map(c=>({{type:'Feature',geometry:{{type:'Point',coordinates:c}},properties:{{}}}}))));
document.getElementById('call').textContent=i<n?`Call ${{i+1}}/${{n}}: ${{T.calls[i]||''}}`:`${{n}} calls · back at POB`;
if(k<n)raf=requestAnimationFrame(step);else document.getElementById('clo').innerHTML='<span class=closure>✓ '+T.closure+'</span>'}})(t0)}}</script>""")
            ev = "".join(f"<li>{E(x)}</li>" for x in d["verdict"].get("evidence", []))
            c = d["cogo"]; nums = []
            if c.get("closure"): nums.append(f"closure {c['closure']['precision']} (misclosure {c['closure']['misclosure_ft']} ft)")
            for k in ("acres_record_cogo", "acres_record_stated", "acres_record_cogo_chorded", "acres_gis_REDACTED", "acres_gis_REDACTED", "acres_gis_patriot", "acres_gis_REDACTED", "acres_gis_city", "acres_gis_REDACTED"):
                if c.get(k) is not None: nums.append(f"{k.replace('_', ' ')}: {c[k]}")
            cb.append(f"<div class=card><h3>Deed evidence</h3><p>{E(c.get('deed') or json.dumps(c.get('deeds', '')))}</p><p>{E(' · '.join(nums))}</p><ul>{ev}</ul>"
                      + (f"<p><i>{E(d['verdict']['caveat'])}</i></p>" if d['verdict'].get('caveat') else "") + "</div>")
            if (imgsrc / d["png"]).exists():
                shutil.copy2(imgsrc / d["png"], S / "img" / d["png"])
                note = "" if include_coj_imagery else "<p><small>Static overlay shown without aerial basemap: the COJ orthoimagery has no published licence, so imagery figures are kept out of the public site.</small></p>"
                cb.append(f"<div class=card><h3>Overlay figure</h3><img class=fig src='../img/{d['png']}' alt='overlay'>{note}</div>")
        (S / "cases" / f"{v['case_id']}.html").write_text(page(f"Case {a} × {b}", "".join(cb), depth=1, head=head))
    (S / "cases.html").write_text(page("Case files", "<h2>Case files</h2><div class=tbl><table><tr><th>pair</th><th>check</th><th>sq ft</th><th>verdict / proposal</th><th>confidence</th><th>basis</th></tr>" + "".join(rows) + "</table></div>"))

    hist = []
    for mf in sorted(Path(runs).glob("*/manifest.json"), reverse=True):
        m = json.loads(mf.read_text()); ins = next((s for s in m["steps"] if s["name"] == "inspect"), {})
        hist.append(dict(run_id=m["run_id"], finished=m.get("finished"), features=ins.get("features"), issues=ins.get("issues"),
                         by_check=ins.get("by_check"), steps={s["name"]: s["status"] for s in m["steps"]}))
    (S / "data" / "history.json").write_text(json.dumps(hist, indent=1))
    hr = "".join(f"<tr><td>{E(h['run_id'])}</td><td>{E(str(h['finished']))}</td><td>{h['features'] or ''}</td><td>{h['issues'] or ''}</td><td>{E(json.dumps(h['by_check']))}</td><td>{E(' '.join(f'{k}:{v}' for k, v in h['steps'].items()))}</td></tr>" for h in hist)
    (S / "history.html").write_text(page("Run history", f"<h2>Run history</h2><div class=tbl><table><tr><th>run</th><th>finished</th><th>parcels</th><th>issues</th><th>by check</th><th>steps</th></tr>{hr}</table></div>"))
    return dict(site=str(S), cases=len(verdicts), issues=len(recs), runs=len(hist), hero=bool(hero))
