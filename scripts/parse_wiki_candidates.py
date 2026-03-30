"""Parse the Wikipedia TN 2026 election article and emit two CSV files.

Outputs:
  data/constituencies.csv        — 234 rows: number, name, district, reserved
  data/candidates_provisional.csv — provisional candidates from SPA and AIADMK+

Usage:
    # 1. Download the page once (do not re-download on subsequent runs)
    curl -s "https://en.wikipedia.org/wiki/2026_Tamil_Nadu_Legislative_Assembly_election" \\
         -o /tmp/tn2026_wiki.html

    # 2. Parse (can be re-run without re-downloading)
    python scripts/parse_wiki_candidates.py [--html /tmp/tn2026_wiki.html]

The script is intentionally read-only: it only writes to data/*.csv, never
touches the database.  Run seed_constituencies.py afterwards to load the DB.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from bs4 import BeautifulSoup, Tag

WIKI_URL = "https://en.wikipedia.org/wiki/2026_Tamil_Nadu_Legislative_Assembly_election"
DEFAULT_HTML_CACHE = Path("/tmp/tn2026_wiki.html")
DATA_DIR = Path(__file__).parent.parent / "data"

# Strip Wikipedia footnote markers like [a], [b], [c], [1], etc.
_FOOTNOTE = re.compile(r"\[[^\]]+\]")


def clean(text: str) -> str:
    """Strip footnote markers and extra whitespace."""
    return _FOOTNOTE.sub("", text).strip()


def reserved_status(raw_name: str) -> tuple[str, str]:
    """Return (clean_name, reserved) where reserved is 'SC', 'ST', or ''."""
    m = re.search(r"\((SC|ST)\)", raw_name, re.IGNORECASE)
    reserved = m.group(1).upper() if m else ""
    name = re.sub(r"\s*\((SC|ST)\)\s*", "", raw_name, flags=re.IGNORECASE).strip()
    return name, reserved


def fetch_or_load(html_path: Path) -> str:
    """Return HTML from cache file, downloading it first if missing."""
    if not html_path.exists():
        print(f"Downloading Wikipedia article → {html_path}")
        urllib.request.urlretrieve(WIKI_URL, html_path)
    else:
        print(f"Using cached HTML from {html_path}")
    return html_path.read_text(encoding="utf-8")


def find_candidates_table(soup: BeautifulSoup) -> Tag:
    """Return the wikitable that contains SPA / AIADMK+ candidate columns."""
    for table in soup.find_all("table", class_="wikitable"):
        if "SPA" in table.get_text():
            return table
    raise ValueError("Candidates table not found in the Wikipedia page.")


def parse_table(table: Tag) -> list[dict]:
    """Parse all 234 data rows; return list of dicts."""
    rows = table.find_all("tr")
    records: list[dict] = []
    current_district = ""

    for row in rows[2:]:  # skip the two header rows
        cells = row.find_all(["td", "th"])

        if len(cells) == 9:
            # First row of a new district group — has the district cell
            current_district = clean(cells[0].get_text())
            no_raw = clean(cells[1].get_text())
            name_raw = clean(cells[2].get_text())
            # cells[3] is an empty coloured cell (SPA alliance colour)
            spa_party = clean(cells[4].get_text())
            spa_cand = clean(cells[5].get_text())
            # cells[6] is an empty coloured cell (AIADMK+ colour)
            ai_party = clean(cells[7].get_text())
            ai_cand = clean(cells[8].get_text())
        elif len(cells) == 8:
            # Continuation row — district carries over from rowspan
            no_raw = clean(cells[0].get_text())
            name_raw = clean(cells[1].get_text())
            spa_party = clean(cells[3].get_text())
            spa_cand = clean(cells[4].get_text())
            ai_party = clean(cells[6].get_text())
            ai_cand = clean(cells[7].get_text())
        else:
            continue  # unexpected row shape — skip

        try:
            number = int(no_raw)
        except ValueError:
            continue

        name, reserved = reserved_status(name_raw)

        records.append(
            {
                "number": number,
                "name": name,
                "district": current_district,
                "reserved": reserved,
                "spa_party": spa_party,
                "spa_candidate": spa_cand,
                "aiadmk_party": ai_party,
                "aiadmk_candidate": ai_cand,
            }
        )

    return records


def write_constituencies(records: list[dict], out: Path) -> None:
    """Write data/constituencies.csv."""
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["number", "name", "district", "reserved"])
        writer.writeheader()
        for r in records:
            writer.writerow(
                {
                    "number": r["number"],
                    "name": r["name"],
                    "district": r["district"],
                    "reserved": r["reserved"],
                }
            )
    print(f"Wrote {len(records)} constituencies → {out}")


def write_candidates(records: list[dict], out: Path) -> None:
    """Write data/candidates_provisional.csv."""
    rows: list[dict] = []
    for r in records:
        if r["spa_party"] or r["spa_candidate"]:
            rows.append(
                {
                    "constituency_number": r["number"],
                    "alliance": "SPA",
                    "party": r["spa_party"],
                    "candidate": r["spa_candidate"],
                }
            )
        if r["aiadmk_party"] or r["aiadmk_candidate"]:
            rows.append(
                {
                    "constituency_number": r["number"],
                    "alliance": "AIADMK+",
                    "party": r["aiadmk_party"],
                    "candidate": r["aiadmk_candidate"],
                }
            )

    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["constituency_number", "alliance", "party", "candidate"]
        )
        writer.writeheader()
        writer.writerows(rows)

    filled = sum(1 for r in rows if r["candidate"])
    print(
        f"Wrote {len(rows)} candidate rows ({filled} with names, "
        f"{len(rows) - filled} party-only) → {out}"
    )


def main(html_path: Path) -> None:
    """Parse the Wikipedia page and write the two CSV files."""
    DATA_DIR.mkdir(exist_ok=True)

    html = fetch_or_load(html_path)
    soup = BeautifulSoup(html, "html.parser")
    table = find_candidates_table(soup)
    records = parse_table(table)

    if len(records) != 234:
        print(
            f"WARNING: expected 234 constituencies, got {len(records)}. "
            "The Wikipedia page structure may have changed.",
            file=sys.stderr,
        )

    write_constituencies(records, DATA_DIR / "constituencies.csv")
    write_candidates(records, DATA_DIR / "candidates_provisional.csv")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--html",
        type=Path,
        default=DEFAULT_HTML_CACHE,
        help=f"Path to cached Wikipedia HTML (default: {DEFAULT_HTML_CACHE})",
    )
    args = parser.parse_args()
    main(args.html)
