from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1400, "height": 1800})
    pg.goto("http://localhost:8599"); pg.wait_for_selector("text=Downloads", timeout=90000); pg.wait_for_timeout(4000)
    pg.screenshot(path="docs/demo.png", full_page=True); b.close()
