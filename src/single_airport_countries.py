#!/usr/bin/env python3
"""The 69 countries that depend on a single airport, ranked by fragility.

A companion to vulnerability-story.html: the same score, but read as a chart
instead of a map — because the point it makes is a comparison, not a location.
One self-contained file, no server, no internet.

    python3 single_airport_countries.py
"""

import json
import os

from vuln_core import BACKGROUND as BG, compute, fragility_colour

HERE = os.path.dirname(os.path.abspath(__file__))

data = compute()
rows = [p for p in data["points"] if p["alone"]]
rows.sort(key=lambda p: -p["score"])

payload = [
    {"c": p["country"], "n": p["name"], "cd": p["code"], "s": p["score"], "k": p["k"],
     "h": p["held"], "o": p["hops"], "lat": p["lat"], "lon": p["lon"], "pt": p["parts"]}
    for p in rows
]

worst, best = rows[0], rows[-1]
median = sorted(p["score"] for p in rows)[len(rows) // 2]

html = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Un pa&iacute;s, un aeropuerto</title>
<style>
  :root {{ --bg:{BG}; --panel:#111c2f; --line:#1e293b; --ink:#e2e8f0; --mut:#94a3b8; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink); padding:28px 30px 70px;
         font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
  h1 {{ margin:0 0 6px; font-size:24px; font-weight:650; letter-spacing:-.2px; }}
  .sub {{ color:var(--mut); margin:0 0 4px; font-size:14px; max-width:760px; }}
  .lead {{ color:var(--mut); font-size:14px; margin:14px 0 0; max-width:820px;
           border-left:2px solid #2b5c8f; padding-left:14px; }}
  .lead b {{ color:var(--ink); }}
  .tools {{ display:flex; flex-wrap:wrap; gap:10px; align-items:center;
            margin:22px 0 14px; padding-bottom:14px; border-bottom:1px solid var(--line); }}
  .chip {{ padding:7px 12px; border-radius:999px; border:1px solid var(--line);
           cursor:pointer; font-size:13px; color:var(--mut); user-select:none; }}
  .chip:hover {{ border-color:#334155; color:var(--ink); }}
  .chip.on {{ background:#1e3a5f; border-color:#2b5c8f; color:#dbeafe; }}
  .count {{ margin-left:auto; color:var(--mut); font-size:13px; }}
  .chart {{ display:flex; align-items:center; gap:12px; padding:3px 0; cursor:pointer;
            border-radius:4px; }}
  .chart:hover {{ background:#152038; }}
  .chart.sel {{ background:#1e3a5f; }}
  .cname {{ width:230px; flex:none; font-size:13.5px; overflow:hidden;
            text-overflow:ellipsis; white-space:nowrap; }}
  .track {{ flex:1; height:17px; background:#101b2e; border-radius:3px; position:relative; }}
  .fill {{ position:absolute; inset:0 auto 0 0; border-radius:3px; }}
  .kmark {{ position:absolute; top:-3px; bottom:-3px; width:2px; background:#fbbf24;
            opacity:.85; }}
  .score {{ width:34px; flex:none; text-align:right; font-variant-numeric:tabular-nums;
            font-size:13px; color:var(--mut); }}
  .hint {{ font-size:11.5px; color:#64748b; margin:4px 0 16px 242px; }}
  .panel {{ position:sticky; bottom:0; margin-top:26px; background:var(--panel);
            border:1px solid var(--line); border-radius:10px; padding:16px 18px; }}
  .panel h2 {{ margin:0 0 2px; font-size:16px; }}
  .panel .co {{ color:var(--mut); font-size:13px; margin-bottom:12px; }}
  .parts {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:10px 22px; }}
  .part .l {{ color:var(--mut); font-size:12px; }}
  .part .t {{ height:6px; background:#16213a; border-radius:4px; overflow:hidden; margin:4px 0 3px; }}
  .part .f {{ height:100%; background:#60a5fa; }}
  .part .v {{ font-variant-numeric:tabular-nums; font-size:13px; }}
  footer {{ margin-top:26px; color:var(--mut); font-size:13px; max-width:860px; }}
  code {{ background:#111c2f; padding:1px 5px; border-radius:3px; }}
</style></head><body>

<h1>Un pa&iacute;s, un aeropuerto</h1>
<p class="sub">{len(rows)} de los {data['countries']} pa&iacute;ses del subconjunto dependen de un solo
aeropuerto: si &eacute;ste cierra, el pa&iacute;s se queda sin conexi&oacute;n a&eacute;rea internacional.
Ordenados por lo fr&aacute;gil que queda cada uno.</p>

<p class="lead">Tener un solo aeropuerto <b>no</b> implica ser vulnerable. Letonia tiene uno solo y
 punt&uacute;a {best['score']}; Tuvalu tambi&eacute;n, y punt&uacute;a {worst['score']}. La diferencia no est&aacute;
 en el n&uacute;mero de|del aeropuerto del pa&iacute;s, sino en <b>d&oacute;nde est&aacute;</b>: si est&aacute; bien conectado a la red,
 cerrarlo duele poco. La barra marca en amarillo el n&uacute;mero de enlaces directos del aeropuerto.</p>

<div class="tools">
  <span class="chip" data-s="s">Ordenar por vulnerabilidad</span>
  <span class="chip" data-s="k">Ordenar por enlaces</span>
  <span class="chip" data-s="c">Ordenar alfab&eacute;ticamente</span>
  <span class="chip" data-f="thin">Solo con 2 enlaces o menos</span>
  <span class="count" id="count"></span>
</div>

<p class="hint">Pasa el rat&oacute;n o pulsa una fila para ver el desglose.</p>
<div id="chart"></div>

<div class="panel" id="panel">
  <div class="co">Elige un pa&iacute;s</div>
</div>

<footer>
  <p><b>C&oacute;mo se calcula.</b> Heur&iacute;stica declarada: aislamiento
  {data['weights']['isolation']} pts &middot; cuello de botella {data['weights']['bottleneck']} pts &middot;
  lejan&iacute;a {data['weights']['remoteness']} pts &middot; sin alternativa {data['weights']['alone']} pts.
  Los 20 pts de «sin alternativa» los ganan todos los de esta lista: lo que los diferencia es el resto.</p>
  <p><b>Fuente.</b> OpenFlights (ODbL), subconjunto de {data['airports']:,} aeropuertos y
  {data['routes']:,} rutas. Base est&aacute;tica: sirve para leer la estructura, no para decidir.</p>
</footer>

<script>
const BANDS = [[0,"#38bdf8"],[20,"#22d3ee"],[40,"#facc15"],[60,"#fb923c"],[80,"#ef4444"]];
const fragility_colour = s => {{ let c = BANDS[0][1]; for (const [t, h] of BANDS) if (s >= t) c = h; return c; }};
const ROWS = {json.dumps(payload, ensure_ascii=False, separators=(",", ":"))};
const state = {{ sort: "s", thin: false, sel: null }};

function colour(s) {{
  return s >= 80 ? "#d7191c" : s >= 60 ? "#fdae61" : s >= 40 ? "#ffffbf" : s >= 20 ? "#abd9e9" : "#2c7bb6";
}}
function pick() {{
  const list = ROWS.filter(r => !state.thin || r.k <= 2);
  if (state.sort === "s") list.sort((a, b) => b.s - a.s || a.c.localeCompare(b.c));
  if (state.sort === "k") list.sort((a, b) => a.k - b.k || b.s - a.s);
  if (state.sort === "c") list.sort((a, b) => a.c.localeCompare(b.c));
  return list;
}}
function show(r) {{
  state.sel = r.c;
  document.querySelectorAll('.chart').forEach(el =>
    el.classList.toggle('sel', el.dataset.c === r.c));
  const parts = [
    ["Aislamiento", r.pt.isolation, 40], ["Cuello de botella", r.pt.bottleneck, 25],
    ["Lejan&iacute;a", r.pt.remoteness, 15], ["Sin alternativa", r.pt.alone, 20],
  ];
  document.getElementById('panel').innerHTML = `
    <h2>${{r.c}}</h2>
    <div class="co">${{r.n}} (${{r.cd}}) &middot; ${{r.k}} enlace(s) directo(s)
      ${{r.h ? ` &middot; si cierra, a&iacute;sla ${{r.h}} aeropuerto(s)` : ""}}
      ${{r.o !== null ? ` &middot; a ${{r.o}} salto(s) del hub m&aacute;s cercano` : ""}}
      &middot; ${{r.lat.toFixed(2)}}, ${{r.lon.toFixed(2)}}</div>
    <div class="parts">${{parts.map(([l, v, max]) => `
      <div class="part"><div class="l">${{l}}</div>
        <div class="t"><div class="f" style="width:${{v / max * 100}}%"></div></div>
        <div class="v">${{v}} de ${{max}}</div></div>`).join("")}}
      <div class="part"><div class="l">Puntuaci&oacute;n final</div>
        <div class="t"><div class="f" style="width:${{r.s}}%;background:${{colour(r.s)}}"></div></div>
        <div class="v"><b>${{r.s}}</b> de 100</div></div>
    </div>`;
}}
function render() {{
  const list = pick();
  document.getElementById('count').textContent =
    list.length + " de " + ROWS.length + " países";
  document.getElementById('chart').innerHTML = list.map(r => `
    <div class="chart${{state.sel === r.c ? " sel" : ""}}" data-c="${{r.c}}">
      <div class="cname" title="${{r.c}}">${{r.c}}</div>
      <div class="track">
        <div class="fill" style="width:${{r.s}}%;background:${{colour(r.s)}}"></div>
        <div class="kmark" style="left:${{Math.min(r.k, 100)}}%" title="${{r.k}} enlaces"></div>
      </div>
      <div class="score">${{r.s}}</div>
    </div>`).join('');
}}
document.querySelectorAll('.chip').forEach(chip => chip.addEventListener('click', () => {{
  if (chip.dataset.s) {{
    state.sort = chip.dataset.s;
    document.querySelectorAll('.chip[data-s]').forEach(c => c.classList.toggle('on', c === chip));
  }} else {{
    state.thin = !state.thin;
    chip.classList.toggle('on', state.thin);
  }}
  render();
}}));
document.addEventListener('click', e => {{
  const row = e.target.closest('.chart');
  if (row) show(ROWS.find(r => r.c === row.dataset.c));
}});
render();
</script>
</body></html>"""

out = os.path.join(HERE, "single-airport.html")
open(out, "w").write(html)
print(f"escrito {out} ({os.path.getsize(out) / 1024:.0f} KB)")
print(f"{len(rows)} países de un solo aeropuerto; mediana de vulnerabilidad {median}")
print(f"peor  : {worst['country']} ({worst['code']}) k={worst['k']} -> {worst['score']}")
print(f"mejor : {best['country']} ({best['code']}) k={best['k']} -> {best['score']}")