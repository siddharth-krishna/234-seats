"""Admin routes: seat management, result entry, writeup editing."""

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models.constituency import Constituency
from app.models.election import Election
from app.models.result import Result
from app.models.user import User

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="app/templates")


def _get_constituency_or_404(db: Session, constituency_id: int) -> Constituency:
    c = db.get(Constituency, constituency_id)
    if c is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Constituency not found")
    return c


# ── Dashboard ──────────────────────────────────────────────────────────────────


@router.get("", response_class=HTMLResponse)
def admin_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> HTMLResponse:
    """Admin dashboard: list all constituencies with management actions."""
    elections = db.query(Election).order_by(Election.year.desc()).all()
    active = next((e for e in elections if e.active), None)
    constituencies = (
        db.query(Constituency)
        .filter_by(election_id=active.id)
        .order_by(Constituency.number)
        .all()
        if active
        else []
    )
    return templates.TemplateResponse(
        request,
        "admin/dashboard.html",
        {
            "current_user": current_user,
            "elections": elections,
            "active_election": active,
            "constituencies": constituencies,
        },
    )


# ── Per-seat management page ───────────────────────────────────────────────────


@router.get("/seat/{constituency_id}", response_class=HTMLResponse)
def admin_seat(
    constituency_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> HTMLResponse:
    """Per-seat admin page: edit writeup and enter result."""
    constituency = _get_constituency_or_404(db, constituency_id)
    return templates.TemplateResponse(
        request,
        "admin/seat.html",
        {"current_user": current_user, "constituency": constituency},
    )


# ── Toggle predictions open/closed ────────────────────────────────────────────


@router.post("/seat/{constituency_id}/predictions/open")
def open_predictions(
    constituency_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> HTMLResponse:
    """Open predictions for a seat. Returns an HTMX status badge or redirects."""
    c = _get_constituency_or_404(db, constituency_id)
    c.predictions_open = True
    db.commit()
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            request, "admin/_seat_row.html", {"c": c}
        )
    return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)


@router.post("/seat/{constituency_id}/predictions/close")
def close_predictions(
    constituency_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> HTMLResponse:
    """Close predictions for a seat."""
    c = _get_constituency_or_404(db, constituency_id)
    c.predictions_open = False
    db.commit()
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            request, "admin/_seat_row.html", {"c": c}
        )
    return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)


# ── Result entry ───────────────────────────────────────────────────────────────


@router.post("/seat/{constituency_id}/result")
def enter_result(
    constituency_id: int,
    winner_name: str = Form(...),
    winner_party: str = Form(...),
    winner_vote_share_raw: str = Form(default="", alias="winner_vote_share"),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> RedirectResponse:
    """Create or update the official result for a seat."""
    _get_constituency_or_404(db, constituency_id)

    try:
        winner_vote_share: float | None = (
            float(winner_vote_share_raw) if winner_vote_share_raw.strip() else None
        )
    except ValueError:
        winner_vote_share = None

    result = db.query(Result).filter_by(constituency_id=constituency_id).first()
    if result is None:
        result = Result(constituency_id=constituency_id)
        db.add(result)

    result.winner_name = winner_name.strip()
    result.winner_party = winner_party.strip()
    result.winner_vote_share = winner_vote_share
    db.commit()
    return RedirectResponse(
        url=f"/admin/seat/{constituency_id}", status_code=status.HTTP_302_FOUND
    )


# ── Writeup editing ────────────────────────────────────────────────────────────


@router.post("/seat/{constituency_id}/writeup")
def save_writeup(
    constituency_id: int,
    writeup: str = Form(default=""),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> RedirectResponse:
    """Save the writeup for a constituency."""
    c = _get_constituency_or_404(db, constituency_id)
    c.writeup = writeup.strip() or None
    db.commit()
    return RedirectResponse(
        url=f"/admin/seat/{constituency_id}", status_code=status.HTTP_302_FOUND
    )


# ── Election activation ────────────────────────────────────────────────────────


@router.post("/election/{election_id}/activate")
def activate_election(
    election_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> RedirectResponse:
    """Set one election as active, deactivating all others."""
    election = db.get(Election, election_id)
    if election is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    db.query(Election).update({"active": False})
    election.active = True
    db.commit()
    return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)
