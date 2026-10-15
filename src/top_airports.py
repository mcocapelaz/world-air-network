#!/usr/bin/env python3
"""Top 10 countries by number of airports, read straight from the S3 store.

Only the standard library: the CSVs are fetched from SeaweedFS with a
hand-rolled AWS SigV4 signature, because boto3 is not installed.

    python3 top_airports.py
"""

import csv
import hashlib
import hmac
import io
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone

ENDPOINT = "http://localhost:9000"
BUCKET = "keasy-dev"
ACCESS_KEY = "keasy-admin"
SECRET_KEY = "keasy-admin-secret"
REGION = "us-east-1"
SERVICE = "s3"


def _sign(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode(), hashlib.sha256).digest()


def get(key: str) -> str:
    """One object from the bucket, signed the way S3 expects (SigV4, GET, no body)."""
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


airports = list(csv.DictReader(io.StringIO(get("geo/airports.csv"))))
routes = list(csv.DictReader(io.StringIO(get("geo/routes.csv"))))

print(f"{len(airports):,} aeropuertos y {len(routes):,} rutas\n")

print("Top 10 países por número de aeropuertos")
print("-" * 46)
for rank, (country, count) in enumerate(Counter(a["country"] for a in airports).most_common(10), 1):
    print(f"{rank:>2}. {country:<32} {count:>5}")

print("\nTop 10 aeropuertos por número de rutas directas")
print("-" * 52)
by_code = {a["id"]: f"{a['name']} ({a['iata'] or a['icao'] or a['id']})" for a in airports}
departures = Counter(r["src"] for r in routes)
for rank, (code, count) in enumerate(departures.most_common(10), 1):
    print(f"{rank:>2}. {by_code.get(code, code):<44} {count:>5}")

# ── The other end: the least connected countries ────────────────────────────
country_of = {a["id"]: a["country"] for a in airports}
airports_per_country = Counter(a["country"] for a in airports)
routes_per_country = Counter()
for r in routes:
    routes_per_country[country_of.get(r["src"], "?")] += 1

fewest = airports_per_country.most_common()[:-11:-1]
print(f"\n10 países con menos aeropuertos (de {len(airports_per_country)} con alguno)")
print("-" * 56)
for rank, (country, count) in enumerate(fewest, 1):
    print(f"{rank:>2}. {country:<32} {count:>5} aeropuerto(s), {routes_per_country[country]:>4} ruta(s)")

# A country with one airport is trivially last, so the second list asks for real
# connection: countries that have routes, fewest first.
with_routes = [(c, n) for c, n in routes_per_country.items() if n > 0 and c != "?"]
with_routes.sort(key=lambda pair: pair[1])
print("\n10 países con menos rutas directas, de los que tienen alguna")
print("-" * 62)
for rank, (country, count) in enumerate(with_routes[:10], 1):
    print(f"{rank:>2}. {country:<32} {count:>5} ruta(s), {airports_per_country[country]:>3} aeropuerto(s)")

solo_uno = sum(1 for n in airports_per_country.values() if n == 1)
print(f"\nNota: {solo_uno} países tienen un solo aeropuerto, y "
      f"{sum(1 for n in routes_per_country.values() if n == 0)} no tienen ninguna ruta que salga de ellos.")

# ── Mega-hubs, and how concentrated each country is on its own hub ──────────
# A route is directed and counted at its origin, so "routes" below is departures.
# The index is the Herfindahl-Hirschman over the country's airports: the sum of
# each airport's squared share of the country's departures, on the usual 0-10000
# scale. Below 1500 is unconcentrated, above 2500 highly concentrated.
airport = {a["id"]: a for a in airports}
routes_of = Counter(r["src"] for r in routes)

by_country = {}
for aid, a in airport.items():
    by_country.setdefault(a["country"], []).append(aid)

hub, share, hhi = {}, {}, {}
for country, ids in by_country.items():
    total = sum(routes_of[i] for i in ids)
    if total == 0:
        continue
    counts = sorted((routes_of[i] for i in ids), reverse=True)
    hub[country] = max(ids, key=lambda i: routes_of[i])
    share[country] = counts[0] / total
    hhi[country] = sum((c / total) ** 2 for c in counts) * 10000

print("\n\nLos 10 mega-hubs, y el peso que tienen en su propio país")
print("=" * 78)
print(f"{'#':>2}. {'Aeropuerto':<40} {'País':<22} {'Rutas':>6} {'% de su país':>13}")
for rank, (aid, n) in enumerate(routes_of.most_common(10), 1):
    a = airport[aid]
    print(f"{rank:>2}. {(a['name'] + ' (' + (a['iata'] or a['icao']) + ')'):<40} "
          f"{a['country']:<22} {n:>6} {share[a['country']] * 100:>12.1f}%")

multi = {c: h for c, h in hhi.items() if len(by_country[c]) > 1}
print(f"\n\nPaíses con más de un aeropuerto, por concentración (índice 0-10000)")
print("=" * 78)
print("Los más concentrados: casi todas sus rutas salen de un solo aeropuerto")
print(f"{'#':>2}. {'País':<24} {'Aerp.':>5} {'Rutas':>6} {'Hub':<34} {'Índice':>7}")
for rank, (country, index) in enumerate(sorted(multi.items(), key=lambda p: -p[1])[:10], 1):
    h = airport[hub[country]]
    name = h["name"][:26] + " (" + (h["iata"] or h["icao"]) + ")"
    print(f"{rank:>2}. {country:<24} {len(by_country[country]):>5} {routes_per_country[country]:>6} "
          f"{name:<34} {index:>7.0f}")

print("\nLos más repartidos: ninguna ruta nacional depende de un solo aeropuerto")
print(f"{'#':>2}. {'País':<24} {'Aerp.':>5} {'Rutas':>6} {'Hub':<34} {'Índice':>7}")
for rank, (country, index) in enumerate(sorted(multi.items(), key=lambda p: p[1])[:10], 1):
    h = airport[hub[country]]
    name = h["name"][:26] + " (" + (h["iata"] or h["icao"]) + ")"
    print(f"{rank:>2}. {country:<24} {len(by_country[country]):>5} {routes_per_country[country]:>6} "
          f"{name:<34} {index:>7.0f}")

unica = [c for c in share if len(by_country[c]) == 1]
print(f"\nAdemás, {len(unica)} países dependen al 100% de su único aeropuerto: toda su "
      f"conexión aérea pasa por un solo punto.")
