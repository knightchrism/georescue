"""Generate GeoRescue brand SVGs (eye + globe-grid + crosshair). Run: uv run python brand/make_brand.py"""
import math
from pathlib import Path
D = Path(__file__).parent
CX, CY, HW, SAG = 256, 256, 216, 150
R = (HW**2 + SAG**2) / (2 * SAG)
EYE = f"M{CX-HW} {CY} A{R:.1f} {R:.1f} 0 0 1 {CX+HW} {CY} A{R:.1f} {R:.1f} 0 0 1 {CX-HW} {CY}Z"
def yarc(x):  # half-height of eye at x
    return math.sqrt(R**2 - (x - CX)**2) - (R - SAG)
def grid(nm, np_):
    p = []
    for i in range(1, nm):
        t = -1 + 2 * i / nm
        if abs(t) < 1e-9: continue
        xt = CX + t * HW * 0.82; h = yarc(xt); xc = CX + t * HW * 1.12
        p.append(f"M{xt:.1f} {CY-h:.1f} Q{xc:.1f} {CY} {xt:.1f} {CY+h:.1f}")
    for j in range(1, np_):
        s = -1 + 2 * j / np_
        if abs(s) < 1e-9: continue
        y = CY + s * SAG; yc = CY + s * SAG * 1.18
        p.append(f"M{CX-HW} {y:.1f} Q{CX} {yc:.1f} {CX+HW} {y:.1f}")
    return " ".join(p)
DEFS = """<linearGradient id=g x1=0 y1=0 x2=1 y2=1><stop offset=0 stop-color='#1e6bff'/><stop offset=1 stop-color='#2ee6ff'/></linearGradient>
<clipPath id=c><path d='{eye}'/></clipPath>
<filter id=glow x='-30%' y='-30%' width='160%' height='160%'><feGaussianBlur stdDeviation='7' result=b/><feMerge><feMergeNode in=b/><feMergeNode in=b/><feMergeNode in=SourceGraphic/></feMerge></filter>"""
def mark(flat=False, tx=0, ty=0, sc=1.0):
    nm, np_, gw = (8, 6, 7) if flat else (22, 14, 2.2)
    f = "" if flat else " filter='url(#glow)'"
    cross = f"<path d='M{CX-HW} {CY}H{CX+HW}M{CX} {CY-SAG}V{CY+SAG}' stroke-width={10 if flat else 4}/>"
    ring = f"<circle cx={CX} cy={CY} r={40 if flat else 52} fill='{'#05070d' if flat else 'none'}' stroke-width={12 if flat else 5}/><circle cx={CX} cy={CY} r={12 if flat else 7} fill='url(#g)' stroke=none/>"
    return (f"<g transform='translate({tx} {ty}) scale({sc})' fill=none stroke='url(#g)' stroke-linecap=round{f}>"
            f"<g clip-path='url(#c)' stroke-width={gw} opacity={0.9 if flat else 0.75}><path d='{grid(nm, np_)}'/></g>"
            f"{cross}{ring}<path d='{EYE}' stroke-width={14 if flat else 6} stroke-linejoin=miter/></g>")
def svg(w, h, body, bg=True):
    q = lambda s: s.replace("=", "=").replace("{eye}", EYE)
    head = f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {w} {h}' width='{w}' height='{h}'><defs>{q(DEFS)}</defs>"
    return head + (f"<rect width='{w}' height='{h}' fill='#05070d'/>" if bg else "") + body + "</svg>"
WORD = "font-family=\"'Exo 2','Rajdhani','Orbitron',system-ui,sans-serif\" font-weight=600 fill='#f4f8ff'"
def quote(s):  # make attributes XML-valid
    import re
    return re.sub(r"(\s[\w:-]+)=([^'\"\s>/]+)", r"\1='\2'", s)
out = {
 "logo-mark.svg": svg(512, 512, mark(), bg=False),
 "logo-mark-flat.svg": svg(512, 512, mark(flat=True), bg=False),
 "logo-horizontal.svg": svg(1400, 360, mark(tx=10, ty=-76, sc=1.0) + f"<text x=540 y=225 font-size=170 {WORD}>GeoRescue</text>", bg=False),
 "logo-stacked.svg": svg(800, 820, mark(tx=144, ty=40, sc=1.0) + f"<text x=400 y=690 text-anchor=middle font-size=150 {WORD}>GeoRescue</text>", bg=False),
 "favicon.svg": svg(512, 512, "<rect width=512 height=512 rx=96 fill='#05070d'/>" + mark(flat=True, tx=-8, ty=-8, sc=1.03), bg=False),
}
for k, v in out.items():
    (D / k).write_text(quote(v))
print("ok", list(out))
