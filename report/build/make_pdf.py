"""Render report/report.md to report/build/report.html in the official sprint template's layout and fonts
(Letter, 1-inch margins, Old Standard TT 11 pt at 1.15 line spacing, title between a thick and a thin rule,
centred author block with "With Apart Research", centred Abstract heading, numbered 14 pt section headings,
the sprint footnote). Usage: uv run --with markdown python report/build/make_pdf.py [--body-only]"""
import re
import sys
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[2]
src = (ROOT / "report/report.md").read_text()
src = re.sub(r"<!--.*?-->\s*", "", src, flags=re.S)
title_line, rest = src.split("\n", 1)
title = title_line.lstrip("# ").strip()
rest = rest.replace("Jollen Dai — Independent — with Apart Research", "", 1)
abstract = rest[rest.index("## Abstract") + len("## Abstract"): rest.index("## 1. Introduction")].strip()
body_md = rest[rest.index("## 1. Introduction"):]
if "--body-only" in sys.argv:
    body_md = body_md[: body_md.index("## Code and Data")]
body_md = body_md.replace("](results/", f"]({ROOT}/results/")
body_html = markdown.markdown(body_md, extensions=["tables", "fenced_code"])
i = body_html.find("<h2>References</h2>")
if i >= 0:
    j = body_html.find("<ul>", i); k = body_html.find("</ul>", j)
    body_html = body_html[:j] + "<ol>" + body_html[j + 4:k] + "</ol>" + body_html[k + 5:]
md = lambda t: markdown.markdown(t, extensions=["tables", "fenced_code"])  # noqa: E731
css = """
@page { size: Letter; margin: 1in; }
body { font-family: 'Old Standard TT', 'Times New Roman', serif; font-size: 11pt; line-height: 1.15; color: #000; }
.toprule { border-top: 3pt solid #000; margin: 0 0 22pt; }
h1.title { font-size: 20pt; font-weight: bold; text-align: center; line-height: 1.2; margin: 0 0 22pt; }
.midrule { border-top: 0.75pt solid #000; margin: 0 0 18pt; }
.authors { text-align: center; margin: 0 0 10pt; } .authors div { line-height: 1.25; }
.with { text-align: center; margin: 0 0 16pt; line-height: 1.25; } .with b { display: block; }
h2.abs { font-size: 14pt; text-align: center; margin: 12pt 0 10pt; }
.abstract { margin: 0 0.95in 6pt; text-align: justify; }
.abstract p { margin: 0 0 8pt; }
h2 { font-size: 14pt; font-weight: bold; margin: 11pt 0 2pt; line-height: 1.4; }
h3 { font-size: 12pt; font-weight: bold; margin: 7pt 0 2pt; }
p { margin: 0 0 4pt; text-align: justify; }
table { border-collapse: collapse; font-size: 8.5pt; margin: 4pt 0 10pt; width: 100%; line-height: 1.2; }
th, td { border: 0.6pt solid #888; padding: 2.5pt 4pt; text-align: left; vertical-align: top; }
th { background: #f2f2f2; }
img { width: 62%; display: block; margin: 4pt auto 2pt; }
pre { font-size: 7.5pt; white-space: pre-wrap; background: #f6f6f4; padding: 6pt; line-height: 1.25; }
code { font-family: 'Courier New', monospace; font-size: 9pt; }
pre code { font-size: 7.5pt; }
ul, ol { margin: 0 0 8pt 20pt; padding: 0; } li { margin-bottom: 2pt; }
.fn { font-size: 9pt; border-top: 0.6pt solid #000; width: 2.2in; margin-top: 14pt; padding-top: 3pt; }
.fn span { display: block; width: 6.5in; }
a { color: #1155cc; }
h2, h3 { break-after: avoid; page-break-after: avoid; }
img, table tr { break-inside: avoid; }
.p1 { height: 8.9in; display: flex; flex-direction: column; break-after: page; }
"""
html = f"""<!doctype html><html><head><meta charset="utf-8"><title>{title}</title>
<link href="https://fonts.googleapis.com/css2?family=Old+Standard+TT:ital,wght@0,400;0,700;1,400&display=block" rel="stylesheet">
<style>{css}</style></head><body>
<div class="p1"><div class="toprule"></div>
<h1 class="title">{title}<sup>1</sup></h1>
<div class="midrule"></div>
<div class="authors"><div>Jollen Dai</div><div>Independent</div></div>
<div class="with"><b>With</b>Apart Research</div>
<h2 class="abs">Abstract</h2>
<div class="abstract">{md(abstract)}</div>
<div style="flex:1"></div><div class="fn"><span><sup>1</sup> Research conducted at the <a href="https://apartresearch.com/sprints/ai-collusion-research-sprint-2026-10-23-to-2026-10-25">AI Collusion Research Sprint</a>, October 2026</span></div></div>
{body_html}
</body></html>"""
out = ROOT / ("report/build/body.html" if "--body-only" in sys.argv else "report/build/report.html")
out.write_text(html)
print(out)
