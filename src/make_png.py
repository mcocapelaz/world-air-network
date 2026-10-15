#!/usr/bin/env python3
"""Render the least-connected-countries map as a publication PNG.

A static, English, print-shaped version of the interactive map: no controls, no
table to scroll — the map with the highlighted countries, a ranked bar list
beside it, and the source note. Written as HTML and rasterised with headless
Chrome, so no image library is needed.

    python3 make_png.py [output.png]
"""

import json
import os
import subprocess
import sys
from collections import defaultdict

from vuln_core import (BACKGROUND as BG, LAND, LAND_STROKE as STROKE, MUTED_AIRPORT,
                        compute, land_paths, load, project)

HERE = os.path.dirname(os.path.abspath(__file__))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
HIGHLIGHT = 20  # countries drawn in orange and labelled on the map
LISTED = 20     # rows in the ranking panel

# Map labels are too long for the space a dot occupies; these read better.
SHORT = {
    "American Samoa": "American Samoa",
    "Cocos (Keeling) Islands": "Cocos (Keeling)",
    "Falkland Islands": "Falklands",
    "Saint Pierre and Miquelon": "St. Pierre & Miquelon",
    "Sao Tome and Principe": "Sao Tome & Principe",
    "Central African Republic": "Central African Rep.",
    "Christmas Island": "Christmas I.",
    "Norfolk Island": "Norfolk I.",
    "East Timor": "East Timor",
}

airports, routes = load()
data = compute()
shapes, W, H = land_paths(os.path.join(HERE, "land110.json"))

out_degree = defaultdict(int)
for r in routes:
    out_degree[r["src"]] += 1

stats = defaultdict(lambda: {"a": 0, "r": 0, "lat": 0.0, "lon": 0.0})
for a in airports:
    s = stats[a["country"]]
    s["a"] += 1
    s["r"] += out_degree[a["id"]]
    s["lat"] += float(a["lat"])
    s["lon"] += float(a["lon"])

countries = [
    {"c": name, "a": s["a"], "r": s["r"], "lat": s["lat"] / s["a"], "lon": s["lon"] / s["a"]}
    for name, s in stats.items()
]
by_least = sorted(countries, key=lambda c: (c["r"], c["c"]))
by_most = sorted(countries, key=lambda c: -c["r"])
highlight = {c["c"] for c in by_least[:HIGHLIGHT]}
worst, best = by_least[0], by_most[0]

dots = []
for a in airports:
    x, y = project(float(a["lon"]), float(a["lat"]), W)
    on = a["country"] in highlight
    dots.append(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{2.8 if on else 2.1}" '
        f'fill="{"#fb923c" if on else MUTED_AIRPORT}" opacity="{1 if on else .7}"/>'
    )

labels = []
placed = []
for c in by_least[:HIGHLIGHT]:
    x, y = project(c["lon"], c["lat"], W)
    # Keep the name inside the frame: Tuvalu sits on the antimeridian and would
    # otherwise be sliced in half by the edge of the map.
    x = max(46, min(W - 46, x))
    # Nudge apart labels that land on the same spot (the Pacific microstates).
    while any(abs(x - px) < 62 and abs(y - py) < 11 for px, py in placed):
        y += 12
        if y > H - 6:
            y -= 24
    placed.append((x, y))
    name = SHORT.get(c["c"], c["c"])
    if len(name) > 24:
        name = name[:23] + "…"
    labels.append(f'<text class="lb" x="{x:.1f}" y="{y:.1f}">{name}</text>')

peak = by_least[LISTED - 1]["r"] or 1
rows = []
for i, c in enumerate(by_least[:LISTED], 1):
    width = max(2.5, c["r"] / peak * 100)
    name = SHORT.get(c["c"], c["c"])
    if len(name) > 27:
        name = name[:26] + "…"
    rows.append(
        f'<div class="row"><span class="rk">{i}</span>'
        f'<span class="nm" title="{c["c"]}">{name}</span>'
        f'<span class="tr"><span class="fl" style="width:{width:.1f}%"></span></span>'
        f'<span class="vl">{c["r"]}</span></div>'
    )

html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<style>
  * {{ box-sizing:border-box; margin:0; }}
  body {{ width:1880px; background:{BG}; color:#e2e8f0; padding:34px 38px 26px;
         font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,sans-serif; }}
  h1 {{ font-size:33px; font-weight:650; letter-spacing:-.5px; }}
  .sub {{ color:#94a3b8; font-size:15.5px; margin-top:5px; max-width:1100px; }}
  .cols {{ display:grid; grid-template-columns:1fr 470px; gap:26px; margin-top:20px; }}
  .land {{ fill:{LAND}; stroke:{STROKE}; stroke-width:.5; }}
  .lb {{ font:10.5px -apple-system,sans-serif; fill:#fcd9b6; text-anchor:middle;
         paint-order:stroke; stroke:{BG}; stroke-width:3px; stroke-linejoin:round; }}
  .lg {{ display:flex; gap:18px; margin-top:8px; font-size:12.5px; color:#94a3b8; }}
  .lg i {{ display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:6px;
           vertical-align:0; }}
  .panel {{ border:1px solid #1e293b; border-radius:10px; padding:16px 18px 12px; background:#0e1929; }}
  .panel h2 {{ font-size:14px; font-weight:600; color:#94a3b8; text-transform:uppercase;
               letter-spacing:.7px; margin-bottom:12px; }}
  .row {{ display:flex; align-items:center; gap:8px; height:22px; }}
  .rk {{ width:16px; color:#64748b; font-size:11.5px; font-variant-numeric:tabular-nums; }}
  .nm {{ width:168px; font-size:13px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
  .tr {{ flex:1; height:9px; background:#16213a; border-radius:3px; overflow:hidden; }}
  .fl {{ display:block; height:100%; background:#f97316; border-radius:3px; }}
  .vl {{ width:34px; text-align:right; font-size:13px; color:#cbd5e1; font-variant-numeric:tabular-nums; }}
  .kpis {{ display:flex; gap:12px; margin-top:14px; padding-top:13px; border-top:1px solid #1e293b; }}
  .kpis div {{ flex:1; font-size:11.5px; color:#94a3b8; }}
  .kpis b {{ display:block; color:#e2e8f0; font-size:19px; font-weight:650; margin-bottom:1px; }}
  footer {{ margin-top:18px; padding-top:13px; border-top:1px solid #1e293b;
            color:#7c8ba1; font-size:12.5px; display:flex; gap:34px; }}
  footer span {{ max-width:640px; }}
  footer b {{ color:#94a3b8; font-weight:600; }}
</style></head><body>

<h1>The least connected countries in the world</h1>
<p class="sub">Of the {len(countries)} countries in this OpenFlights subset, these {HIGHLIGHT} have the
fewest outbound air routes. Every airport is plotted at its real position; the orange ones belong to
the highlighted countries.</p>

<div class="cols">
  <div>
    <svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto">
      <rect width="{W}" height="{H}" fill="{BG}"/>
      <g class="land">{''.join(f'<path d="{d}"/>' for d in shapes)}</g>
      <g>{''.join(dots)}</g>
      <g>{''.join(labels)}</g>
    </svg>
    <div class="lg">
      <span><i style="background:#f97316"></i>{HIGHLIGHT} least connected countries</span>
      <span><i style="background:{MUTED_AIRPORT}"></i>every other airport ({len(airports):,} in total)</span>
    </div>
  </div>

  <div>
    <div class="panel">
      <h2>Outbound routes by country</h2>
      {''.join(rows)}
      <div class="kpis">
        <div><b>{worst['r']}</b>routes &middot; {worst['c']}</div>
        <div><b>{best['r']:,}</b>routes &middot; {best['c']}</div>
        <div><b>{len(countries)}</b>countries</div>
      </div>
    </div>
  </div>
</div>

<footer>
  <span><b>What "routes" means.</b> Directed flights departing from the airports of each country.
  It is a count of available links, not of seat capacity or service quality.</span>
  <span><b>Source.</b> OpenFlights (ODbL), subset derived from the LDBC/OpenFlights download.
  Static dataset with uneven coverage: the structure holds, exact per-country counts should not be
  cited as hard figures.</span>
</footer>
</body></html>"""

tmp = os.path.join(HERE, "_render.html")
open(tmp, "w").write(html)

target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "least-connected-countries.png")
if os.path.exists(target):
    os.remove(target)

subprocess.run(
    [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
     "--force-device-scale-factor=2", "--window-size=1880,880",
     f"--screenshot={target}", "file://" + tmp],
    check=True, capture_output=True,
)
os.remove(tmp)
print(f"escrito {target} ({os.path.getsize(target) / 1024:.0f} KB)")