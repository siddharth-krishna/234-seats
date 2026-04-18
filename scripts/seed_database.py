"""Seed the database with parties, constituencies, and provisional candidates.

Reads three CSV files from data/:
  data/parties.csv                — parties with abbreviations and colours
  data/constituencies.csv         — 234 TN constituencies
  data/candidates_provisional.csv — provisional candidates from Wikipedia

Usage:
    python scripts/seed_database.py [--election-id N]

The script is idempotent: re-running it will not create duplicates.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models.candidate import Candidate
from app.models.constituency import Constituency, Party
from app.models.election import Election

DATA_DIR = Path(__file__).parent.parent / "data"


# ── CSV loaders ───────────────────────────────────────────────────────────────


def _read_csv(path: Path) -> list[dict[str, str]]:
    """Read a CSV file and return rows as dicts. Exits if file missing."""
    if not path.exists():
        print(f"Error: {path} not found.", file=sys.stderr)
        print(
            "Run scripts/parse_wiki_candidates.py first to generate the CSV files.",
            file=sys.stderr,
        )
        sys.exit(1)
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ── Seeding helpers ───────────────────────────────────────────────────────────


def seed_parties(db: object) -> dict[str, Party]:
    """Upsert all parties from data/parties.csv.

    Returns a dict mapping abbreviation → Party for use when seeding candidates.
    """
    from sqlalchemy.orm import Session

    assert isinstance(db, Session)

    rows = _read_csv(DATA_DIR / "parties.csv")
    by_abbrev: dict[str, Party] = {}
    created = updated = 0

    for row in rows:
        name = row["name"].strip()
        abbrev = row["abbreviation"].strip()
        alliance = row.get("alliance", "").strip() or None
        color = row["color_hex"].strip()

        party = db.query(Party).filter_by(name=name).first()
        if party is None:
            party = Party(name=name, abbreviation=abbrev, alliance=alliance, color_hex=color)
            db.add(party)
            db.flush()
            created += 1
        else:
            party.abbreviation = abbrev
            party.alliance = alliance
            party.color_hex = color
            updated += 1

        by_abbrev[abbrev] = party

    db.commit()
    print(f"Parties: {created} created, {updated} updated.")
    return by_abbrev


def seed_constituencies(db: object, election: Election) -> dict[int, Constituency]:
    """Upsert constituencies from data/constituencies.csv.

    Returns a dict mapping constituency number → Constituency.
    """
    from sqlalchemy.orm import Session

    assert isinstance(db, Session)

    rows = _read_csv(DATA_DIR / "constituencies.csv")
    by_number: dict[int, Constituency] = {}
    created = 0

    for row in rows:
        number = int(row["number"])
        existing = db.query(Constituency).filter_by(election_id=election.id, number=number).first()
        if existing:
            by_number[number] = existing
            continue

        c = Constituency(
            election_id=election.id,
            number=number,
            name=row["name"].strip(),
            district=row["district"].strip(),
            population=None,
        )
        db.add(c)
        db.flush()
        by_number[number] = c
        created += 1

    db.commit()
    print(f"Constituencies: {created} created, {len(rows) - created} already existed.")
    return by_number


def seed_candidates(
    db: object,
    constituencies: dict[int, Constituency],
    parties_by_abbrev: dict[str, Party],
) -> None:
    """Insert provisional candidates from data/candidates_provisional.csv.

    Looks up parties by abbreviation first, then by full name, then creates
    a placeholder party if neither matches.
    """
    from sqlalchemy.orm import Session

    assert isinstance(db, Session)

    rows = _read_csv(DATA_DIR / "candidates_provisional.csv")
    created = skipped = unmatched_party = 0

    for row in rows:
        candidate_name = row["candidate"].strip()
        if not candidate_name:
            continue  # party announced but candidate not yet named — skip

        number = int(row["constituency_number"])
        constituency = constituencies.get(number)
        if constituency is None:
            print(f"  WARNING: constituency {number} not in DB — skipping candidate row")
            continue

        # Resolve party: try abbreviation first, then full name lookup in DB
        party_raw = row["party"].strip()
        party = parties_by_abbrev.get(party_raw)
        if party is None:
            party = db.query(Party).filter_by(name=party_raw).first()
        if party is None:
            party = Party(name=party_raw, abbreviation=party_raw[:15], color_hex="#888888")
            db.add(party)
            db.flush()
            unmatched_party += 1

        exists = (
            db.query(Candidate)
            .filter_by(constituency_id=constituency.id, name=candidate_name)
            .first()
        )
        if exists:
            skipped += 1
            continue

        db.add(
            Candidate(
                constituency_id=constituency.id,
                name=candidate_name,
                party_id=party.id,
            )
        )
        created += 1

    db.commit()
    print(f"Candidates: {created} created, {skipped} already existed.", end="")
    if unmatched_party:
        print(
            f"  ({unmatched_party} new parties auto-created — add them to data/parties.csv)",
            end="",
        )
    print()


# ── Main ──────────────────────────────────────────────────────────────────────


def seed(election_id: int) -> None:
    """Seed parties, constituencies, and provisional candidates."""
    db = SessionLocal()
    try:
        election = db.get(Election, election_id)
        if election is None:
            election = Election(name="Tamil Nadu 2026", year=2026, active=True)
            db.add(election)
            db.flush()
            db.commit()
            print(f"Created election: {election.name} (id={election.id})")

        parties_by_abbrev = seed_parties(db)
        constituencies = seed_constituencies(db, election)
        seed_candidates(db, constituencies, parties_by_abbrev)

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--election-id",
        type=int,
        default=1,
        help="Election ID to seed into (default: 1; created if absent)",
    )
    args = parser.parse_args()
    seed(args.election_id)
