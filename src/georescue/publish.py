"""`georescue publish`: static dashboard (HTML + Leaflet + JSON) from out/latest -> site/ (GitHub Pages ready)."""
from __future__ import annotations
import html, json, shutil
from pathlib import Path
import pandas as pd

LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
CSS = """body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:0;color:#222;background:#f6f7f9}
header{background:#24323f;color:#fff;padding:14px 24px}header a{color:#cfe3f5;margin-right:16px;text-decoration:none}
h1{font-size:20px;margin:0 0 6px}main{padding:18px 24px;max-width:1300px;margin:auto}
.kpis{display:flex;flex-wrap:wrap;gap:10px}.kpi{background:#fff;border:1px solid #dde;border-radius:6px;padding:10px 14px;min-width:120px}
.kpi b{display:block;font-size:22px}.kpi span{font-size:12px;color:#667}
table{border-collapse:collapse;width:100%;background:#fff;font-size:12.5px}th,td{border-bottom:1px solid #e4e6ea;padding:5px 8px;text-align:left;vertical-align:top}
th{background:#eef1f4;position:sticky;top:0}#map{height:460px;border:1px solid #ccd;border-radius:6px;margin:12px 0}
.tbl{max-height:520px;overflow:auto;border:1px solid #dde}input,select{padding:5px;margin:0 6px 8px 0}
.badge{padding:2px 7px;border-radius:10px;font-size:11px;color:#fff}.high{background:#2e7d4f}.medium{background:#c18a1d}.low{background:#a33}
.card{background:#fff;border:1px solid #dde;border-radius:6px;padding:12px 16px;margin:12px 0}img.fig{max-width:100%;border:1px solid #ccd}
footer{font-size:11px;color:#667;padding:16px 24px;border-top:1px solid #dde}code{background:#eef1f4;padding:1px 4px}"""
FOOT = ("Data: City of Jacksonville / Duval Property Appraiser parcels (maps.coj.net CityBiz/Parcels); Duval Property Appraiser "
        "(paopropertysearch.coj.net); Duval Clerk of Courts Official Records (or.duvalclerk.com). Map tiles &copy; OpenStreetMap contributors. "
        "Map library: Leaflet (BSD-2-Clause). Deed outlines are COGO traverses best-fit to GIS, not surveys; all fixes except invalid-geometry repair are proposals for review.")
E = html.escape


def page(title, body, depth=0, head=""):
    up = "../" * depth
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>{E(title)} · GeoRescue</title><link rel=stylesheet href="{up}assets/style.css">{head}</head><body>
<header><h1>GeoRescue · {E(title)}</h1><nav><a href="{up}index.html">Dashboard</a><a href="{up}cases.html">Case files</a><a href="{up}history.html">Run history</a></nav></header>
<main>{body}</main><footer>{FOOT}</footer></body></html>"""


def _deed_index(vdir: Path):
    """Map case_id -> manual deed verification (verdicts + COGO numbers + PNGs)."""
    out = {}
    vf, cf = vdir / "deed_verdicts.json", vdir / "deed_cogo_duval.json"
    if not vf.exists(): return out
    v = json.loads(vf.read_text()); c = json.loads(cf.read_text()) if cf.exists() else {}
    keys = {"REDACTED_001542_0010_vs_REDACTED_001531_5300": ("001542 0010", "001531 5300", "deed_REDACTED_overlay.png"),
            "patriot_013030_0010_vs_REDACTED_013030_0300": ("013030 0010", "013030 0300", "deed_patriot_REDACTED_overlay.png"),
            "city_004307_0320_vs_REDACTED_004307_0230": ("004307 0320", "004307 0230", "deed_city_REDACTED_overlay.png")}
    for k, (a, b, png) in keys.items():
        if k in v: out[(a, b)] = dict(verdict=v[k], cogo=c.get(k, {}), png=png)
    return out


def publish(latest="out/latest", site="site", runs="out/runs", include_coj_imagery=False) -> dict:
    L, S = Path(latest), Path(site)
    if S.exists(): shutil.rmtree(S)
    (S / "data").mkdir(parents=True); (S / "assets").mkdir(); (S / "cases").mkdir(); (S / "img").mkdir()
    (S / "assets" / "style.css").write_text(CSS); (S / ".nojekyll").write_text("")
    man = json.loads((L / "manifest.json").read_text())
    summ = json.loads((L / "summary.json").read_text()) if (L / "summary.json").exists() else {}
    iss = pd.read_csv(L / "issues.csv") if (L / "issues.csv").exists() else pd.DataFrame(columns=["feature_id", "check", "severity", "message"])
    cols = [c for c in ["feature_id", "check", "severity", "message", "metric"] if c in iss.columns]
    recs = iss[cols].astype(object).where(iss[cols].notna(), "").to_dict("records")
    for r in recs: r["message"] = str(r["message"]).split("|")[0][:240]
    (S / "data" / "issues.json").write_text(json.dumps(recs))
    if (L / "flagged.geojson").exists():   # small web copy: simplified (~1 m), 6-decimal coords, flagged parcels only
        import geopandas as gpd
        fg = gpd.read_file(L / "flagged.geojson")
        fg["geometry"] = fg.geometry.simplify(1e-5, preserve_topology=True)
        fg.to_file(S / "data" / "flagged.geojson", driver="GeoJSON", COORDINATE_PRECISION=6)
    shutil.copy2(L / "manifest.json", S / "data" / "manifest.json")
    verdicts = json.loads((L / "verdicts.json").read_text()) if (L / "verdicts.json").exists() else []
    deeds = _deed_index(L / "verify")
    # imagery figures: COJ ortho has no published licence -> excluded unless explicitly allowed; use non-imagery v1 figures
    imgsrc = L / "verify" if include_coj_imagery else L / "verify" / "v1"

    by = summ.get("issues_by_check") or iss["check"].value_counts().to_dict()
    kpis = "".join(f"<div class=kpi><b>{n:,}</b><span>{E(k)}</span></div>" for k, n in sorted(by.items(), key=lambda x: -x[1]))
    kpis = f"<div class=kpi><b>{summ.get('features', 0):,}</b><span>parcels</span></div><div class=kpi><b>{len(verdicts)}</b><span>overlap case files</span></div>" + kpis
    checks = sorted(iss["check"].dropna().unique()) if len(iss) else []
    steps = "".join(f"<tr><td>{E(s['name'])}</td><td>{E(s['status'])}</td><td>{s.get('seconds', '')}</td><td>{E(s.get('reason') or s.get('error') or '')}</td></tr>" for s in man["steps"])
    body = f"""<p>Run <code>{E(man['run_id'])}</code> · dataset {E(man.get('dataset', ''))} · finished {E(man.get('finished', ''))}<br><small>{E(man['policy'])}</small></p>
<div class=kpis>{kpis}</div><h2>Flagged parcels</h2><div id=map></div>
<h2>Issues</h2><input id=q placeholder="search id / message"><select id=chk><option value="">all checks</option>{''.join(f'<option>{E(c)}</option>' for c in checks)}</select><span id=cnt></span>
<div class=tbl><table><thead><tr><th>feature</th><th>check</th><th>severity</th><th>message</th><th>metric</th></tr></thead><tbody id=tb></tbody></table></div>
<h2>Pipeline steps</h2><table><tr><th>step</th><th>status</th><th>s</th><th>note</th></tr>{steps}</table>
<script src="{LEAFLET_JS}"></script><script>
const m=L.map('map').setView([30.33,-81.66],10);L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',{{maxZoom:19,attribution:'&copy; OpenStreetMap contributors'}}).addTo(m);
const col=c=>c.includes('contained')?'#d62728':c.includes('overlap')?'#ff7f0e':c.includes('invalid')?'#9467bd':c.includes('gap')?'#1f77b4':'#7f7f7f';
fetch('data/flagged.geojson').then(r=>r.json()).then(g=>{{const l=L.geoJSON(g,{{style:f=>({{color:col(f.properties.checks||''),weight:1.5,fillOpacity:.25}}),
onEachFeature:(f,x)=>x.bindPopup('<b>'+f.properties.fid+'</b><br>'+f.properties.checks)}}).addTo(m);if(l.getBounds().isValid())m.fitBounds(l.getBounds())}}).catch(()=>{{}});
let D=[];const tb=document.getElementById('tb');function draw(){{const q=document.getElementById('q').value.toLowerCase(),c=document.getElementById('chk').value;
const r=D.filter(x=>(!c||x.check==c)&&(!q||(x.feature_id+' '+x.message).toLowerCase().includes(q)));document.getElementById('cnt').textContent=r.length+' rows';
tb.innerHTML=r.slice(0,1000).map(x=>`<tr><td>${{x.feature_id}}</td><td>${{x.check}}</td><td>${{x.severity}}</td><td>${{x.message}}</td><td>${{x.metric===''?'':(+x.metric).toFixed(3)}}</td></tr>`).join('')}}
fetch('data/issues.json').then(r=>r.json()).then(d=>{{D=d;draw()}});document.getElementById('q').oninput=draw;document.getElementById('chk').onchange=draw;</script>"""
    (S / "index.html").write_text(page("Dashboard", body, head=f'<link rel=stylesheet href="{LEAFLET_CSS}">'))

    rows = []
    for v in verdicts:
        a, b = v["parcels"]; d = deeds.get((a, b)); conf = (d["verdict"]["confidence"] if d else v["confidence"])
        rows.append(f"<tr><td><a href='cases/{v['case_id']}.html'>{E(a)} × {E(b)}</a></td><td>{E(v['check'])}</td><td>{v.get('overlap_sqft') or ''}</td>"
                    f"<td>{E(d['verdict']['verdict'] if d else v['proposal'])}</td><td><span class='badge {conf.split()[0]}'>{E(conf)}</span></td><td>{'deed-verified' if d else 'first-pass'}</td></tr>")
        cb = [f"<div class=card><h3>Verdict</h3><p><b>{E(d['verdict']['verdict'] if d else v['proposal'])}</b> <span class='badge {conf.split()[0]}'>{E(conf)}</span> · status: <b>proposed</b> (not applied)</p>"
              f"<p>{E(v['rationale'])}</p><p>Overlap: {v.get('overlap_sqft') or '?'} sq ft · check <code>{E(v['check'])}</code></p></div>"]
        cb.append("<div class=card><h3>Parcels & ORB references</h3><table><tr><th>parcel</th><th>owner (PA)</th><th>ORB book-page</th></tr>" + "".join(
            f"<tr><td><a href='https://paopropertysearch.coj.net/Basic/Detail.aspx?RE={p.replace(' ', '')}'>{E(p)}</a></td><td>{E(str((v.get('owners') or {}).get(p) or ''))}</td><td>{E(', '.join((v.get('orb_refs') or {}).get(p) or []))}</td></tr>" for p in (a, b)) + "</table></div>")
        if d:
            ev = "".join(f"<li>{E(x)}</li>" for x in d["verdict"].get("evidence", []))
            c = d["cogo"]; nums = []
            if c.get("closure"): nums.append(f"closure {c['closure']['precision']} (misclosure {c['closure']['misclosure_ft']} ft)")
            for k in ("acres_record_cogo", "acres_record_stated", "acres_record_cogo_chorded", "acres_gis_REDACTED", "acres_gis_REDACTED", "acres_gis_patriot", "acres_gis_REDACTED", "acres_gis_city", "acres_gis_REDACTED"):
                if c.get(k) is not None: nums.append(f"{k.replace('_', ' ')}: {c[k]}")
            cb.append(f"<div class=card><h3>Deed verification</h3><p>{E(c.get('deed') or json.dumps(c.get('deeds', '')))}</p><p>{E(' · '.join(nums))}</p><ul>{ev}</ul>"
                      + (f"<p><i>{E(d['verdict']['caveat'])}</i></p>" if d['verdict'].get('caveat') else "") + "</div>")
            if (imgsrc / d["png"]).exists():
                shutil.copy2(imgsrc / d["png"], S / "img" / d["png"])
                note = "" if include_coj_imagery else "<p><small>Overlay shown without aerial basemap: the COJ orthoimagery has no published licence, so imagery figures are kept out of the public site.</small></p>"
                cb.append(f"<div class=card><h3>Overlay</h3><img class=fig src='../img/{d['png']}' alt='overlay'>{note}</div>")
        (S / "cases" / f"{v['case_id']}.html").write_text(page(f"Case {a} × {b}", "".join(cb), depth=1))
    (S / "cases.html").write_text(page("Case files", "<table><tr><th>pair</th><th>check</th><th>sq ft</th><th>verdict / proposal</th><th>confidence</th><th>basis</th></tr>" + "".join(rows) + "</table>"))

    hist = []
    for mf in sorted(Path(runs).glob("*/manifest.json"), reverse=True):
        m = json.loads(mf.read_text()); ins = next((s for s in m["steps"] if s["name"] == "inspect"), {})
        hist.append(dict(run_id=m["run_id"], finished=m.get("finished"), features=ins.get("features"), issues=ins.get("issues"),
                         by_check=ins.get("by_check"), steps={s["name"]: s["status"] for s in m["steps"]}))
    (S / "data" / "history.json").write_text(json.dumps(hist, indent=1))
    hr = "".join(f"<tr><td>{E(h['run_id'])}</td><td>{E(str(h['finished']))}</td><td>{h['features'] or ''}</td><td>{h['issues'] or ''}</td><td>{E(json.dumps(h['by_check']))}</td><td>{E(' '.join(f'{k}:{v}' for k, v in h['steps'].items()))}</td></tr>" for h in hist)
    (S / "history.html").write_text(page("Run history", f"<table><tr><th>run</th><th>finished</th><th>parcels</th><th>issues</th><th>by check</th><th>steps</th></tr>{hr}</table>"))
    return dict(site=str(S), cases=len(verdicts), issues=len(recs), runs=len(hist))
