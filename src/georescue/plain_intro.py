"""Plain-language 'start here' section for the GeoRescue dashboard (redesign-plain).
Facts only from this repo: README, glossary (COLORS), footer data sources, Pages workflow."""
CONTACT = "geoknight0015@gmail.com"

_LEG = [("#ff4d6d", "Contained parcel", "one lot drawn on top of a bigger one instead of cut out of it"),
        ("#ff9f1c", "Overlap", "two parcels claim the same piece of ground"),
        ("#4cc9f0", "Gap", "a small hole between parcels that no parcel covers"),
        ("#80ffdb", "Sliver", "a tiny or very thin strip, often a leftover of lines that don't meet"),
        ("#b388ff", "Invalid shape", "an outline that breaks basic drawing rules, e.g. crosses itself"),
        ("#ffd166", "Missing information", "a required field, such as owner name, is blank")]

INTRO = f"""<section class=plain id=start aria-labelledby=start-h>
<div class=p-hero><div class=p-eyebrow>GeoKnight GIS · public demo · Duval County, Florida</div>
<h1 id=start-h>GeoRescue scans public property maps for drawing mistakes and shows each one on a map, in plain English.</h1>
<p class=p-lede>County parcel maps are the outlines of every property lot. Sometimes those outlines overlap, leave holes, or don't match the deed.
GeoRescue checks every parcel in the county's public map automatically, flags what looks wrong, and explains why. Nothing is changed in any official record.</p>
<div class=p-cta><a class="btn gold" href="#map-sec">Explore the map</a><a class="btn ghost" href="#how">How it works</a><a class="btn ghost" href="mailto:{CONTACT}?subject=GeoRescue%20question">Contact GeoKnight GIS</a></div>
<p class=p-note>Test demo, not authoritative: results are automated proposals, not surveys, title opinions or legal advice.</p></div>

<h2 id=how>How it works, in 3 steps</h2><ol class=p-steps>
<li><span>1</span><b>Load the public map</b>GeoRescue downloads Duval County's public parcel map (City of Jacksonville / Property Appraiser) on an automatic schedule.</li>
<li><span>2</span><b>Check every parcel</b>Automated tests look for overlaps, lots inside other lots, holes, slivers, broken shapes and missing information.</li>
<li><span>3</span><b>Explain and propose</b>Each problem is flagged with a plain explanation. For a few cases, the recorded deed is read and compared. Fixes are suggestions for a person to review, never applied to official data.</li></ol>

<h2>Who it's for</h2><div class=p-cards>
<div><b>Property owners &amp; neighbours</b>See whether the public map around a lot looks consistent.</div>
<div><b>GIS &amp; mapping teams</b>Get a list of likely map errors to review, with the reason for each.</div>
<div><b>Surveyors, title &amp; real-estate pros</b>Spot places worth a closer look. Final answers still need a licensed surveyor or attorney.</div></div>

<h2>Reading the map</h2><p class=p-sub>Each colour is one kind of problem. Zoomed out you see a heat map of where problems cluster; zoom in and click a parcel for details.</p>
<ul class=p-legend>{''.join(f'<li><i style="background:{c}"></i><b>{n}</b> {d}</li>' for c, n, d in _LEG)}</ul>
<p class=p-sub><a href="glossary.html">Full glossary of every check →</a> · <a href="cases.html">Case files with deed comparisons →</a></p>

<h2>Where the data comes from</h2><p class=p-sub>Parcel outlines: City of Jacksonville / Duval Property Appraiser (maps.coj.net CityBiz/Parcels). Legal descriptions: Duval Property Appraiser. Deeds: Duval Clerk of Courts Official Records.
Basemap © CARTO © OpenStreetMap contributors; map library MapLibre GL JS. GeoRescue is not affiliated with these agencies and does not own their data. Owner names are redacted on this site.</p>

<h2>Questions</h2><div class=p-faq>
<details><summary>Does this change the county's records?</summary><p>No. GeoRescue works on its own copy. The only automatic fix is repairing broken shapes in that copy; everything else is a proposal for review.</p></details>
<details><summary>Is a flag proof something is wrong with my property?</summary><p>No. A flag means the public map looks inconsistent. Many flags are harmless drawing quirks. Only a licensed surveyor, an attorney and the official records can settle a boundary.</p></details>
<details><summary>What is the "featured test case" below?</summary><p>One example where a smaller lot appears to be drawn inside a larger parcel. GeoRescue read the larger parcel's deed and compared its described shape to the map. Owner names are replaced with "Parcel A" and "Parcel B".</p></details>
<details><summary>How often is it updated?</summary><p>The public demo is set to re-run automatically once a week. The date of the latest run is shown under "Latest run".</p></details>
<details><summary>I found an error or want my parcel removed.</summary><p>Open an issue at <a href="https://github.com/knightchrism/georescue/issues">github.com/knightchrism/georescue/issues</a> or email <a href="mailto:{CONTACT}">{CONTACT}</a>.</p></details></div>

<div class=p-band><div><b>Want this kind of check on your own parcel data?</b><span>Ask GeoKnight GIS what's possible for your map.</span></div><a class="btn gold" href="mailto:{CONTACT}?subject=GeoRescue%20inquiry">Email geoknight0015@gmail.com</a></div>
<h2 class=p-detail>The details: featured test case and latest run</h2></section>"""

CSS = """
.plain{--navy:#0b1b33;--navy2:#13294b;--gold:#f2c14e;--gold2:#ffd97a;max-width:1180px;margin:0 auto 28px}
.p-hero{background:radial-gradient(1200px 400px at 85% -10%,#1f4f8a55,transparent 60%),radial-gradient(2px 2px at 20% 30%,#ffffffaa,transparent),radial-gradient(1.5px 1.5px at 70% 60%,#ffffff88,transparent),radial-gradient(1.5px 1.5px at 45% 15%,#ffe9a877,transparent),linear-gradient(160deg,var(--navy),#071222 70%);color:#eef3fb;border:1px solid #f2c14e33;border-radius:18px;padding:clamp(22px,4vw,48px);box-shadow:0 10px 40px #0006}
.p-eyebrow{color:var(--gold);font-weight:700;letter-spacing:1.6px;text-transform:uppercase;font-size:12px}
.p-hero h1{font-family:'Exo 2',system-ui,sans-serif;font-size:clamp(26px,3.6vw,44px);line-height:1.12;margin:10px 0 14px;max-width:24ch}
.p-lede{font-size:clamp(16px,1.4vw,19px);max-width:62ch;color:#cfdaea}.p-note{font-size:13px;color:#9fb0c8;margin:14px 0 0}
.p-cta{display:flex;flex-wrap:wrap;gap:10px;margin-top:18px}.btn{display:inline-block;padding:11px 18px;border-radius:10px;font-weight:700;text-decoration:none}
.plain .btn.gold{background:linear-gradient(180deg,var(--gold2),var(--gold));color:#1a1405;border:0}.plain .btn.ghost{background:transparent;border:1px solid #f2c14e88;color:#f6e3b0}
.plain h2{font-family:'Exo 2',system-ui,sans-serif;margin:34px 0 12px;border-left:4px solid var(--gold);padding-left:10px}
.p-steps{list-style:none;padding:0;display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.p-steps li,.p-cards div{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px}
.p-steps span{display:inline-grid;place-items:center;width:34px;height:34px;border-radius:50%;background:var(--navy2);color:var(--gold);font-weight:800;margin-bottom:8px;border:1px solid #f2c14e66}
.p-steps b,.p-cards b{display:block;font-size:17px;margin-bottom:4px}.p-cards{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.p-sub{color:var(--mut);max-width:80ch}.p-legend{list-style:none;padding:0;display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.p-legend li{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;color:var(--mut)}.p-legend b{color:var(--fg);display:block}
.p-legend i{display:inline-block;width:14px;height:14px;border-radius:4px;margin-right:8px;vertical-align:-2px;float:left;margin-top:5px}
.p-faq details{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 16px;margin-bottom:8px}.p-faq summary{cursor:pointer;font-weight:700}
.p-band{margin-top:26px;display:flex;flex-wrap:wrap;gap:14px;align-items:center;justify-content:space-between;background:linear-gradient(90deg,var(--navy),var(--navy2));color:#eef3fb;border:1px solid #f2c14e55;border-radius:16px;padding:20px 24px}
.p-band b{display:block;font-size:18px}.p-band span{color:#c6d3e6}.p-detail{margin-top:40px!important}
header{border-bottom:2px solid #f2c14e66}
@media(max-width:1000px){.p-legend{grid-template-columns:repeat(2,1fr)}}
@media(max-width:760px){.p-steps,.p-cards,.p-legend{grid-template-columns:1fr}.btn{flex:1 1 100%;text-align:center}}
@media(min-width:1700px){.plain{max-width:1400px}}
"""

def apply_static(index_html: str, nav_link=True) -> str:
    """Inject the intro into an already-published index.html (idempotent)."""
    if 'class=plain id=start' in index_html:
        return index_html
    out = index_html.replace("<main>", "<main>" + INTRO, 1)
    if nav_link:
        out = out.replace('<nav><a href="index.html">Dashboard</a>', '<nav><a href="index.html#start">Start here</a><a href="index.html">Dashboard</a>', 1)
    return out
