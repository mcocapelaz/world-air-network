#!/usr/bin/env python3
"""Degree and centrality over the OpenFlights airport network.

Reads the same two CSVs as top_airports.py (standard library only, SigV4 by
hand) and answers: which airports are barely connected (k = 1 or 2), and which
sit worst in the network.

Three measures, each answering a different question:
  · degree (k)      — how many other airports it is directly linked to, either way.
  · PageRank        — importance by *where* the routes come from, on the directed
                      graph, so a hub that is fed by other hubs scores higher.
  · betweenness     — how often it lies on the shortest path between two other
                      airports: the bridges and bottlenecks (Brandes, undirected).

    python3 airport_centrality.py
"""

import csv
import hashlib
import hmac
import io
import math
import urllib.parse
import urllib.request
from collections import Counter, defaultdict, deque

ENDPOINT = "http://localhost:9000"
BUCKET = "keasy-dev"
ACCESS_KEY = "keasy-admin"
SECRET_KEY = "keasy-admin-secret"
REGION, SERVICE = "us-east-1", "s3"


def _sign(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode(), hashlib.sha256).digest()


def get(key: str) -> str:
    host = urllib.parse.urlparse(ENDPOINT).netloc
    amz_date, date_stamp = datetime_stamp()
    payload_hash = hashlib.sha256(b"").hexdigest()
    signed_headers = "host;x-amz-content-sha256;x-amz-date"
    canonical_headers = f"host:{host}\nx-amz-content-sha256:{payload_hash}\nx-amz-date:{amz_date}\n"
    canonical_request = "\n".join(
        ["GET", "/" + urllib.parse.quote(f"{BUCKET}/{key}"), "", canonical_headers, signed_headers, payload_hash]
    )
    scope = f"{date_stamp}/{REGION}/{SERVICE}/aws4_request"
    to_sign = "\n".join(
        ["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical_request.encode()).hexdigest()]
    )
    signing_key = _sign(("AWS4" + SECRET_KEY).encode(), date_stamp)
    for part in (REGION, SERVICE, "aws4_request"):
        signing_key = _sign(signing_key, part)
    signature = hmac.new(signing_key, to_sign.encode(), hashlib.sha256).hexdigest()
    request = urllib.request.Request(
        f"{ENDPOINT}/{BUCKET}/{key}",
        headers={
            "Host": host,
            "x-amz-date": amz_date,
            "x-amz-content-sha256": payload_hash,
            "Authorization": (
                f"AWS4-HMAC-SHA256 Credential={ACCESS_KEY}/{scope}, "
                f"SignedHeaders={signed_headers}, Signature={signature}"
            ),
        },
    )
    with urllib.request.urlopen(request, timeout=120) as answer:
        return answer.read().decode("utf-8")


def datetime_stamp():
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    return now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")


airports = list(csv.DictReader(io.StringIO(get("geo/airports.csv"))))
routes = list(csv.DictReader(io.StringIO(get("geo/routes.csv"))))

airport = {a["id"]: a for a in airports}
name = {
    a["id"]: f"{a['name']} ({a['iata'] or a['icao']})" for a in airports
}
country = {a["id"]: a["country"] for a in airports}

# ── The graph ────────────────────────────────────────────────────────────────
# Undirected neighbours (who it links to at all, either way) and the directed
# edges (who it flies to) for PageRank.
neighbours = defaultdict(set)
out_edges = defaultdict(list)
for r in routes:
    src, dst = r["src"], r["dst"]
    out_edges[src].append(dst)
    neighbours[src].add(dst)
    neighbours[dst].add(src)

nodes = list(airport)
n = len(nodes)


def pagerank(damping: float = 0.85, iterations: int = 60) -> dict:
    rank = {v: 1.0 / n for v in nodes}
    out_degree = {v: len(out_edges[v]) for v in nodes}
    for _ in range(iterations):
        nxt = {}
        for v in nodes:
            links = out_edges[v]
            if links:
                share = damping * rank[v] / len(links)
                for w in links:
                    nxt[w] = nxt.get(w, 0.0) + share
            else:
                nxt[v] = nxt.get(v, 0.0) + damping * rank[v]
        dangling = (1 - damping) * sum(
            rank[v] for v in nodes if not out_edges[v]
        ) / n
        rank = {v: nxt.get(v, 0.0) + dangling for v in nodes}
    return rank


def betweenness() -> dict:
    """Brandes' algorithm on the undirected graph, unweighted."""
    score = dict.fromkeys(nodes, 0.0)
    for source in nodes:
        stack, predecessors = [], defaultdict(list)
        sigma = dict.fromkeys(nodes, 0.0)
        sigma[source] = 1.0
        distance = {source: 0}
        queue = deque([source])
        while queue:
            v = queue.popleft()
            stack.append(v)
            for w in neighbours[v]:
                if w not in distance:
                    distance[w] = distance[v] + 1
                    queue.append(w)
                if distance[w] == distance[v] + 1:
                    sigma[w] += sigma[v]
                    predecessors[w].append(v)
        delta = dict.fromkeys(nodes, 0.0)
        for w in reversed(stack):
            for v in predecessors[w]:
                delta[v] += (sigma[v] / sigma[w]) * (1 + delta[w])
            if w != source:
                score[w] += delta[w]
    # Undirected: every shortest path is counted from both ends.
    return {v: score[v] / 2 for v in nodes}


import json
import os

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "centrality.cache.json")

print(f"{len(airports):,} aeropuertos, {len(routes):,} rutas dirigidas")
if os.path.exists(CACHE):
    # Betweenness is the slow half and never changes while the CSVs do not, so
    # it is kept next to the script and reused on the next run.
    saved = json.load(open(CACHE))
    pr, bt = {k: float(v) for k, v in saved["pagerank"].items()}, saved["betweenness"]
    print("centralidades leidas de la cache (borrar centrality.cache.json para recalcular)\n")
else:
    print("calculando PageRank...", flush=True)
    pr = pagerank()
    print("calculando betweenness (puede tardar un poco)...", flush=True)
    bt = betweenness()
    json.dump({"pagerank": pr, "betweenness": bt}, open(CACHE, "w"))
    print("hecho (guardado en cache)\n")

degree = {v: len(neighbours[v]) for v in nodes}

# ── How the network is shaped ────────────────────────────────────────────────
histogram = Counter(degree.values())
buckets = [(0, "0 (aislado)"), (1, "1"), (2, "2"), (3, "3"), (4, "4"), (5, "5")]
print("Distribución del grado (k = vecinos directos, en cualquier dirección)")
print("-" * 58)
for k, label in buckets:
    count = histogram.get(k, 0)
    print(f"  k = {label:<12} {count:>5} aeropuertos  ({count / n * 100:>4.1f}%)")
tail = sum(c for k, c in histogram.items() if k > 5)
print(f"  k > 5          {tail:>5} aeropuertos")

for label, wanted in (("k = 1", 1), ("k = 2", 2)):
    group = [v for v in nodes if degree[v] == wanted]
    print("\n" + "=" * 74)
    print(f"Aeropuertos con {label}: {len(group)} en total")
    print("-" * 58)
    if not group:
        continue
    ranked = sorted(group, key=lambda v: (bt[v], pr[v]))
    for v in ranked[:8]:
        print(f"  {name[v][:44]:<44} {country[v][:20]:<20} PageRank {pr[v]:.2e}")
    worst = min(group, key=lambda v: bt[v])
    print(f"  ... y {len(group) - 8} más. Peor betweenness: "
          f"{name[worst][:36]} ({bt[worst]:.1f})")

# ── The lowest degree, worst centrality ──────────────────────────────────────
print("\n" + "=" * 74)
print("Los peores por centralidad (betweenness más bajo, con su grado)")
print("-" * 74)
print(f"{'Aeropuerto':<42} {'País':<20} {'k':>3} {'Betweenness':>12}")
for v in sorted(nodes, key=lambda v: (bt[v], pr[v]))[:10]:
    print(f"{name[v][:42]:<42} {country[v][:20]:<20} {degree[v]:>3} {bt[v]:>12.1f}")

print("\n" + "=" * 74)
print("Los 10 más centrales, para contraste")
print("-" * 74)
print(f"{'Aeropuerto':<42} {'País':<20} {'k':>3} {'Betweenness':>12}")
for v in sorted(nodes, key=lambda v: -bt[v])[:10]:
    print(f"{name[v][:42]:<42} {country[v][:20]:<20} {degree[v]:>3} {bt[v]:>12.1f}")

# ── The interesting case: low degree but load-bearing ────────────────────────
low = [v for v in nodes if degree[v] <= 2]
bridges = sorted((v for v in low if bt[v] > 0), key=lambda v: -bt[v])
print("\n" + "=" * 74)
print("De los aeropuertos con k <= 2, los que más rutas ajenas llevan entre medias")
print("(betweenness > 0: hacen de puente aunque casi no vuelan)")
print("-" * 74)
for v in bridges[:10]:
    print(f"{name[v][:42]:<42} {country[v][:20]:<20} k={degree[v]}  betweenness {bt[v]:.1f}")
if not bridges:
    print("  Ninguno: los nodos con k <= 2 no hacen de puente en esta red.")
