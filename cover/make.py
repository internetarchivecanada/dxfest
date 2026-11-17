"""Render cover/cover.html and screenshot it to cover/dxfest-cover.jpg (1200x630, like the other tiles).

    python3 cover/make.py
"""
import json
import subprocess
from pathlib import Path

here = Path(__file__).parent
root = here.parent
pub = (root / "public").resolve()
d = json.loads((root / "data" / "festival.json").read_text())
imgs = json.loads((root / "data" / "images.json").read_text())
import re
BRANDED = re.compile(r"dx-20|premiere|poster|placeholder|facebook", re.I)
films = sorted((f for f in d["films"].values() if f"f:{f['id']}" in imgs and f["years"] and not BRANDED.search(f.get("image") or "")),
               key=lambda f: -max(f["years"]))
by_year, picks = {}, []
for f in films:
    y = max(f["years"])
    if by_year.get(y, 0) < 2:
        by_year[y] = by_year.get(y, 0) + 1
        picks.append(f)
picks = picks[:18]
tiles = "".join(f'<img src="file://{pub}/{imgs["f:" + f["id"]]}">' for f in picks)
html = f"""<!doctype html><meta charset=utf-8><style>
html,body{{margin:0;width:1200px;height:630px;overflow:hidden;background:#141414;color:#f4efe6;font-family:Georgia,serif}}
.grid{{position:absolute;inset:0;display:grid;grid-template-columns:repeat(6,1fr);grid-auto-rows:210px;opacity:.38;filter:grayscale(.35) contrast(1.05)}}
.grid img{{width:100%;height:100%;object-fit:cover}}
.veil{{position:absolute;inset:0;background:linear-gradient(90deg,rgba(20,20,20,.97) 0,rgba(20,20,20,.88) 52%,rgba(20,20,20,.35) 100%)}}
.mark{{position:absolute;left:64px;top:70px;font:700 150px/1 Georgia,serif;letter-spacing:-6px;color:#f4efe6;text-shadow:9px 6px 0 rgba(224,58,47,.9)}}
h1{{position:absolute;left:66px;top:250px;margin:0;font:700 64px/1.05 Georgia,serif}}
h1 em{{font-style:italic;font-weight:400;color:#ffb3aa}}
p{{position:absolute;left:68px;top:340px;margin:0;font:26px/1.45 -apple-system,Helvetica,sans-serif;color:#ddd5c7;width:780px}}
.bar{{position:absolute;left:0;right:0;bottom:0;height:10px;background:#e03a2f}}
</style><div class=grid>{tiles}</div><div class=veil></div>
<div class=mark>DX</div><h1>Double Exposure <em>Explorer</em></h1>
<p>{len(d['films'])} films · {len(d['sessions'])} sessions · {len(d['people']):,} people<br>Twelve years of the investigative film festival, 2015–2026</p><div class=bar></div>"""
(here / "cover.html").write_text(html)
chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
png = here / "cover.png"
subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--allow-file-access-from-files",
                "--window-size=1200,630", f"--screenshot={png}", f"file://{(here / 'cover.html').resolve()}"], check=True,
               capture_output=True)
subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "82", str(png), "--out", str(here / "dxfest-cover.jpg")],
               check=True, capture_output=True)
png.unlink()
print(here / "dxfest-cover.jpg")
