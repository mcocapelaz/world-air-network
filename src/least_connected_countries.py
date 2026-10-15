#!/usr/bin/env python3
"""The least connected countries in the world, on a map.

The other views score single airports. This one goes one level up: it ranks
countries by how many routes their airports send in total, and puts them on the
world map. Same score-free metric (routes actually flown), same self-contained
HTML, same styling as the rest.

    python3 least_connected_countries.py
"""

import json
import os
from collections import defaultdict

from vuln_core import (LAND, LAND_STROKE as STROKE, MUTED_AIRPORT, PAGE, SEA,
                        compute, land_paths, project)

HERE = os.path.dirname(os.path.abspath(__file__))
airports, routes = load = None, None

from vuln_core import load  # noqa: E402

airports, routes = load()
data = compute()
shapes, W, H = land_paths(os.path.join(HERE, "land110.json"))

by_id = {a["id"]: a for a in airports}
out_degree = defaultdict(int)
for r in routes:
    out_degree[r["src"]] += 1

# Per country: how much air service it sends out, and how spread it is.
stats = defaultdict(lambda: {"airports": 0, "routes": 0, "lat": 0.0, "lon": 0.0, "ids": []})
for a in airports:
    s = stats[a["country"]]
    s["airports"] += 1
    s["routes"] += out_degree[a["id"]]
    s["lat"] += float(a["lat"])
    s["lon"] += float(a["lon"])
    s["ids"].append(a["id"])

countries = []
for name, s in stats.items():
    countries.append({
        "c": name,
        "a": s["airports"],
        "r": s["routes"],
        "per": round(s["routes"] / s["airports"], 1),
        "lat": s["lat"] / s["airports"],
        "lon": s["lon"] / s["airports"],
        "ids": s["ids"],
    })

by_least = sorted(countries, key=lambda c: (c["r"], c["c"]))
by_most = sorted(countries, key=lambda c: (-c["r"], c["c"]))

payload = {
    "rows": [{k: v for k, v in c.items() if k != "ids"} for c in countries],
    "least": [c["c"] for c in by_least[:30]],
    "most": [c["c"] for c in by_most[:30]],
}

# Every airport on the map, muted: the ones of the selected countries stand out.
dots, labels = [], []
for a in airports:
    x, y = project(float(a["lon"]), float(a["lat"]), W)
    dots.append(
        f'<circle class="d" data-c="{a["country"]}" data-i="{a["id"]}" cx="{x:.1f}" cy="{y:.1f}" '
        f'r="2.5" fill="{MUTED_AIRPORT}"><title>{a["name"]} — {a["country"]}</title></circle>'
    )

for c in by_least[:30] + by_most[:30]:
    x, y = project(c["lon"], c["lat"], W)
    labels.append(
        f'<text class="lb" data-c="{c["c"]}" x="{x:.1f}" y="{y:.1f}">{c["c"]}</text>'
    )

rank_of = {c["c"]: i + 1 for i, c in enumerate(by_least)}
worst = by_least[0]
best = by_most[0]

html = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Qui&eacute;n queda fuera &middot; los pa&iacute;ses menos conectados</title>
<style>
  :root {{ --bg:{PAGE}; --panel:#111c2f; --line:#1e293b; --ink:#e2e8f0; --mut:#94a3b8; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink); padding:28px 30px 70px;
         font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
  h1 {{ margin:0 0 6px; font-size:24px; font-weight:650; letter-spacing:-.2px; }}
  .sub {{ color:var(--mut); margin:0; font-size:14px; max-width:800px; }}
  .stat {{ display:flex; gap:30px; flex-wrap:wrap; margin:20px 0 4px; padding:14px 0;
           border-block:1px solid var(--line); }}
  .stat div {{ font-size:13px; color:var(--mut); }}
  .stat b {{ display:block; font-size:22px; color:var(--ink); font-weight:650; }}
  .tools {{ display:flex; flex-wrap:wrap; gap:10px; align-items:center; margin:16px 0 12px; }}
  .chip {{ padding:7px 12px; border-radius:999px; border:1px solid var(--line);
           cursor:pointer; font-size:13px; color:var(--mut); user-select:none; }}
  .chip:hover {{ border-color:#334155; color:var(--ink); }}
  .chip.on {{ background:#1e3a5f; border-color:#2b5c8f; color:#dbeafe; }}
  .count {{ margin-left:auto; color:var(--mut); font-size:13px; }}
  .grid {{ display:grid; grid-template-columns:1fr 380px; gap:0; align-items:start; }}
  @media (max-width:1080px) {{ .grid {{ grid-template-columns:1fr; }} }}
  .mapwrap {{ position:relative; padding:10px 10px 16px 0; }}
  svg {{ width:100%; height:auto; display:block; }}
  .land {{ fill:{LAND}; stroke:{STROKE}; stroke-width:.5; }}
  .d {{ opacity:.55; }}
  .d.hi {{ fill:#f97316; opacity:1; }}
  .lb {{ font:9.5px -apple-system,sans-serif; fill:#64748b; text-anchor:middle;
         paint-order:stroke; stroke:{SEA}; stroke-width:2.6px; stroke-linejoin:round; }}
  .lb.hi {{ fill:#fed7aa; font-weight:600; }}
  .lg {{ position:absolute; left:14px; top:14px; background:#0b1220dd; border:1px solid var(--line);
         border-radius:8px; padding:9px 12px; font-size:12px; }}
  .lg i {{ display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:6px;
           vertical-align:-1px; }}
  aside {{ border-left:1px solid var(--line); padding:14px 20px 30px; max-height:80vh;
           overflow:auto; position:sticky; top:16px; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  th {{ text-align:left; color:var(--mut); font-weight:500; padding:6px 3px; cursor:pointer;
        border-bottom:1px solid var(--line); position:sticky; top:0; background:var(--bg); }}
  th:hover {{ color:var(--ink); }}
  td {{ padding:5px 3px; border-bottom:1px solid #16203a; }}
  tr.r {{ cursor:pointer; }}
  tr.r:hover td {{ background:#152038; }}
  tr.r.sel td {{ background:#1e3a5f; }}
  .n {{ max-width:150px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
  .sc {{ text-align:right; font-variant-numeric:tabular-nums; }}
  footer {{ margin-top:24px; color:var(--mut); font-size:13px; max-width:880px; }}
  code {{ background:#111c2f; padding:1px 5px; border-radius:3px; }}
</style></head><body>

<h1>Qui&eacute;n queda fuera</h1>
<p class="sub">Los {len(countries)} pa&iacute;ses del subconjunto, ordenados por el n&uacute;mero de rutas
a&eacute;reas que env&iacute;an sus aeropuertos. Cada punto del mapa es un aeropuerto; los naranjas
pertenecen a los pa&iacute;ses destacados.</p>

<div class="stat">
  <div><b>{worst['c']}</b>{worst['r']} rutas &middot; {worst['a']} aeropuerto(s)</div>
  <div><b>{best['c']}</b>{best['r']:,} rutas &middot; {best['a']} aeropuerto(s)</div>
  <div><b>{worst['r']}</b>rutas del pa&iacute;s menos conectado</div>
  <div><b>{len(countries)}</b>pa&iacute;ses en el subconjunto</div>
</div>

<div class="tools">
  <span class="chip on" data-v="least">Los 30 menos conectados</span>
  <span class="chip" data-v="most">Los 30 m&aacute;s conectados</span>
  <span class="chip" data-v="none">Ver todos</span>
  <span class="chip" data-f="single">Solo pa&iacute;ses de un solo aeropuerto</span>
  <span class="count" id="count"></span>
</div>

<div class="grid">
  <div class="mapwrap">
    <svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">
      <rect width="{W}" height="{H}" fill="{SEA}"></rect>
      <g class="land">{''.join(f'<path d="{d}"/>' for d in shapes)}</g>
      <g id="dots">{''.join(dots)}</g>
      <g id="labels">{''.join(labels)}</g>
    </svg>
    <div class="lg">
      <div><i style="background:#f97316"></i>pa&iacute;s destacado</div>
      <div style="margin-top:4px"><i style="background:{MUTED_AIRPORT}"></i>resto de aeropuertos</div>
    </div>
  </div>
  <aside>
    <table>
      <thead><tr>
        <th data-s="c">Pa&iacute;s</th><th data-s="r" class="sc">Rutas</th>
        <th data-s="a" class="sc">Aerop.</th><th data-s="per" class="sc">Por aerop.</th>
      </tr></thead>
      <tbody id="rows"></tbody>
    </table>
  </aside>
</div>

<footer>
  <p><b>Qu&eacute; mide «rutas».</b> El n&uacute;mero de vuelos dirigidos que salen de los aeropuertos de
  cada pa&iacute;s, en el subconjunto de {data['airports']:,} aeropuertos y {data['routes']:,} rutas. No es una
  medida de capacidad (asientos) ni de calidad: es)&aacute;ntamente el volumen de enlaces disponibles.</p>
  <p><b>Cuidado al comparar.</b> El total favorece a los pa&iacute;ses grandes y populated: para ver la
  intensidad por tama&ntilde;o, la cuarta columna divide entre el n&uacute;mero de aeropuertos. Un pa&iacute;s con
  un solo aeropuerto muy conectado (Qatar) tiene total bajo y media alta.</p>
  <p><b>Fuente.</b> OpenFlights (ODbL), subconjunto derivado por <code>make seed</code>. Base est&aacute;tica
  con cobertura desigual: la estructura es v&aacute;lida, las cifras exactas de rutas por pa&iacute;s no.</p>
</footer>

<script>
const DATA = {json.dumps(payload, ensure_ascii=False, separators=(",", ":"))};
const state = {{ view: "least", single: false, sort: "r", sel: null }};

function ranked() {{
  const list = DATA.rows.filter(r => !state.single || r.a === 1);
  if (state.sort === "c") list.sort((a, b) => a.c.localeCompare(b.c));
  else if (state.sort === "a") list.sort((a, b) => a.a - b.a || b.r - a.r);
  else if (state.sort === "per") list.sort((a, b) => a.per - b.per || a.r - b.r);
  else if (state.view === "most") list.sort((a, b) => b.r - a.r || a.c.localeCompare(b.c));
  else list.sort((a, b) => a.r - b.r || a.c.localeCompare(b.c));
  return list;
}}

function render() {{
  const list = ranked();
  const highlight = new Set(state.view === "none" ? [] : DATA[state.view]);
  document.getElementById('count').textContent =
    highlight.size + " pa&iacute;ses destacados";
  document.querySelectorAll('.d').forEach(d =>
    d.classList.toggle('hi', highlight.has(d.dataset.c)));
  document.querySelectorAll('.lb').forEach(t =>
    t.classList.toggle('hi', highlight.has(t.dataset.c)));
  document.getElementById('rows').innerHTML = list.slice(0, 300).map(r => `
    <tr class="r${{state.sel === r.c ? " sel" : ""}}" data-c="${{r.c}}">
      <td class="n" title="${{r.c}}">${{highlight.has(r.c) ? "● " : ""}}${{r.c}}</td>
      <td class="sc">${{r.r}}</td>
      <td class="sc mut">${{r.a}}</td>
      <td class="sc mut">${{r.per}}</td>
    </tr>`).join("");
}}

document.querySelectorAll('.chip[data-v]').forEach(chip => chip.addEventListener('click', () => {{
  state.view = chip.dataset.v;
  document.querySelectorAll('.chip[data-v]').forEach(c => c.classList.toggle('on', c === chip));
  render();
}}));
document.querySelector('.chip[data-f]').addEventListener('click', e => {{
  state.single = !state.single;
  e.currentTarget.classList.toggle('on', state.single);
  render();
}});
document.querySelectorAll('th[data-s]').forEach(th => th.addEventListener('click', () => {{
  state.sort = th.dataset.s; render();
}}));
document.addEventListener('click', e => {{
  const row = e.target.closest('tr.r');
  if (row) {{ state.sel = row.dataset.c; render(); }}
}});
render();
</script>
</body></html>"""

out = os.path.join(HERE, "least-connected.html")
open(out, "w").write(html)
print(f"escrito {out} ({os.path.getsize(out) / 1024:.0f} KB)")
print(f"{len(countries)} países; menos conectado {worst['c']} ({worst['r']}); "
      f"más conectado {best['c']} ({best['r']})")
print("\nLos 12 menos conectados:")
for c in by_least[:12]:
    print(f"  {c['r']:>4} rutas  {c['a']:>3} aeroport(s)  {c['c']}")