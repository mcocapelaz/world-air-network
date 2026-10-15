# World Air Network

An interactive look at the fragility of the world's airport network, built from
the OpenFlights dataset.

**Live map:** <https://USER.github.io/world-air-network/>

## What's here

| Page | What it shows |
|---|---|
| `index.html` | Every airport on a world map, coloured by how fragile its connectivity is. Search, five filters, sortable table, and a breakdown of the score for any airport you pick. |
| `least-connected.html` | The same view one level up: countries ranked by the routes their airports send out, with the 30 least connected highlighted on the map. |
| `single-airport.html` | The 69 countries that depend on a single airport, as a bar chart. |
| `least-connected-countries.png` | A static version of the country map, for print or slides. |

## The argument the data makes

Most of the world is well connected. The interesting cases are the edges — and
they are not the same kind of problem:

- **Isolation.** Tuvalu, Niue, the Cocos Islands: one airport, one route, three
  hops from anywhere. Geography, and hard to fix.
- **Substitution.** Eswatini has a single route, to OR Tambo — but OR Tambo is one
  of Africa's largest hubs, 80 km away by road. It isn't isolated; it just has no
  air service of its own, because there is no reason to fly there.
- **Periphery of the periphery.** Bangui, in the Central African Republic, is 4,195
  km from the nearest mega-hub — almost exactly as far as Kigali (4,067 km), which
  has 17 routes to its 4. Distance alone explains neither. Kigali is a gateway:
  the landlocked Great Lakes states need it. Nobody needs Bangui, because its
  neighbours have airports of their own.

That third case is the one the current score gets wrong, and it is why the score
is stated openly on the page rather than presented as a measurement.

## The score

A stated heuristic, 100 points across four factors:

| Factor | Weight | What it measures |
|---|---|---|
| Isolation | 40 | Few direct links: k=0 scores 40, k≥5 scores 0 |
| Bottleneck | 25 | Share of the airports that would be cut off if it closed (capped at 3) |
| Remoteness | 15 | Hops to the nearest mega-hub (capped at 5) |
| No alternative | 20 | Its country has no other airport |

It measures local degree, so it understates countries whose *neighbours* are also
poorly served. Adding a gravity-model term — neighbour strength weighted by
whether the neighbour depends on you — would fix that, and is the obvious next
step.

## Regenerating

The scripts read the CSVs straight out of keasy's S3 store, so they need the
stack running (`make dev` in a keasy checkout) and Python 3. No third-party
packages: everything uses the standard library, including the AWS SigV4 signing.

```bash
cd src
python3 vulnerability_story.py en      # the interactive map, English
python3 vulnerability_story.py es      # the interactive map, Spanish
python3 least_connected_countries.py   # the country map
python3 single_airport_countries.py    # the bar chart
python3 make_png.py                    # the static PNG (needs Chrome)
python3 airport_centrality.py          # degree, PageRank, betweenness
python3 remote_vulnerability.py        # cut vertices, islands, remoteness
python3 top_airports.py                # rankings and national concentration
```

`centrality.cache.json` keeps the betweenness results between runs, so the
generated pages stay fast to rebuild. It is not committed.

## Data

OpenFlights (ODbL), via the subset keasy derives in `make seed`: 3,218 airports
that some direct route touches, and the 36,906 directed routes between them. The
coastline outline is Natural Earth 110m land (public domain).

**On the numbers.** OpenFlights is a static, community-maintained dataset with
uneven coverage, and it is old. The *structure* holds — who connects to whom,
which territories depend on a single link — but per-country route counts should
not be cited as hard figures. Several airports in the set no longer operate
(Atatürk, and Wonsan in North Korea, which is why DPRK appears with 4 routes).
For current data use OpenSky Network.

## Licence

Code: do as you like with it. Data: OpenFlights is ODbL — keep the attribution.