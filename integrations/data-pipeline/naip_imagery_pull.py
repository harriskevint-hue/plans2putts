#!/usr/bin/env python3
"""
ShadesCaddie / Plans2Putts — NAIP aerial-imagery pull (imagery-source evaluation).

Retrieves current NAIP aerial imagery for a small set of golf courses so the imagery
can be evaluated as a source for digitizing greens, bunkers, and hazard margins. This
is a QUALITY/USEFULNESS test, not a bulk job: for each course it pulls

  1. a full-course OVERVIEW framed to the course bbox, and
  2. a tight GREEN CROP (~150 m box) on one clearly-visible green.

The green crop is the important one — it shows whether NAIP is sharp enough to trace a
green edge, bunker lip, and hazard margin.

THE HARD RULE (project): this script only fetches PICTURES. It never invents, estimates,
or writes per-hole coordinates. A picture is a canvas for a human to trace later, not a
coordinate source. Pixels-to-coordinates digitizing is a separate, human step.

=============================================================================
WHERE THIS RUNS: LOCALLY (not in the Claude Code web environment).
=============================================================================
The cloud environment's network policy blocks the NAIP hosts (gis.apfo.usda.gov,
planetarycomputer.microsoft.com, earthexplorer.usgs.gov) with HTTP 403
"Host not in allowlist." Run this on a normal machine with internet.

Output PNGs + a metadata file land in integrations/data-pipeline/data/naip/ by default.
That directory is a regenerable artifact (gitignored) — the imagery is large and not
source-of-truth, so it is not committed.

-----------------------------------------------------------------------------
METHOD A (default) — USDA APFO NAIP ArcGIS ImageServer `exportImage`
-----------------------------------------------------------------------------
Pure standard library (urllib only). The service returns a ready-to-use PNG clipped to
the bbox at the size we ask for, so no GeoTIFF tooling (GDAL/rasterio) is needed. This
is why it is the default. The script discovers the current ImageServer from the service
directory, or you can name one with --service.

-----------------------------------------------------------------------------
METHOD B (--method pc) — Microsoft Planetary Computer STAC
-----------------------------------------------------------------------------
Searches the `naip` STAC collection for the most recent item over each bbox and renders
true color to PNG. This path needs extra packages (pystac-client, rasterio). If they are
missing the script tells you exactly what to install and falls back to printing the STAC
item info so you can fetch it by hand.

-----------------------------------------------------------------------------
TWO-PHASE WORKFLOW (because picking a green needs human eyes)
-----------------------------------------------------------------------------
You cannot center a green crop on a green you haven't looked at, and this script does NOT
guess green locations (the hard rule). So:

  Phase 1:  python3 naip_imagery_pull.py
            -> pulls the 6 OVERVIEW images only, and prints a reminder.

  Phase 2:  open each overview, read off the lat,lon of one clearly-visible green,
            put it in GREEN_CENTERS below (or pass --green-centers), then:
            python3 naip_imagery_pull.py --greens
            -> pulls the 6 GREEN CROP images.

Run with no flags to do overviews; add --greens once you've filled in green centers.
--all does both in one go (only useful after green centers are set).

Usage:
    python3 naip_imagery_pull.py                      # Phase 1: overviews
    python3 naip_imagery_pull.py --greens            # Phase 2: green crops
    python3 naip_imagery_pull.py --all               # both
    python3 naip_imagery_pull.py --only white_horse  # one course
    python3 naip_imagery_pull.py --service NAIPLatest # force an ImageServer name
    python3 naip_imagery_pull.py --method pc          # use Planetary Computer
    python3 naip_imagery_pull.py --gsd 0.3            # assume 0.3 m native (sizes pixels)
"""

import argparse
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUTDIR = os.path.join(HERE, "data", "naip")
USER_AGENT = "ShadesCaddie-NAIP-Eval/0.1 (imagery source test; contact harriskevint@gmail.com)"

APFO_NAIP_DIR = "https://gis.apfo.usda.gov/arcgis/rest/services/NAIP"
PC_STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"

# ArcGIS exportImage refuses very large outputs; 4100 px/side is the common server cap.
# Native NAIP over a ~1.7 km bbox is ~2,800 px at 0.6 m (well under the cap); a 0.3 m
# product would want ~5,600 px, which the server will reject, so we clamp and warn.
MAX_PX = 4100

# Default native ground sample distance assumption, in meters/pixel, used to size the
# output so we ask for ~native resolution and do NOT downsample. NAIP is ~0.6 m (some
# 2021+ flights are 0.3 m). Override with --gsd if you know the local vintage.
DEFAULT_GSD = 0.6

GREEN_CROP_METERS = 150.0  # side length of the green close-up box

# ---------------------------------------------------------------------------
# The 6 courses. bbox = (min_lon, min_lat, max_lon, max_lat), WGS84 / EPSG:4326.
# green_center = (lat, lon) of ONE clearly-visible green — FILL IN after looking at the
# Phase-1 overview. Leave as None until then; the script will skip the crop and remind you.
# ---------------------------------------------------------------------------
COURSES = [
    {
        "slug": "white_horse",
        "name": "White Horse Golf Club (Kingston, WA)",
        "bbox": (-122.539283, 47.761589, -122.519283, 47.777589),
        "green_center": None,
    },
    {
        "slug": "meadowmeer",
        "name": "Meadowmeer Golf & Country Club (Bainbridge Island, WA)",
        "bbox": (-122.552642, 47.656292, -122.532642, 47.672292),
        "green_center": None,
    },
    {
        "slug": "rolling_hills",
        "name": "Rolling Hills Golf Course (Bremerton, WA)",
        "bbox": (-122.626447, 47.612770, -122.606447, 47.628770),
        "green_center": None,
    },
    {
        "slug": "foster",
        "name": "Foster Golf Links (Tukwila, WA)",
        "bbox": (-122.275192, 47.473211, -122.255192, 47.489211),
        "green_center": None,
    },
    {
        "slug": "maplewood",
        "name": "Maplewood Golf Course (Renton, WA)",
        "bbox": (-122.171832, 47.463023, -122.151832, 47.479023),
        "green_center": None,
    },
    {
        "slug": "newcastle",
        "name": "The Golf Club at Newcastle (Newcastle, WA)",
        "bbox": (-122.153766, 47.527509, -122.133766, 47.543509),
        "green_center": None,
    },
]


# ---------------------------------------------------------------------------
# geometry helpers
# ---------------------------------------------------------------------------
def meters_per_deg(lat):
    """Approx meters per degree of lat and lon at a given latitude."""
    lat_m = 111_320.0
    lon_m = 111_320.0 * math.cos(math.radians(lat))
    return lat_m, lon_m


def bbox_size_px(bbox, gsd, max_px=MAX_PX):
    """Pixel size (w,h) for a bbox at the given native GSD, clamped to max_px."""
    min_lon, min_lat, max_lon, max_lat = bbox
    mid_lat = (min_lat + max_lat) / 2.0
    lat_m, lon_m = meters_per_deg(mid_lat)
    w_m = (max_lon - min_lon) * lon_m
    h_m = (max_lat - min_lat) * lat_m
    w = max(1, round(w_m / gsd))
    h = max(1, round(h_m / gsd))
    clamped = False
    if w > max_px or h > max_px:
        scale = max_px / max(w, h)
        w = max(1, round(w * scale))
        h = max(1, round(h * scale))
        clamped = True
    return w, h, w_m, h_m, clamped


def green_bbox(green_center, side_m=GREEN_CROP_METERS):
    """A square bbox of side_m meters centered on (lat, lon)."""
    lat, lon = green_center
    lat_m, lon_m = meters_per_deg(lat)
    dlat = (side_m / 2.0) / lat_m
    dlon = (side_m / 2.0) / lon_m
    return (lon - dlon, lat - dlat, lon + dlon, lat + dlat)


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------
def http_get(url, retries=4, timeout=120):
    """GET with polite UA and exponential-backoff retries. Returns (bytes, content_type)."""
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read(), resp.headers.get("Content-Type", "")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            last = e
            wait = 2 ** (attempt + 1)
            sys.stderr.write(f"  request failed ({e}); retry in {wait}s\n")
            time.sleep(wait)
    raise RuntimeError(f"GET failed after {retries} tries: {url}\n  last error: {last}")


# ---------------------------------------------------------------------------
# METHOD A — USDA APFO ArcGIS ImageServer
# ---------------------------------------------------------------------------
def discover_apfo_service(preferred=None):
    """
    Inspect the APFO NAIP service directory and return an ImageServer service name.
    Preference order: an explicit --service; a name containing 'mostrecent'/'latest';
    the highest 4-digit year found; else the first ImageServer. Prints what it found so a
    human can override with --service.
    """
    if preferred:
        return preferred
    data, _ = http_get(f"{APFO_NAIP_DIR}?f=json")
    info = json.loads(data)
    services = [s for s in info.get("services", []) if s.get("type") == "ImageServer"]
    folders = info.get("folders", [])
    names = [s["name"].split("/")[-1] for s in services]
    print("  APFO NAIP ImageServers found:", names or "(none at top level)")
    if folders:
        print("  APFO NAIP subfolders:", folders, "(inspect with --service folder/Name)")
    if not names:
        raise RuntimeError(
            "No ImageServer at the top level. Open "
            f"{APFO_NAIP_DIR}?f=json , pick a service/layer, and pass it via --service."
        )

    def year_of(n):
        import re
        m = re.findall(r"(19|20)\d{2}", n)
        return max(int(y) for y in m) if m else -1

    for n in names:
        if "mostrecent" in n.lower() or "latest" in n.lower():
            return n
    names_by_year = sorted(names, key=year_of, reverse=True)
    return names_by_year[0]


def apfo_export(service, bbox, size, outpath):
    """Call exportImage for a bbox and save the PNG. Returns the export URL used."""
    w, h = size
    params = {
        "bbox": ",".join(str(c) for c in bbox),
        "bboxSR": "4326",
        "imageSR": "4326",
        "size": f"{w},{h}",
        "format": "png",
        "f": "image",
    }
    url = f"{APFO_NAIP_DIR}/{service}/ImageServer/exportImage?" + urllib.parse.urlencode(params)
    body, ctype = http_get(url)
    # On error the service returns JSON, not an image — surface it instead of saving junk.
    if "image" not in ctype.lower():
        try:
            msg = json.loads(body).get("error", body[:300])
        except Exception:
            msg = body[:300]
        raise RuntimeError(f"exportImage did not return an image ({ctype}): {msg}")
    with open(outpath, "wb") as f:
        f.write(body)
    return url


def apfo_capture_year(service, bbox):
    """
    Best-effort NAIP vintage: query the ImageServer catalog for items overlapping the
    bbox and read a date/year field. Returns a string (year(s) or 'unknown').
    """
    geom = {
        "xmin": bbox[0], "ymin": bbox[1], "xmax": bbox[2], "ymax": bbox[3],
        "spatialReference": {"wkid": 4326},
    }
    params = {
        "geometry": json.dumps(geom),
        "geometryType": "esriGeometryEnvelope",
        "spatialRel": "esriSpatialRelIntersects",
        "returnGeometry": "false",
        "outFields": "*",
        "f": "json",
    }
    url = f"{APFO_NAIP_DIR}/{service}/ImageServer/query?" + urllib.parse.urlencode(params)
    try:
        body, _ = http_get(url)
        info = json.loads(body)
        years = set()
        for feat in info.get("features", []):
            attrs = {k.lower(): v for k, v in feat.get("attributes", {}).items()}
            for key in ("srcimgdate", "srcdate", "naip_year", "year", "acquisitiondate"):
                if key in attrs and attrs[key]:
                    v = str(attrs[key])
                    # epoch ms dates -> year
                    if v.isdigit() and len(v) >= 11:
                        years.add(time.gmtime(int(v) / 1000).tm_year)
                    else:
                        import re
                        m = re.findall(r"(19|20)\d{2}", v)
                        years.update(int(y) for y in m)
        return ", ".join(str(y) for y in sorted(years)) if years else "unknown"
    except Exception as e:
        return f"unknown ({e})"


# ---------------------------------------------------------------------------
# METHOD B — Microsoft Planetary Computer STAC (optional, needs extra libs)
# ---------------------------------------------------------------------------
def pc_search_item(bbox):
    """Return the most recent NAIP STAC item (as dict) intersecting bbox, or raise."""
    query = {
        "collections": ["naip"],
        "bbox": list(bbox),
        "limit": 5,
        "sortby": [{"field": "properties.datetime", "direction": "desc"}],
    }
    req = urllib.request.Request(
        f"{PC_STAC}/search",
        data=json.dumps(query).encode(),
        headers={"User-Agent": USER_AGENT, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read())
    feats = result.get("features", [])
    if not feats:
        raise RuntimeError("No NAIP STAC items found for bbox.")
    return feats[0]


def pc_render(item, bbox, size, outpath):
    """
    Render the STAC item's COG to a true-color PNG clipped to bbox. Needs rasterio.
    Raises ImportError with install hint if rasterio is unavailable.
    """
    try:
        import numpy as np
        import rasterio
        from rasterio.warp import transform_bounds
        from rasterio.windows import from_bounds
    except ImportError as e:
        raise ImportError(
            "Planetary Computer rendering needs rasterio + numpy:\n"
            "    pip install rasterio numpy planetary-computer pystac-client\n"
            f"(missing: {e})"
        )
    import planetary_computer as pc
    signed = pc.sign(item["assets"]["image"]["href"])
    with rasterio.open(signed) as src:
        left, bottom, right, top = transform_bounds("EPSG:4326", src.crs, *bbox)
        window = from_bounds(left, bottom, right, top, src.transform)
        w, h = size
        data = src.read([1, 2, 3], window=window, out_shape=(3, h, w))
        # simple 2-98 percentile stretch per band for a natural-color PNG
        arr = np.zeros((h, w, 3), dtype=np.uint8)
        for i in range(3):
            band = data[i].astype("float32")
            lo, hi = np.percentile(band, (2, 98))
            hi = hi if hi > lo else lo + 1
            arr[:, :, i] = np.clip((band - lo) / (hi - lo) * 255, 0, 255).astype("uint8")
    try:
        from PIL import Image
        Image.fromarray(arr).save(outpath)
    except ImportError:
        # fall back to writing a PNG via rasterio if PIL is absent
        import rasterio as rio
        with rio.open(
            outpath, "w", driver="PNG", height=h, width=w, count=3, dtype="uint8"
        ) as dst:
            for i in range(3):
                dst.write(arr[:, :, i], i + 1)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def run(args):
    os.makedirs(args.outdir, exist_ok=True)
    courses = COURSES
    if args.only:
        wanted = set(s.strip() for s in args.only.split(","))
        courses = [c for c in COURSES if c["slug"] in wanted]
        if not courses:
            sys.exit(f"No course matched --only {args.only}. Slugs: "
                     + ", ".join(c["slug"] for c in COURSES))

    do_overview = args.all or not args.greens
    do_green = args.all or args.greens

    service = None
    if args.method == "apfo":
        print("Discovering USDA APFO NAIP ImageServer ...")
        service = discover_apfo_service(args.service)
        print(f"Using ImageServer: {service}\n")

    metadata_lines = []
    for c in courses:
        print(f"=== {c['name']} [{c['slug']}] ===")
        cap_year = "unknown"
        if args.method == "apfo":
            cap_year = apfo_capture_year(service, c["bbox"])

        # ---- overview ----
        if do_overview:
            w, h, w_m, h_m, clamped = bbox_size_px(c["bbox"], args.gsd, args.max_px)
            out = os.path.join(args.outdir, f"naip_{c['slug']}_overview.png")
            print(f"  overview: {w}x{h}px  ({w_m:.0f}m x {h_m:.0f}m, gsd~{args.gsd}m)"
                  + ("  [CLAMPED to max-px]" if clamped else ""))
            try:
                if args.method == "apfo":
                    used = apfo_export(service, c["bbox"], (w, h), out)
                else:
                    item = pc_search_item(c["bbox"])
                    cap_year = item["properties"].get("datetime", "unknown")[:10]
                    used = item["assets"]["image"]["href"]
                    pc_render(item, c["bbox"], (w, h), out)
                print(f"    saved {out}")
            except Exception as e:
                print(f"    !! overview FAILED: {e}")
                used = "FAILED"
            metadata_lines.append(
                f"{c['name']} (overview) · NAIP {cap_year} · gsd~{args.gsd}m · "
                f"method {args.method.upper()} · bbox {c['bbox']} EPSG:4326 · {w}x{h}px"
            )

        # ---- green crop ----
        if do_green:
            if not c["green_center"]:
                print("  green crop SKIPPED — no green_center set. Open the overview, "
                      "read a green's lat,lon, put it in GREEN_CENTERS / COURSES, "
                      "then rerun with --greens.")
                metadata_lines.append(
                    f"{c['name']} (green) · SKIPPED — green_center not set"
                )
            else:
                gb = green_bbox(c["green_center"])
                gw, gh, gw_m, gh_m, gclamp = bbox_size_px(gb, args.gsd, args.max_px)
                out = os.path.join(args.outdir, f"naip_{c['slug']}_green.png")
                print(f"  green:    {gw}x{gh}px  centered {c['green_center']}")
                try:
                    if args.method == "apfo":
                        apfo_export(service, gb, (gw, gh), out)
                    else:
                        item = pc_search_item(gb)
                        cap_year = item["properties"].get("datetime", "unknown")[:10]
                        pc_render(item, gb, (gw, gh), out)
                    print(f"    saved {out}")
                except Exception as e:
                    print(f"    !! green FAILED: {e}")
                metadata_lines.append(
                    f"{c['name']} (green) · NAIP {cap_year} · gsd~{args.gsd}m · "
                    f"method {args.method.upper()} · bbox {tuple(round(x,6) for x in gb)} "
                    f"EPSG:4326 · {gw}x{gh}px"
                )
        print()

    meta_path = os.path.join(args.outdir, "naip_metadata.txt")
    with open(meta_path, "w") as f:
        f.write("\n".join(metadata_lines) + "\n")
    print("Metadata lines:")
    for line in metadata_lines:
        print("  " + line)
    print(f"\nWrote {meta_path}")
    if do_overview and not do_green:
        print("\nPhase 1 done. Next: open each overview, read off one green's lat,lon, "
              "set it in COURSES[].green_center, then rerun with --greens.")


def main():
    ap = argparse.ArgumentParser(description="Pull NAIP imagery for course-mapping evaluation.")
    ap.add_argument("--greens", action="store_true", help="Phase 2: pull green crops (needs green_center set).")
    ap.add_argument("--all", action="store_true", help="Pull both overviews and green crops.")
    ap.add_argument("--only", help="Comma-separated slugs to limit to (e.g. white_horse,foster).")
    ap.add_argument("--method", choices=["apfo", "pc"], default="apfo",
                    help="apfo = USDA ArcGIS exportImage (default, no deps); pc = Planetary Computer STAC.")
    ap.add_argument("--service", help="Force an APFO ImageServer name (e.g. NAIPLatest or folder/Name).")
    ap.add_argument("--gsd", type=float, default=DEFAULT_GSD, help="Assumed native GSD m/px for sizing (default 0.6).")
    ap.add_argument("--max-px", type=int, default=MAX_PX, help="Max pixels per side (server cap, default 4100).")
    ap.add_argument("--outdir", default=DEFAULT_OUTDIR, help="Output directory.")
    args = ap.parse_args()
    try:
        run(args)
    except RuntimeError as e:
        msg = str(e)
        sys.stderr.write(f"\nStopped: {msg}\n")
        if "403" in msg or "allowlist" in msg.lower():
            sys.stderr.write(
                "\nThis looks like a blocked network. The NAIP hosts are reachable from a\n"
                "normal machine with open internet, but NOT from the Claude Code web\n"
                "environment (its egress policy allows only GitHub). Run this script\n"
                "locally, or have the environment's network allowlist updated to include\n"
                "gis.apfo.usda.gov (and, for --method pc, planetarycomputer.microsoft.com\n"
                "plus the Azure blob hosts the STAC assets live on).\n"
            )
        sys.exit(1)


if __name__ == "__main__":
    main()
