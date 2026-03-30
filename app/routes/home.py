"""Home page: leaderboard and constituency list."""

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_login
from app.models.constituency import Constituency
from app.models.election import Election
from app.models.prediction import Prediction
from app.models.user import User
from app.services.scoring import SORT_KEYS, compute_scores, sort_scores
from app.templates_config import templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    sort: str = Query(default="correct_seats"),
    dir: str = Query(default="desc"),
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

    open_seats_count = sum(1 for c in constituencies if c.predictions_open)

    # Set of constituency numbers the current user has already predicted on
    predicted_numbers: set[int] = set()
    if election is not None:
        predicted_numbers = {
            p.constituency.number
            for p in db.query(Prediction)
            .filter_by(user_id=current_user.id)
            .join(Constituency)
            .filter(Constituency.election_id == election.id)
            .all()
        }

    # Map data for SVG colour-coding keyed by constituency number (AC_NO)
    map_data = {
        c.number: {
            "id": c.id,
            "name": c.name,
            "open": c.predictions_open,
            "predicted": c.number in predicted_numbers,
            "result": c.result is not None,
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
            "constituencies": constituencies,
            "open_seats_count": open_seats_count,
            "map_data": map_data,
            "sort": sort,
            "dir": dir,
            "sort_keys": list(SORT_KEYS.keys()),
        },
    )
