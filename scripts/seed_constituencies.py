"""Seed the database with Tamil Nadu 2026 assembly constituency data.

Usage:
    python scripts/seed_constituencies.py [--election-id N]

The script is idempotent: running it twice will not create duplicates.
It reads from data/constituencies.csv if present, otherwise falls back
to the bundled minimal dataset.

CSV format (header row required):
    number,name,district,population,current_mla,current_party
"""

import argparse
import csv
import sys
from pathlib import Path

# Allow running as a top-level script
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models.constituency import Constituency, Party
from app.models.election import Election

# Minimal built-in dataset — enough to verify the app works.
# Replace with a full data/constituencies.csv for production.
BUILTIN_DATA: list[dict[str, str]] = [
    {
        "number": "1",
        "name": "Gummidipoondi",
        "district": "Tiruvallur",
        "population": "",
        "current_mla": "",
        "current_party": "DMK",
    },
    {
        "number": "2",
        "name": "Ponneri",
        "district": "Tiruvallur",
        "population": "",
        "current_mla": "",
        "current_party": "DMK",
    },
    {
        "number": "3",
        "name": "Tiruttani",
        "district": "Tiruvallur",
        "population": "",
        "current_mla": "",
        "current_party": "AIADMK",
    },
]


def get_or_create_party(db: object, name: str) -> Party:
    """Return an existing party or create one with sensible defaults."""
    from sqlalchemy.orm import Session

    assert isinstance(db, Session)
    party = db.query(Party).filter_by(name=name).first()
    if party is None:
        party = Party(name=name, abbreviation=name[:10])
        db.add(party)
        db.flush()
    return party


def seed(election_id: int) -> None:
    """Seed constituencies for the given election."""
    db = SessionLocal()
    try:
        election = db.get(Election, election_id)
        if election is None:
            # Create a default election if none exists
            election = Election(name="Tamil Nadu 2026", year=2026, active=True)
            db.add(election)
            db.flush()
            print(f"Created election: {election.name} (id={election.id})")

        csv_path = Path(__file__).parent.parent / "data" / "constituencies.csv"
        if csv_path.exists():
            rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
            print(f"Loading {len(rows)} constituencies from {csv_path}")
        else:
            rows = BUILTIN_DATA
            print(f"No CSV found at {csv_path}, using built-in sample data ({len(rows)} rows)")

        created = 0
        for row in rows:
            existing = (
                db.query(Constituency)
                .filter_by(election_id=election.id, number=int(row["number"]))
                .first()
            )
            if existing:
                continue

            party_name = row.get("current_party", "").strip()
            party = get_or_create_party(db, party_name) if party_name else None

            constituency = Constituency(
                election_id=election.id,
                number=int(row["number"]),
                name=row["name"].strip(),
                district=row["district"].strip(),
                population=int(row["population"]) if row.get("population") else None,
                current_mla=row.get("current_mla", "").strip() or None,
                current_party_id=party.id if party else None,
            )
            db.add(constituency)
            created += 1

        db.commit()
        print(f"Done. Created {created} constituencies.")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--election-id", type=int, default=1, help="Election ID to seed into")
    args = parser.parse_args()
    seed(args.election_id)
