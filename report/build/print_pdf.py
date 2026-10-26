"""Print report/build/{report,body}.html to PDF with Playwright Chromium (waits for the web fonts).
Usage: uv run --with playwright python report/build/print_pdf.py"""
from pathlib import Path

from playwright.sync_api import sync_playwright

B = Path(__file__).resolve().parent
with sync_playwright() as p:
    br = p.chromium.launch()
    pg = br.new_page()
    for name in ("body", "report"):
        pg.goto((B / f"{name}.html").as_uri(), wait_until="networkidle")
        pg.evaluate("document.fonts.ready")
        ok = pg.evaluate("document.fonts.check('11pt \"Old Standard TT\"')")
        pg.pdf(path=str(B / f"{name}.pdf"), format="Letter", print_background=True, prefer_css_page_size=True)
        print(name, "font loaded:", ok)
    br.close()
