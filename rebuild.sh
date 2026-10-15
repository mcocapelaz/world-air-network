#!/bin/sh
# Rebuild every published page from the scripts, then tell you how to publish.
#
# The site that GitHub Pages serves is the generated HTML, not these scripts.
# So changing a colour in src/vuln_core.py changes nothing online until this
# script regenerates index.html and you commit it.
#
#   sh rebuild.sh          rebuild everything and print the git commands
#   sh rebuild.sh --png    also rebuild the PNG (needs Chrome)

set -e
cd "$(dirname "$0")"

echo "Regenerando el mapa interactivo…"
cd src
python3 vulnerability_story.py en
python3 least_connected_countries.py > /dev/null
python3 single_airport_countries.py > /dev/null
if [ "$1" = "--png" ]; then
  echo "Regenerando la imagen PNG…"
  python3 make_png.py
fi
cd ..

cp src/vulnerability-story-en.html index.html
cp src/least-connected.html least-connected.html
cp src/single-airport.html single-airport.html
if [ "$1" = "--png" ]; then
  cp src/least-connected-countries.png least-connected-countries.png
fi

echo
echo "Listo. Archivos actualizados:"
ls -l index.html least-connected.html single-airport.html | awk '{print "  " $9, $5, "bytes"}'
echo
echo "Para publicarlo:"
echo "  git add -A"
echo "  git commit -m \"nueva paleta de colores\""
echo "  git push"
echo
echo "La web se actualiza sola en 1-2 minutos."