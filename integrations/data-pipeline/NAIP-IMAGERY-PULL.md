# NAIP Imagery Pull — how to run it

`naip_imagery_pull.py` fetches NAIP aerial imagery for 6 golf courses so we can judge
whether the free, public-domain NAIP product is sharp enough to trace greens, bunkers,
and hazard margins by hand. It is an **imagery-quality test**, not part of the live app.

It only fetches **pictures**. It never writes per-hole coordinates — turning pixels into
coordinates is a separate human step (the project's hard rule: never fabricate coords).

## Why it can't run in the Claude Code web session

The cloud environment's network policy only allows GitHub. The NAIP hosts
(`gis.apfo.usda.gov`, `planetarycomputer.microsoft.com`, `earthexplorer.usgs.gov`) all
return HTTP 403 "Host not in allowlist." **Run this on a normal computer with internet**
(same situation as `us_courses_pull.py`). Nothing to install for the default method — it
uses only what comes with Python 3.

## What you get

For each course, two PNGs in `data/naip/` (gitignored — large, regenerable):
- `naip_<slug>_overview.png` — the whole course, ~2,500×2,970 px at native 0.6 m.
- `naip_<slug>_green.png` — a 150 m crop on one green, 250 px (0.6 m) / 500 px (0.3 m).

Plus `naip_metadata.txt` with one line per image (NAIP year, GSD, method, bbox, size).

## Two-step workflow (a human has to pick the green)

The script won't guess where a green is. So:

**Step 1 — overviews:**
```
python3 naip_imagery_pull.py
```
Pulls the 6 overview images.

**Step 2 — green crops:**
Open each overview, find one clearly-visible green, read off its `lat,lon`, and put it in
the `COURSES` list near the top of the script (`green_center`). Then:
```
python3 naip_imagery_pull.py --greens
```

Handy flags: `--all` (both, once green centers are set) · `--only white_horse,foster`
(subset) · `--gsd 0.3` (if the local NAIP vintage is 0.3 m) · `--service NAME` (force a
specific USDA ImageServer) · `--method pc` (use Planetary Computer instead — needs
`pip install rasterio numpy planetary-computer pystac-client`).

## Methods

- **APFO (default)** — USDA's ArcGIS ImageServer returns a ready PNG clipped to the bbox,
  so no GeoTIFF tooling is needed. The script auto-discovers the current NAIP ImageServer
  (override with `--service`).
- **Planetary Computer (`--method pc`)** — searches the `naip` STAC collection for the
  most recent item and renders true color; needs the extra packages above.

After the images come back, fill in the scoring rubric in the original handoff request to
decide which courses are "NAIP-good" vs. which few need a sharper or fresher source.
