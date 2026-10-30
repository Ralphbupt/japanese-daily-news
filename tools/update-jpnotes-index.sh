#!/bin/sh
# Refresh the copy of jpnotes.dev's grammar index that the site build uses to
# link each episode's grammar points to the matching jpnotes lesson section
# (site/src/lib/jpnotes.ts). Run after lessons are added or renamed there.
set -e
cd "$(dirname "$0")/.."
curl -sf https://jpnotes.dev/search-index.json -o site/src/data/jpnotes-index.json
python3 -c "import json; print(len(json.load(open('site/src/data/jpnotes-index.json'))), 'entries')"
