"""Home page: leaderboard, theme toggle, and constituency list."""

from fastapi import APIRouter, Cookie, Depends, Form, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_login
from app.models.constituency import Constituency
from app.models.election import Election
from app.models.prediction import Prediction
from app.models.user import User
from app.services.provisional_results import (
    get_latest_provisional_results_by_constituency,
    provisional_winner,
)
from app.services.scoring import SORT_KEYS, compute_scores, sort_scores
from app.templates_config import templates

router = APIRouter()

THEME_COOKIE_NAME = "theme"
THEME_COOKIE_MAX_AGE = 60 * 60 * 24 * 365
DEFAULT_SEAT_SORT = "actionable"


def _constituency_sort_key(
    constituency: Constituency,
    predicted_ids: set[int],
    result_display: dict[int, dict[str, str | bool]],
    sort_by: str,
) -> str | int | tuple[int, int, str]:
    """Return the sort key for a constituency row."""
    if sort_by == DEFAULT_SEAT_SORT:
        return (
            0 if constituency.predictions_open else 1,
            0 if constituency.id not in predicted_ids else 1,
            constituency.name.lower(),
        )
    if sort_by == "district":
        return constituency.district.lower()
    if sort_by == "status":
        return 0 if constituency.predictions_open else 1
    if sort_by == "predicted":
        return 0 if constituency.id in predicted_ids else 1
    if sort_by == "result":
        result = result_display.get(constituency.id)
        if result is None:
            return "zzz"
        return str(result["label"]).lower()
    return constituency.name.lower()


@router.post("/theme")
def toggle_theme(
    next_url: str = Form(default="/", alias="next"),
    current_theme: str | None = Cookie(default=None, alias=THEME_COOKIE_NAME),
) -> RedirectResponse:
    """Toggle the user's theme preference and redirect back."""
    next_theme = "light" if current_theme == "dark" else "dark"
    redirect = RedirectResponse(url=next_url, status_code=status.HTTP_302_FOUND)
    redirect.set_cookie(
        key=THEME_COOKIE_NAME,
        value=next_theme,
        max_age=THEME_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return redirect


@router.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    sort: str = Query(default="correct_seats"),
    dir: str = Query(default="desc"),
    seat_sort: str = Query(default=DEFAULT_SEAT_SORT),
    seat_dir: str = Query(default="asc"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_login),
) -> Response:
    """Render the home page with the leaderboard and constituency list."""
    election = db.query(Election).filter_by(active=True).first()

    scores = []
    constituencies: list[Constituency] = []

    if election is not None:
        descending = dir != "asc"
        scores = sort_scores(compute_scores(db, election.id), sort_by=sort, descending=descending)
        constituencies = (
            db.query(Constituency)
            .filter_by(election_id=election.id)
            .order_by(Constituency.number)
            .all()
        )

    provisional_results = (
        get_latest_provisional_results_by_constituency(db, election.id)
        if election is not None
        else {}
    )
    result_display: dict[int, dict[str, str | bool]] = {}
    for constituency in constituencies:
        provisional_result = provisional_results.get(constituency.id)
        provisional_leader = (
            provisional_winner(provisional_result) if provisional_result is not None else None
        )
        if provisional_leader is not None:
            party_label = (
                provisional_leader.party.abbreviation if provisional_leader.party else "Independent"
            )
            result_display[constituency.id] = {
                "label": f"{provisional_leader.candidate_name} ({party_label})",
                "provisional": True,
            }
        elif constituency.result is not None:
            result_display[constituency.id] = {
                "label": (
                    f"{constituency.result.winner_name} " f"({constituency.result.winner_party})"
                ),
                "provisional": False,
            }

    open_seats_count = sum(1 for c in constituencies if c.predictions_open)

    # Set of constituency numbers the current user has already predicted on
    predicted_numbers: set[int] = set()
    predicted_ids: set[int] = set()
    if election is not None:
        user_predictions = (
            db.query(Prediction)
            .filter_by(user_id=current_user.id)
            .join(Constituency)
            .filter(Constituency.election_id == election.id)
            .all()
        )
        predicted_numbers = {p.constituency.number for p in user_predictions}
        predicted_ids = {p.constituency_id for p in user_predictions}

    seat_descending = seat_dir == "desc"
    sorted_constituencies = sorted(
        constituencies,
        key=lambda c: (
            _constituency_sort_key(c, predicted_ids, result_display, seat_sort),
            c.name.lower(),
        ),
        reverse=seat_descending,
    )

    # Map data for SVG colour-coding keyed by constituency number (AC_NO)
    map_data = {
        c.number: {
            "id": c.id,
            "name": c.name,
            "open": c.predictions_open,
            "predicted": c.number in predicted_numbers,
            "result": c.id in result_display,
        }
        for c in constituencies
    }

    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "current_user": current_user,
            "election": election,
            "scores": scores,
            "constituencies": sorted_constituencies,
            "open_seats_count": open_seats_count,
            "map_data": map_data,
            "result_display": result_display,
            "sort": sort,
            "dir": dir,
            "seat_sort": seat_sort,
            "seat_dir": seat_dir,
            "sort_keys": list(SORT_KEYS.keys()),
        },
    )
