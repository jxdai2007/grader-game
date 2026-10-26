from pathlib import Path
from playwright.sync_api import sync_playwright
D = Path(__file__).resolve().parent
(D / "png").mkdir(exist_ok=True)
with sync_playwright() as p:
    br = p.chromium.launch()
    pg = br.new_page(viewport={"width": 1920, "height": 1080})
    pg.goto((D / "slides.html").as_uri()); pg.wait_for_load_state("networkidle")
    slides = pg.query_selector_all("section.slide")
    for i, el in enumerate(slides, 1):
        el.screenshot(path=str(D / "png" / f"slide{i:02d}.png"))
    pg.pdf(path=str(D / "slides.pdf"), width="1920px", height="1080px", print_background=True, prefer_css_page_size=True)
    print(len(slides), "slides")
    br.close()
