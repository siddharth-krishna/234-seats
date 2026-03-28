"""Bulk-import election results from a CSV file.

Usage:
    python scripts/import_results.py results.csv [--election-id N]

CSV format (header row required):
    constituency_number,winner_name,winner_party,winner_vote_share

- constituency_number: integer matching Constituency.number
- winner_name: string
- winner_party: string
- winner_vote_share: float (optional, leave blank if unknown)

Existing results are updated; missing constituencies are skipped with a warning.
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models.constituency import Constituency
from app.models.result import Result


def import_results(csv_path: Path, election_id: int) -> None:
    """Import results from *csv_path* into the given election."""
    if not csv_path.exists():
        print(f"Error: file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    db = SessionLocal()
    try:
        rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
        created = updated = skipped = 0

        for row in rows:
            number_str = row.get("constituency_number", "").strip()
            if not number_str:
                skipped += 1
                continue

            constituency = (
                db.query(Constituency)
                .filter_by(election_id=election_id, number=int(number_str))
                .first()
            )
            if constituency is None:
                print(f"  Warning: constituency #{number_str} not found — skipping")
                skipped += 1
                continue

            share_str = row.get("winner_vote_share", "").strip()
            try:
                vote_share: float | None = float(share_str) if share_str else None
            except ValueError:
                vote_share = None

            result = db.query(Result).filter_by(constituency_id=constituency.id).first()
            if result is None:
                result = Result(constituency_id=constituency.id)
                db.add(result)
                created += 1
            else:
                updated += 1

            result.winner_name = row["winner_name"].strip()
            result.winner_party = row["winner_party"].strip()
            result.winner_vote_share = vote_share

        db.commit()
        print(f"Done. Created {created}, updated {updated}, skipped {skipped}.")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_file", type=Path, help="Path to results CSV")
    parser.add_argument("--election-id", type=int, default=1)
    args = parser.parse_args()
    import_results(args.csv_file, args.election_id)
