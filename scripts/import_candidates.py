"""Import parties and candidates for Tamil Nadu 2026 from myneta.info.

Source: https://myneta.info/TamilNadu2026/

Running the script always seeds the known Tamil Nadu parties with correct
colours and abbreviations.  Candidate scraping only runs once MyNeta's
TN 2026 database is live (after nomination filing closes, ~early April 2026).

Usage:
    python scripts/import_candidates.py [--election-id N] [--dry-run]

Options:
    --election-id N   DB election ID to import into (default: 1)
    --dry-run         Fetch and parse but do not write to the database

NOTE: requests and beautifulsoup4 are NOT in requirements.txt (they are
dev/script dependencies only).  On PythonAnywhere prod, install them once:
    pip install requests beautifulsoup4
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print(
        "Missing dependencies.\nRun:  pip install requests beautifulsoup4",
        file=sys.stderr,
    )
    sys.exit(1)

from app.database import SessionLocal
from app.models.candidate import Candidate
from app.models.constituency import Constituency, Party
from app.models.election import Election

# ── Constants ─────────────────────────────────────────────────────────────────

BASE_URL = "https://myneta.info/TamilNadu2026"
REQUEST_DELAY = 0.5  # seconds between requests

# Well-known TN parties: MyNeta display name → (abbreviation, hex colour).
# Colour choices follow each party's flag/logo.
KNOWN_PARTIES: dict[str, tuple[str, str]] = {
    "Dravida Munnetra Kazhagam": ("DMK", "#E50000"),
    "DMK": ("DMK", "#E50000"),
    "All India Anna Dravida Munnetra Kazhagam": ("AIADMK", "#1A1A1A"),
    "AIADMK": ("AIADMK", "#1A1A1A"),
    "Bharatiya Janata Party": ("BJP", "#FF6600"),
    "BJP": ("BJP", "#FF6600"),
    "Indian National Congress": ("INC", "#138808"),
    "INC": ("INC", "#138808"),
    "Pattali Makkal Katchi": ("PMK", "#006400"),
    "PMK": ("PMK", "#006400"),
    "Viduthalai Chiruthaigal Katchi": ("VCK", "#0000CD"),
    "VCK": ("VCK", "#0000CD"),
    "Communist Party of India  (Marxist)": ("CPI(M)", "#CC0000"),
    "Communist Party of India (Marxist)": ("CPI(M)", "#CC0000"),
    "CPI(M)": ("CPI(M)", "#CC0000"),
    "Communist Party of India": ("CPI", "#DD0000"),
    "CPI": ("CPI", "#DD0000"),
    "Marumalarchi Dravida Munnetra Kazhagam": ("MDMK", "#008000"),
    "MDMK": ("MDMK", "#008000"),
    "Desiya Murpokku Dravida Kazhagam": ("DMDK", "#F5A623"),
    "DMDK": ("DMDK", "#F5A623"),
    "Naam Tamilar Katchi": ("NTK", "#FF0000"),
    "NTK": ("NTK", "#FF0000"),
    "Amma Makkal Munnettra Kazagam": ("AMMK", "#8B0000"),
    "AMMK": ("AMMK", "#8B0000"),
    "Makkal Needhi Maiam": ("MNM", "#E50000"),
    "MNM": ("MNM", "#E50000"),
    "Tamilaga Vettri Kazhagam": ("TVK", "#FF4500"),
    "TVK": ("TVK", "#FF4500"),
    "Indian Union Muslim League": ("IUML", "#006400"),
    "IUML": ("IUML", "#006400"),
    "All India Majlis-E-Ittehadul Muslimeen": ("AIMIM", "#2E8B57"),
    "Independent": ("IND", "#888888"),
    "IND": ("IND", "#888888"),
}

# ── Data types ────────────────────────────────────────────────────────────────


class ScrapedCandidate(NamedTuple):
    """A candidate row scraped from a MyNeta constituency page."""

    name: str
    party_name: str
    is_winner: bool


# ── HTTP helpers ──────────────────────────────────────────────────────────────

_session = requests.Session()
_session.headers["User-Agent"] = "Mozilla/5.0 (compatible; 234seats-import/1.0)"


def _get(url: str) -> requests.Response:
    """Fetch a URL, raising on HTTP errors."""
    resp = _session.get(url, timeout=15)
    resp.raise_for_status()
    return resp


def _candidates_live() -> bool:
    """Return True if the TN 2026 MyNeta database has been populated."""
    try:
        text = _get(BASE_URL + "/").text
        return "Unknown database" not in text and "Unable to connect to MySQL" not in text
    except requests.RequestException:
        return False


# ── Scrapers ──────────────────────────────────────────────────────────────────


def scrape_constituency_ids() -> list[tuple[int, str]]:
    """Return list of (myneta_id, name) for all TN 2026 constituencies."""
    soup = BeautifulSoup(_get(BASE_URL + "/").text, "html.parser")
    seen: set[int] = set()
    results: list[tuple[int, str]] = []
    for a in soup.find_all("a", href=re.compile(r"constituency_id=\d+")):
        m = re.search(r"constituency_id=(\d+)", a["href"])
        if not m:
            continue
        cid = int(m.group(1))
        name = a.get_text(strip=True)
        if name and name != "ALL CONSTITUENCIES" and cid not in seen:
            seen.add(cid)
            results.append((cid, name))
    return results


def scrape_candidates(myneta_id: int) -> list[ScrapedCandidate]:
    """Return all candidates listed on a MyNeta constituency page."""
    url = f"{BASE_URL}/index.php?action=show_candidates&constituency_id={myneta_id}"
    soup = BeautifulSoup(_get(url).text, "html.parser")
    table = soup.find("table", class_="w3-table")
    if table is None:
        return []
    results: list[ScrapedCandidate] = []
    for row in table.find_all("tr")[1:]:  # skip header row
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        name_cell = cells[1]
        is_winner = bool(name_cell.find("font", color="green"))
        a = name_cell.find("a")
        if a is None:
            continue
        name = a.get_text(strip=True)
        party = cells[2].get_text(strip=True) or "Independent"
        if name:
            results.append(ScrapedCandidate(name=name, party_name=party, is_winner=is_winner))
    return results


# ── Name matching ─────────────────────────────────────────────────────────────

_RESERVED_SUFFIX = re.compile(r"\s*\((SC|ST)\)\s*$", re.IGNORECASE)


def _normalise(name: str) -> str:
    """Lowercase and strip reserved-seat suffixes for fuzzy matching."""
    return _RESERVED_SUFFIX.sub("", name).strip().lower()


def find_constituency(
    db_constituencies: list[Constituency], myneta_name: str
) -> Constituency | None:
    """Match a MyNeta constituency name to a DB record by normalised name."""
    target = _normalise(myneta_name)
    for c in db_constituencies:
        if _normalise(c.name) == target:
            return c
    return None


# ── DB helpers ────────────────────────────────────────────────────────────────


def upsert_party(db: object, party_name: str) -> Party:
    """Return an existing party or create one; updates colour/abbrev if known."""
    from sqlalchemy.orm import Session

    assert isinstance(db, Session)

    party = db.query(Party).filter_by(name=party_name).first()
    known = KNOWN_PARTIES.get(party_name)

    if party is None:
        party = Party(
            name=party_name,
            abbreviation=known[0] if known else party_name[:15],
            color_hex=known[1] if known else "#888888",
        )
        db.add(party)
        db.flush()
    elif known:
        party.abbreviation = known[0]
        party.color_hex = known[1]

    return party


# ── Steps ─────────────────────────────────────────────────────────────────────


def seed_parties(db: object, dry_run: bool) -> int:
    """Upsert all known TN parties.  Returns number created."""
    from sqlalchemy.orm import Session

    assert isinstance(db, Session)

    # Deduplicate by abbreviation — only seed each unique party once
    seeded: set[str] = set()
    created = 0
    for display_name, (abbrev, _color) in KNOWN_PARTIES.items():
        if abbrev in seeded:
            continue
        seeded.add(abbrev)
        if not dry_run:
            upsert_party(db, display_name)
            created += 1
        else:
            created += 1
    if not dry_run:
        db.commit()  # type: ignore[attr-defined]
    return created


def import_candidates(
    db: object,
    election_id: int,
    dry_run: bool,
) -> None:
    """Scrape all candidates from MyNeta and insert into the DB."""
    from sqlalchemy.orm import Session

    assert isinstance(db, Session)

    print("Fetching constituency list from MyNeta…")
    constituency_ids = scrape_constituency_ids()
    print(f"Found {len(constituency_ids)} constituencies on MyNeta.")

    db_constituencies = db.query(Constituency).filter_by(election_id=election_id).all()

    total_created = 0
    total_skipped = 0
    unmatched: list[str] = []

    for i, (myneta_id, myneta_name) in enumerate(constituency_ids, 1):
        constituency = find_constituency(db_constituencies, myneta_name)
        if constituency is None:
            unmatched.append(myneta_name)
            print(f"  [{i}/{len(constituency_ids)}] UNMATCHED: {myneta_name!r}")
            time.sleep(REQUEST_DELAY)
            continue

        print(
            f"  [{i}/{len(constituency_ids)}] {constituency.name}…",
            end=" ",
            flush=True,
        )

        candidates = scrape_candidates(myneta_id)
        created = 0
        for sc in candidates:
            exists = (
                db.query(Candidate).filter_by(constituency_id=constituency.id, name=sc.name).first()
            )
            if exists:
                continue
            if not dry_run:
                party = upsert_party(db, sc.party_name)
                db.add(
                    Candidate(
                        constituency_id=constituency.id,
                        name=sc.name,
                        party_id=party.id,
                    )
                )
            created += 1

        if not dry_run:
            db.commit()

        print(f"+{created} new  ({len(candidates)} total)")
        total_created += created
        total_skipped += len(candidates) - created
        time.sleep(REQUEST_DELAY)

    print(f"\nCandidates created : {total_created}")
    print(f"Already existed    : {total_skipped}")
    if unmatched:
        print(f"Unmatched seats    : {len(unmatched)}")
        for name in unmatched:
            print(f"  - {name!r}")


# ── Main ──────────────────────────────────────────────────────────────────────


def run(election_id: int, dry_run: bool) -> None:
    """Seed parties (always) then import candidates (if MyNeta data is live)."""
    db = SessionLocal()
    try:
        election = db.get(Election, election_id)
        if election is None:
            print(f"Error: no election with id={election_id}.", file=sys.stderr)
            sys.exit(1)

        # ── Step 1: seed parties (always runs) ────────────────────────────────
        print(f"Seeding {len({a for a, _ in KNOWN_PARTIES.values()})} known TN parties…")
        n = seed_parties(db, dry_run)
        print(f"  {n} party records created/updated.")

        # ── Step 2: import candidates (only if MyNeta is live) ────────────────
        print("\nChecking if MyNeta TN 2026 candidate data is live…")
        if not _candidates_live():
            print(
                "  Not yet available — MyNeta's TN 2026 database hasn't been populated.\n"
                "  This happens after nomination filing closes (~early April 2026).\n"
                f"  Check: {BASE_URL}/\n"
                "  Re-run this script once candidate data appears there."
            )
            return

        import_candidates(db, election_id, dry_run)

        if dry_run:
            print("\n(dry-run — no changes written to DB)")

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--election-id",
        type=int,
        default=1,
        help="DB election ID to import into (default: 1)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and parse but do not write to the database",
    )
    args = parser.parse_args()
    run(args.election_id, args.dry_run)
