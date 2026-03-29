"""Generate an SVG map of Tamil Nadu assembly constituencies.

Downloads the India_AC shapefile from datameet/maps, extracts the 234
Tamil Nadu constituencies, and writes a standalone SVG to
app/static/tn_map.svg.

Usage:
    python scripts/generate_tn_map.py

Dependencies (install once):
    pip install pyshp
"""

from __future__ import annotations

import os
import sys
import tempfile
import urllib.request
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

SVG_WIDTH = 500
SVG_HEIGHT = 650
PADDING = 10  # px padding inside SVG viewport

OUTPUT = Path(__file__).parent.parent / "app" / "static" / "tn_map.svg"

SHAPEFILE_BASE = "https://raw.githubusercontent.com/datameet/maps/master/assembly-constituencies/India_AC"
NEEDED_EXTENSIONS = [".shp", ".dbf", ".shx"]


# ── Helpers ───────────────────────────────────────────────────────────────────


def download_shapefiles(tmpdir: str) -> str:
    """Download India_AC shapefile components; return path prefix."""
    base_path = os.path.join(tmpdir, "India_AC")
    for ext in NEEDED_EXTENSIONS:
        url = SHAPEFILE_BASE + ext
        dest = base_path + ext
        print(f"  Downloading {url} …", end=" ", flush=True)
        urllib.request.urlretrieve(url, dest)
        size = os.path.getsize(dest)
        print(f"{size // 1024} KB")
    return base_path


def geo_to_svg(
    x: float,
    y: float,
    min_x: float,
    min_y: float,
    scale: float,
    svg_height: float,
) -> tuple[float, float]:
    """Convert geographic coordinates to SVG pixel coordinates."""
    px = PADDING + (x - min_x) * scale
    py = PADDING + (svg_height - PADDING * 2) - (y - min_y) * scale  # flip Y
    return px, py


def points_to_path(
    points: list[tuple[float, float]],
    min_x: float,
    min_y: float,
    scale: float,
    svg_height: float,
) -> str:
    """Convert a list of (lon, lat) points to an SVG path d attribute."""
    parts: list[str] = []
    for i, (x, y) in enumerate(points):
        px, py = geo_to_svg(x, y, min_x, min_y, scale, svg_height)
        cmd = "M" if i == 0 else "L"
        parts.append(f"{cmd}{px:.2f},{py:.2f}")
    parts.append("Z")
    return " ".join(parts)


def build_multipart_path(
    shape_points: list[tuple[float, float]],
    shape_parts: list[int],
    min_x: float,
    min_y: float,
    scale: float,
    svg_height: float,
) -> str:
    """Build SVG path d for a possibly multi-part polygon."""
    n = len(shape_points)
    # Each entry in parts is the start index of that ring
    rings: list[list[tuple[float, float]]] = []
    for i, start in enumerate(shape_parts):
        end = shape_parts[i + 1] if i + 1 < len(shape_parts) else n
        rings.append(shape_points[start:end])

    segments: list[str] = []
    for ring in rings:
        segments.append(points_to_path(ring, min_x, min_y, scale, svg_height))
    return " ".join(segments)


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    """Download shapefile, generate SVG, write to app/static/tn_map.svg."""
    try:
        import shapefile  # type: ignore[import]
    except ImportError:
        print("Error: pyshp not installed. Run: pip install pyshp", file=sys.stderr)
        sys.exit(1)

    with tempfile.TemporaryDirectory() as tmpdir:
        print("Downloading shapefiles…")
        shp_prefix = download_shapefiles(tmpdir)

        print("Reading shapefile…")
        r = shapefile.Reader(shp_prefix)

        tn_items: list[dict] = []
        for i in range(len(r)):
            rec = r.record(i).as_dict()
            if str(rec.get("ST_NAME", "")).upper() == "TAMIL NADU":
                tn_items.append({"rec": rec, "shp": r.shape(i)})

        print(f"Found {len(tn_items)} Tamil Nadu constituencies")

        # Compute bounding box over all TN shapes
        all_x: list[float] = []
        all_y: list[float] = []
        for item in tn_items:
            bbox = item["shp"].bbox
            all_x.extend([bbox[0], bbox[2]])
            all_y.extend([bbox[1], bbox[3]])
        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)

        geo_w = max_x - min_x
        geo_h = max_y - min_y
        draw_w = SVG_WIDTH - PADDING * 2
        draw_h = SVG_HEIGHT - PADDING * 2
        scale = min(draw_w / geo_w, draw_h / geo_h)

    print("Generating SVG…")
    lines: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}"',
        f'     width="{SVG_WIDTH}" height="{SVG_HEIGHT}" id="tn-map">',
        "  <g id=\"constituencies\">",
    ]

    for item in tn_items:
        rec = item["rec"]
        shp = item["shp"]
        ac_no = int(rec["AC_NO"])
        ac_name = str(rec["AC_NAME"])
        dist = str(rec.get("DIST_NAME", ""))

        d = build_multipart_path(
            shp.points, list(shp.parts), min_x, min_y, scale, SVG_HEIGHT
        )

        # Sanitise name for use as an id
        safe_id = f"ac-{ac_no}"

        lines.append(
            f'    <path id="{safe_id}"'
            f' data-ac-no="{ac_no}"'
            f' data-name="{ac_name}"'
            f' data-district="{dist}"'
            f' d="{d}"'
            f' class="constituency"'
            f' fill="#e5e7eb" stroke="white" stroke-width="0.5">'
            f"<title>{ac_name}</title></path>"
        )

    lines += [
        "  </g>",
        "</svg>",
    ]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    size_kb = OUTPUT.stat().st_size // 1024
    print(f"Written {OUTPUT} ({size_kb} KB, {len(tn_items)} constituencies)")


if __name__ == "__main__":
    main()
