#!/usr/bin/env python3
"""The one computation behind every view of this analysis.

Reads the two OpenFlights CSVs from keasy's S3 store (standard library only; the
request is signed by hand because boto3 is not installed), builds the airport
graph, and scores every airport for how fragile its connectivity is.

`compute()` returns the points, the land outline, and the numbers the page needs.
Both `vulnerability_map.py` (a static picture) and `vulnerability_story.py` (the
interactive one) are thin wrappers around it.
"""

import csv
import hashlib
import hmac
import io
import json
import os
import sys
import urllib.parse
import urllib.request
from collections import defaultdict, deque
from datetime import datetime, timezone

ENDPOINT = "http://localhost:9000"
BUCKET = "keasy-dev"
ACCESS_KEY = "keasy-admin"
SECRET_KEY = "keasy-admin-secret"
REGION, SERVICE = "us-east-1", "s3"

HERE = os.path.dirname(os.path.abspath(__file__))
BETWEENNESS_CACHE = os.path.join(HERE, "centrality.cache.json")

# The five factors of the score, and what each is worth. Stated, not measured.
WEIGHTS = {"isolation": 40, "bottleneck": 25, "remoteness": 15, "alone": 20}
TOP_HUBS = 10

# ── The palette, in one place ────────────────────────────────────────────────
# Cool means safe, warm means fragile. The low end is deliberately bright: the
# first version started at #2c7bb6, which is so close to the dark land fill that
# most of the map read as empty. It also keeps the cool/warm split, so the scale
# still reads without relying on a red-green distinction.
# The basemap is deliberately quiet so the data is the only bright thing on it:
# the sea is near-black and the landmass is a desaturated slate, well short of
# competing with any dot. The land stroke is a shade lighter than the fill so
# coastlines still read as shapes.
# The page around the map, the sea inside it, and the landmass are three
# separate things: the page keeps a dark navy so the text reads, the sea is
# pure black so the dots float on it, and the land is a coral wash that stays
# behind the data instead of competing with it.
PAGE = "#0b1220"          # the frame the whole page sits on, darker than the sea
SEA = "#2f3646"           # slate grey inside the map: it frames the map against the
                         # navy page, and it is light enough that the dark rim on every
                         # dot reads as a circle rather than vanishing into the sea
LAND = "#EFA4A461"        # coral at 38%: solid enough that the continents read as
                         # landmass, still far enough back for the dots to carry the data
LAND_STROKE = "#566584"   # a shade lighter than the fill, so coasts read as shapes

# Cool means safe, warm means fragile: the scale reads without relying on a
# red-green distinction, and the first version's dark blue vanished against the
# land, so the low end is deliberately bright.
# The cuts follow the data, not round numbers: 99% of the airports score
# between 0 and 40, so cuts at 0/20/40/60/80 left half the world in one band and
# three bands empty. These six spread it across the range the scores actually
# occupy, and the last one is for the handful that score above 60.
FRAGILITY_BANDS = [
    (0, "#00b0ff"),    # safest
    (12, "#00d2c6"),
    (24, "#ffd000"),
    (36, "#ff8a00"),
    (50, "#ff2f2f"),
    (60, "#b026ff"),   # the few that score above 60
]
MUTED_AIRPORT = "#50484A"  # every airport not in the selected set


def fragility_colour(score):
    chosen = FRAGILITY_BANDS[0][1]
    for threshold, hex_colour in FRAGILITY_BANDS:
        if score >= threshold:
            chosen = hex_colour
    return chosen


def _sign(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode(), hashlib.sha256).digest()


def get(key: str) -> str:
    """One object from the bucket, signed the way S3 expects (SigV4, GET)."""
    host = urllib.parse.urlparse(ENDPOINT).netloc
    now = datetime.now(timezone.utc)
    amz_date, date_stamp = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
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


def load():
    """The two OpenFlights CSVs.

    Reads them out of keasy's S3 store when the stack is up, and falls back to
    the copies in `data/` when it is not — so changing a colour does not require
    starting Docker. The two paths are the same bytes: `data/` is a copy of the
    `make seed` output. Set KEASY_S3=off to force the local copy.
    """
    if os.environ.get("KEASY_S3", "on").lower() == "off":
        return _load_local()
    try:
        return (
            list(csv.DictReader(io.StringIO(get("geo/airports.csv")))),
            list(csv.DictReader(io.StringIO(get("geo/routes.csv")))),
        )
    except OSError as error:
        print(f"S3 no disponible ({error}); uso la copia local en data/", file=sys.stderr)
        return _load_local()


def _load_local():
    folder = os.path.join(HERE, "data")

    def read(name):
        with open(os.path.join(folder, name), encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    return read("airports.csv"), read("routes.csv")


def build_graph(airports, routes):
    neighbours = defaultdict(set)
    for r in routes:
        neighbours[r["src"]].add(r["dst"])
        neighbours[r["dst"]].add(r["src"])
    for a in airports:
        neighbours.setdefault(a["id"], set())
    return neighbours


def cut_vertices(nodes, neighbours):
    """Tarjan, iterative: the airports whose closure would split the network."""
    discovery, low, parent, clock = {}, {}, {}, [0]
    cuts = set()
    for root in nodes:
        if root in discovery:
            continue
        root_children = 0
        discovery[root] = low[root] = clock[0]
        clock[0] += 1
        stack = [(root, iter(neighbours[root]))]
        while stack:
            v, it = stack[-1]
            descended = False
            for w in it:
                if w not in discovery:
                    parent[w] = v
                    discovery[w] = low[w] = clock[0]
                    clock[0] += 1
                    if v == root:
                        root_children += 1
                    stack.append((w, iter(neighbours[w])))
                    descended = True
                    break
                if w != parent.get(v):
                    low[v] = min(low[v], discovery[w])
            if not descended:
                stack.pop()
                if stack:
                    p = stack[-1][0]
                    low[p] = min(low[p], low[v])
                    if p != root and low[v] >= discovery[p]:
                        cuts.add(p)
        if root_children > 1:
            cuts.add(root)
    return cuts


def held_if_removed(v, neighbours):
    """How many airports fall off the network when v closes: the pieces left
    behind, ignoring the largest (the side that stays connected to the world)."""
    seen, pieces = set(), []
    for start in neighbours[v]:
        if start in seen:
            continue
        size, queue = 0, deque([start])
        seen.add(start)
        while queue:
            u = queue.popleft()
            size += 1
            for w in neighbours[u]:
                if w != v and w not in seen:
                    seen.add(w)
                    queue.append(w)
        pieces.append(size)
    return sum(pieces) - max(pieces) if pieces else 0


def hops_to_hubs(nodes, neighbours):
    """Distance to the nearest of the ten busiest airports.

    The hubs are the ten highest-degree airports. An earlier version took them
    from the betweenness cache, which made the score depend on a file that is
    not in the repository: with the cache absent every airport got `None` and
    the remoteness factor silently contributed zero to all of them. Taking the
    hubs from the degree keeps the score reproducible from the CSVs alone.
    """
    hubs = sorted(nodes, key=lambda v: (-len(neighbours[v]), v))[:TOP_HUBS]
    hops, seen = {h: 0 for h in hubs}, set(hubs)
    frontier = deque(hubs)
    while frontier:
        v = frontier.popleft()
        for w in neighbours[v]:
            if w not in seen:
                seen.add(w)
                hops[w] = hops[v] + 1
                frontier.append(w)
    return hops, hubs


def compute():
    """Every airport with its geometry, its graph metrics and its score."""
    airports, routes = load()
    airport = {a["id"]: a for a in airports}
    nodes = list(airport)
    neighbours = build_graph(airports, routes)
    cuts = cut_vertices(nodes, neighbours)
    hops, hubs = hops_to_hubs(nodes, neighbours)

    per_country = defaultdict(list)
    for a in airports:
        per_country[a["country"]].append(a["id"])
    alone_countries = {c for c, ids in per_country.items() if len(ids) == 1}

    points = []
    for v in nodes:
        a = airport[v]
        k = len(neighbours[v])
        held = held_if_removed(v, neighbours) if v in cuts else 0
        distance = hops.get(v)
        parts = {
            "isolation": WEIGHTS["isolation"] * (1 - min(k, 5) / 5),
            "bottleneck": WEIGHTS["bottleneck"] * min(held, 3) / 3,
            "remoteness": WEIGHTS["remoteness"] * min(distance, 5) / 5 if distance is not None else 0,
            "alone": WEIGHTS["alone"] if a["country"] in alone_countries else 0,
        }
        points.append(
            {
                "id": v,
                "name": a["name"],
                "code": a["iata"] or a["icao"] or a["id"],
                "city": a["city"],
                "country": a["country"],
                "lon": float(a["lon"]),
                "lat": float(a["lat"]),
                "altitude": a["altitude"],
                "k": k,
                "held": held,
                "hops": distance,
                "alone": a["country"] in alone_countries,
                "cut": v in cuts,
                "score": min(100, round(sum(parts.values()))),
                "parts": {k2: round(v2, 1) for k2, v2 in parts.items()},
            }
        )

    points.sort(key=lambda p: (-p["score"], p["name"]))
    return {
        "points": points,
        "airports": len(airports),
        "routes": len(routes),
        "countries": len(per_country),
        "single_airport_countries": len(alone_countries),
        "cuts": len(cuts),
        "weights": WEIGHTS,
        "hubs": [{"name": airport[h]["name"], "code": airport[h]["iata"] or airport[h]["icao"]} for h in hubs],
    }


def land_paths(path=None, width=1200, lat0=-58.0, lat1=84.0, lon0=-180.0, lon1=180.0):
    """The world outline as SVG path data in the same projection as the map."""
    geojson = json.load(open(path or os.path.join(HERE, "land110.json")))
    height = round(width * (lat1 - lat0) / (lon1 - lon0))
    shapes = []
    for feature in geojson["features"]:
        geometry = feature["geometry"]
        polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
        for polygon in polygons:
            for ring in polygon:
                if len(ring) < 3:
                    continue
                d = " ".join(
                    ("M" if i == 0 else "L") + "%.1f %.1f" % (project(lon, lat, width, lat0, lat1, lon0, lon1))
                    for i, (lon, lat) in enumerate(ring)
                    if lat0 - 5 <= lat <= lat1 + 5
                )
                if len(d) > 12:
                    shapes.append(d + "Z")
    return shapes, width, height


def project(lon, lat, width=1200, lat0=-58.0, lat1=84.0, lon0=-180.0, lon1=180.0):
    return ((lon - lon0) / (lon1 - lon0) * width, (lat1 - lat) / (lat1 - lat0) * round(width * (lat1 - lat0) / (lon1 - lon0)))
