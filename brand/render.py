"""Rasterize brand SVGs + og.png via headless Chromium (Playwright). Run: uv run python brand/render.py"""
from pathlib import Path
from playwright.sync_api import sync_playwright
from PIL import Image
D = Path(__file__).parent.resolve()
def shot(b, svg, w, h, out, bg="transparent"):
    pg = b.new_page(viewport={"width": w, "height": h})
    pg.set_content(f"<html><body style='margin:0;background:{bg}'><div style='width:{w}px;height:{h}px'>{(D/svg).read_text().replace("<svg ","<svg style='width:100%;height:100%;display:block' ",1)}</div></body></html>")
    pg.wait_for_timeout(300); pg.screenshot(path=str(out), omit_background=(bg == "transparent")); pg.close()
with sync_playwright() as p:
    b = p.chromium.launch()
    for s in (512, 192):
        shot(b, "logo-mark.svg", s, s, D / f"logo-mark-{s}.png")
    shot(b, "logo-mark-flat.svg", 32, 32, D / "logo-mark-32.png")
    shot(b, "favicon.svg", 180, 180, D / "apple-touch-icon.png")
    shot(b, "favicon.svg", 256, 256, D / "_fav256.png")
    shot(b, "logo-horizontal.svg", 1400, 360, D / "logo-horizontal.png")
    shot(b, "logo-stacked.svg", 800, 820, D / "logo-stacked.png")
    pg = b.new_page(viewport={"width": 1200, "height": 630})
    pg.set_content(f"""<html><body style="margin:0;width:1200px;height:630px;background:radial-gradient(circle at 50% 38%,#0d1a33,#05070d 70%);display:flex;flex-direction:column;align-items:center;justify-content:center;font-family:'Exo 2',sans-serif">
<div style='width:400px;height:400px;margin:-70px 0 -80px'>{(D/"logo-mark.svg").read_text().replace("<svg ","<svg style='width:100%;height:100%' ",1)}</div>
<div style="color:#f4f8ff;font-size:92px;font-weight:600;letter-spacing:1px">GeoRescue</div>
<div style="color:#7fdcff;font-size:36px;margin-top:6px">Evidence-based parcel boundary QA</div></body></html>""")
    pg.wait_for_timeout(400); pg.screenshot(path=str(D / "og.png")); b.close()
Image.open(D / "_fav256.png").save(D / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)]); (D / "_fav256.png").unlink()
print("ok")
