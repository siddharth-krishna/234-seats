"""Scrape ECI provisional results for open seats and post them to the API.

Usage:
    python scripts/scrape_eci_provisional_results.py \
        --api-url http://localhost:8000 \
        --token "$PROVISIONAL_RESULTS_API_TOKEN"

The script reads the active election's open seats from the local database,
fetches the matching ECI constituency pages into a temp cache directory, parses
candidate vote shares, and posts one result snapshot to /api/provisional-results.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import requests
    from bs4 import BeautifulSoup
    from bs4.element import Tag
except ImportError:
    print(
        "Missing dependencies.\nRun:  pip install requests beautifulsoup4",
        file=sys.stderr,
    )
    sys.exit(1)

from app.database import SessionLocal
from app.models.constituency import Constituency
from app.models.election import Election

BASE_URL = "https://results.eci.gov.in/ResultAcGenMay2026"
STATE_CODE = "S22"
REQUEST_DELAY_SECONDS = 0.5
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Referer": BASE_URL + "/index.htm",
    "Upgrade-Insecure-Requests": "1",
}


@dataclass(frozen=True)
class OpenSeat:
    """A constituency that is open for betting locally."""

    number: int
    name: str


@dataclass(frozen=True)
class ScrapedCandidate:
    """A candidate row scraped from an ECI constituency page."""

    name: str
    party: str
    votes: int | None
    vote_share: float | None


@dataclass(frozen=True)
class ScrapedSeat:
    """A constituency result scraped from ECI."""

    constituency_number: int
    votes_counted: int | None
    candidates: list[ScrapedCandidate]
    counted_at: datetime | None


def get_open_seats() -> list[OpenSeat]:
    """Return active-election seats that are still open for betting."""
    db = SessionLocal()
    try:
        election = db.query(Election).filter_by(active=True).first()
        if election is None:
            raise RuntimeError("No active election found.")
        rows = (
            db.query(Constituency)
            .filter_by(election_id=election.id, predictions_open=True)
            .order_by(Constituency.number)
            .all()
        )
        return [OpenSeat(number=row.number, name=row.name) for row in rows]
    finally:
        db.close()


def build_eci_url(constituency_number: int) -> str:
    """Return the ECI constituency page URL for a Tamil Nadu assembly seat."""
    return f"{BASE_URL}/Constituencywise{STATE_CODE}{constituency_number}.htm"


def fetch_page(
    session: requests.Session,
    url: str,
    cache_path: Path,
    refresh: bool,
) -> str:
    """Fetch a page into the cache and return its HTML."""
    if cache_path.exists() and not refresh:
        return cache_path.read_text(encoding="utf-8")

    response = session.get(url, timeout=30)
    response.raise_for_status()
    cache_path.write_text(response.text, encoding="utf-8")
    return response.text


def scrape_open_seats(
    seats: list[OpenSeat],
    cache_dir: Path,
    refresh: bool,
    use_browser: bool,
    headed: bool,
    browser_channel: str | None,
) -> list[ScrapedSeat]:
    """Scrape all configured open seats from ECI."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    if use_browser:
        fetch_pages_with_browser(seats, cache_dir, refresh, headed, browser_channel)

    session = requests.Session()
    session.headers.update(BROWSER_HEADERS)
    if not use_browser:
        warm_eci_session(session)
    results: list[ScrapedSeat] = []

    for seat in seats:
        url = build_eci_url(seat.number)
        cache_path = cache_dir / f"Constituencywise{STATE_CODE}{seat.number}.htm"
        action = "Reading cached" if use_browser else "Fetching"
        print(f"{action} #{seat.number} {seat.name}: {url}")
        if use_browser and not cache_path.exists():
            print("  Warning: browser did not cache this page; skipping this seat.")
            continue
        try:
            html = (
                cache_path.read_text(encoding="utf-8")
                if use_browser
                else fetch_page(session, url, cache_path, refresh)
            )
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else "unknown"
            print(f"  Warning: ECI returned HTTP {status_code}; skipping this seat.")
            continue
        except requests.RequestException as exc:
            print(f"  Warning: failed to fetch page: {exc}; skipping this seat.")
            continue
        scraped = parse_constituency_page(html, seat.number)
        if scraped.candidates:
            results.append(scraped)
        else:
            print(f"  Warning: no candidate table found for #{seat.number} {seat.name}")
        time.sleep(REQUEST_DELAY_SECONDS)

    return results


def fetch_pages_with_browser(
    seats: list[OpenSeat],
    cache_dir: Path,
    refresh: bool,
    headed: bool,
    browser_channel: str | None,
) -> None:
    """Fetch ECI pages into the cache with a real browser via Playwright."""
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "Missing dependency for --browser.\n"
            "Run:  pip install playwright && python -m playwright install chromium",
            file=sys.stderr,
        )
        sys.exit(1)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed, channel=browser_channel)
        context = browser.new_context(
            locale="en-US",
            viewport={"width": 1440, "height": 1000},
        )
        page = context.new_page()
        try:
            print(f"Opening ECI index in browser: {BASE_URL}/index.htm")
            index_response = page.goto(
                BASE_URL + "/index.htm",
                wait_until="domcontentloaded",
                timeout=45000,
            )
            if index_response is not None and index_response.status >= 400:
                print(f"  Warning: browser got HTTP {index_response.status} for ECI index.")

            for seat in seats:
                cache_path = cache_dir / f"Constituencywise{STATE_CODE}{seat.number}.htm"
                if cache_path.exists() and not refresh:
                    continue

                url = build_eci_url(seat.number)
                print(f"Browser fetching #{seat.number} {seat.name}: {url}")
                try:
                    response = page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    status_code = response.status if response is not None else None
                    if status_code is not None and status_code >= 400:
                        print(f"  Warning: browser got HTTP {status_code}; not caching page.")
                        continue
                    page.wait_for_load_state("networkidle", timeout=10000)
                except PlaywrightTimeoutError:
                    print("  Warning: browser timed out; caching current DOM anyway.")
                except PlaywrightError as exc:
                    print(f"  Warning: browser failed to fetch page: {exc}; skipping this seat.")
                    continue

                cache_path.write_text(page.content(), encoding="utf-8")
                time.sleep(REQUEST_DELAY_SECONDS)
        finally:
            context.close()
            browser.close()


def warm_eci_session(session: requests.Session) -> None:
    """Visit the ECI index page first so constituency requests carry cookies."""
    try:
        session.get(BASE_URL + "/index.htm", timeout=30).raise_for_status()
    except requests.RequestException as exc:
        print(f"Warning: failed to warm ECI session: {exc}")


def parse_constituency_page(html: str, constituency_number: int) -> ScrapedSeat:
    """Parse one ECI constituency result page."""
    soup = BeautifulSoup(html, "html.parser")
    counted_at = parse_last_updated(soup)
    candidates = parse_candidate_table(soup)
    candidates = fill_missing_vote_shares(candidates)
    votes_counted = sum(candidate.votes or 0 for candidate in candidates) or None
    return ScrapedSeat(
        constituency_number=constituency_number,
        votes_counted=votes_counted,
        candidates=candidates,
        counted_at=counted_at,
    )


def parse_candidate_table(soup: BeautifulSoup) -> list[ScrapedCandidate]:
    """Return candidate rows from the first ECI result table."""
    for table in soup.find_all("table"):
        if not isinstance(table, Tag):
            continue
        rows = table.find_all("tr")
        if not rows:
            continue
        headers = [_cell_text(cell) for cell in rows[0].find_all(["th", "td"])]
        indexes = _candidate_table_indexes(headers)
        if indexes is None:
            continue

        candidate_index, party_index, votes_index, share_index = indexes
        candidates: list[ScrapedCandidate] = []
        for row in rows[1:]:
            cells = row.find_all(["th", "td"])
            if len(cells) <= max(candidate_index, party_index, votes_index):
                continue
            name = _clean_candidate_name(_cell_text(cells[candidate_index]))
            if not name or name.lower() == "total":
                continue
            candidates.append(
                ScrapedCandidate(
                    name=name,
                    party=_clean_party(_cell_text(cells[party_index])),
                    votes=_parse_int(_cell_text(cells[votes_index])),
                    vote_share=_parse_float(_cell_text(cells[share_index]))
                    if share_index is not None and len(cells) > share_index
                    else None,
                )
            )
        if candidates:
            return candidates
    return []


def parse_last_updated(soup: BeautifulSoup) -> datetime | None:
    """Parse ECI's last-updated timestamp from page text."""
    page_text = " ".join(soup.stripped_strings)
    marker = "Last Updated at "
    if marker not in page_text:
        return None
    timestamp_text = page_text.split(marker, maxsplit=1)[1].strip()
    timestamp_text = timestamp_text.split(" Disclaimer", maxsplit=1)[0].strip()
    timestamp_text = " ".join(timestamp_text.split()[:5])
    try:
        return datetime.strptime(timestamp_text, "%I:%M %p On %d/%m/%Y")
    except ValueError:
        return None


def fill_missing_vote_shares(candidates: list[ScrapedCandidate]) -> list[ScrapedCandidate]:
    """Derive missing vote shares from total votes when ECI omits percentages."""
    total_votes = sum(candidate.votes or 0 for candidate in candidates)
    if total_votes <= 0:
        return candidates
    return [
        ScrapedCandidate(
            name=candidate.name,
            party=candidate.party,
            votes=candidate.votes,
            vote_share=candidate.vote_share
            if candidate.vote_share is not None
            else round(((candidate.votes or 0) / total_votes) * 100, 2),
        )
        for candidate in candidates
    ]


def build_api_payload(seats: list[ScrapedSeat]) -> dict[str, Any]:
    """Build the JSON payload accepted by /api/provisional-results."""
    counted_at = max(
        (seat.counted_at for seat in seats if seat.counted_at is not None),
        default=datetime.now().replace(second=0, microsecond=0),
    )
    return {
        "counted_at": counted_at.isoformat(),
        "seats": [
            {
                "constituency_number": seat.constituency_number,
                "votes_counted": seat.votes_counted,
                "candidates": [
                    {
                        "name": candidate.name,
                        "party": candidate.party,
                        "vote_share": candidate.vote_share,
                    }
                    for candidate in seat.candidates
                    if candidate.vote_share is not None
                ],
            }
            for seat in seats
        ],
    }


def post_payload(api_url: str, token: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Post a provisional result payload to the app API."""
    url = api_url.rstrip("/") + "/api/provisional-results"
    response = requests.post(
        url,
        json=payload,
        headers={"X-Provisional-Results-Token": token},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    assert isinstance(data, dict)
    return data


def main() -> None:
    """Run the scraper CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--token", default=os.environ.get("PROVISIONAL_RESULTS_API_TOKEN"))
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(tempfile.gettempdir()) / "234seats-eci-results",
    )
    parser.add_argument("--refresh", action="store_true", help="Re-download cached ECI pages.")
    parser.add_argument(
        "--browser",
        action="store_true",
        help="Fetch ECI pages with Playwright before parsing cached HTML.",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Show the browser window when used with --browser.",
    )
    parser.add_argument(
        "--browser-channel",
        help="Playwright browser channel to use, for example 'chrome' or 'msedge'.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print payload without posting.")
    args = parser.parse_args()

    seats = get_open_seats()
    print(f"Found {len(seats)} open seats locally.")
    scraped = scrape_open_seats(
        seats,
        args.cache_dir,
        args.refresh,
        args.browser,
        args.headed,
        args.browser_channel,
    )
    if not scraped:
        print(
            "Error: no ECI pages were scraped. If every request returned 403, "
            "ECI is blocking non-browser traffic from this network.",
            file=sys.stderr,
        )
        sys.exit(1)
    payload = build_api_payload(scraped)

    if args.dry_run:
        print(json.dumps(payload, indent=2))
        return

    if not args.token:
        print("Error: pass --token or set PROVISIONAL_RESULTS_API_TOKEN.", file=sys.stderr)
        sys.exit(1)

    response = post_payload(args.api_url, args.token, payload)
    print(json.dumps(response, indent=2))


def _candidate_table_indexes(headers: list[str]) -> tuple[int, int, int, int | None] | None:
    """Return relevant column indexes for an ECI candidate table."""
    lowered = [header.lower() for header in headers]
    candidate_index = _first_index_containing(lowered, "candidate")
    party_index = _first_index_containing(lowered, "party")
    votes_index = _first_index_containing(lowered, "total")
    share_index = _first_index_containing(lowered, "%")
    if candidate_index is None or party_index is None or votes_index is None:
        return None
    return candidate_index, party_index, votes_index, share_index


def _first_index_containing(values: list[str], needle: str) -> int | None:
    """Return the first index containing a case-normalized substring."""
    for index, value in enumerate(values):
        if needle in value:
            return index
    return None


def _cell_text(cell: Tag) -> str:
    """Return normalized text from a table cell."""
    return " ".join(cell.stripped_strings)


def _clean_candidate_name(value: str) -> str:
    """Remove status suffixes from ECI candidate names."""
    words = value.strip().split()
    while words and words[-1].lower() in {"leading", "won"}:
        words.pop()
    return " ".join(words)


def _clean_party(value: str) -> str:
    """Return a compact party abbreviation/name from an ECI party cell."""
    text = " ".join(value.strip().split())
    if " - " in text:
        text = text.rsplit(" - ", maxsplit=1)[1].strip()
    parts = text.split()
    if len(parts) == 2 and parts[0] == parts[1]:
        return parts[0]
    return text


def _parse_int(value: str) -> int | None:
    """Parse an integer from ECI numeric text."""
    digits = "".join(character for character in value if character.isdigit())
    return int(digits) if digits else None


def _parse_float(value: str) -> float | None:
    """Parse a floating-point percentage from ECI numeric text."""
    allowed = "".join(character for character in value if character.isdigit() or character == ".")
    if not allowed:
        return None
    try:
        return float(allowed)
    except ValueError:
        return None


if __name__ == "__main__":
    main()
