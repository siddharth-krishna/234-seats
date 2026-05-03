"""Admin routes: seat management, result entry, writeup editing."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models.candidate import Candidate
from app.models.constituency import Constituency, Party
from app.models.election import Election
from app.models.result import ProvisionalResultSet, Result
from app.models.user import User
from app.services.provisional_results import (
    ProvisionalResultValidationError,
    create_provisional_result_set,
    datetime_local_value,
    default_counted_at,
    get_result_form_constituencies,
    update_provisional_result_set,
)
from app.templates_config import templates

router = APIRouter(prefix="/admin")


def _get_constituency_or_404(db: Session, constituency_id: int) -> Constituency:
    c = db.get(Constituency, constituency_id)
    if c is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Constituency not found")
    return c


def _get_active_election_or_404(db: Session) -> Election:
    election = db.query(Election).filter_by(active=True).first()
    if election is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active election")
    return election


def _get_provisional_result_set_or_404(db: Session, result_set_id: int) -> ProvisionalResultSet:
    result_set = db.get(ProvisionalResultSet, result_set_id)
    if result_set is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provisional result set not found",
        )
    return result_set


def _form_values(form: dict[str, object]) -> dict[str, str]:
    """Return form values as plain strings for template re-rendering."""
    return {key: str(value) for key, value in form.items()}


# ── Dashboard ──────────────────────────────────────────────────────────────────


@router.get("", response_class=HTMLResponse)
def admin_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> Response:
    """Admin dashboard: list all constituencies with management actions."""
    elections = db.query(Election).order_by(Election.year.desc()).all()
    active = next((e for e in elections if e.active), None)
    constituencies = (
        db.query(Constituency).filter_by(election_id=active.id).order_by(Constituency.number).all()
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


# ── Provisional results ───────────────────────────────────────────────────────


@router.get("/results", response_class=HTMLResponse)
def admin_results(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> Response:
    """List provisional result sets for the active election."""
    active = db.query(Election).filter_by(active=True).first()
    result_sets = (
        db.query(ProvisionalResultSet)
        .filter_by(election_id=active.id)
        .order_by(ProvisionalResultSet.counted_at.desc(), ProvisionalResultSet.id.desc())
        .all()
        if active
        else []
    )
    return templates.TemplateResponse(
        request,
        "admin/results.html",
        {
            "current_user": current_user,
            "active_election": active,
            "result_sets": result_sets,
        },
    )


@router.get("/results/new", response_class=HTMLResponse)
def new_provisional_results(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> Response:
    """Show a form for a new provisional result set."""
    election = _get_active_election_or_404(db)
    constituencies = get_result_form_constituencies(db, election.id)
    return templates.TemplateResponse(
        request,
        "admin/result_form.html",
        {
            "current_user": current_user,
            "active_election": election,
            "result_set": None,
            "constituencies": constituencies,
            "counted_at_value": datetime_local_value(default_counted_at()),
        },
    )


@router.post("/results")
async def create_provisional_results(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> Response:
    """Create a provisional result set."""
    election = _get_active_election_or_404(db)
    constituencies = get_result_form_constituencies(db, election.id)
    form = await request.form()
    try:
        result_set = create_provisional_result_set(db, election, form, constituencies)
    except ProvisionalResultValidationError as exc:
        db.rollback()
        return templates.TemplateResponse(
            request,
            "admin/result_form.html",
            {
                "current_user": current_user,
                "active_election": election,
                "result_set": None,
                "constituencies": constituencies,
                "counted_at_value": str(form.get("counted_at", "")),
                "form_values": _form_values(dict(form)),
                "errors": exc.errors,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return RedirectResponse(
        url=f"/admin/results/{result_set.id}/edit",
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/results/{result_set_id}/edit", response_class=HTMLResponse)
def edit_provisional_results(
    result_set_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> Response:
    """Show a form for editing a provisional result set."""
    result_set = _get_provisional_result_set_or_404(db, result_set_id)
    constituencies = get_result_form_constituencies(db, result_set.election_id)
    existing_candidate_results = {
        f"{seat.constituency_id}:{candidate_result.candidate_id}": candidate_result
        for seat in result_set.seat_results
        for candidate_result in seat.candidate_results
    }
    existing_seat_results = {seat.constituency_id: seat for seat in result_set.seat_results}
    return templates.TemplateResponse(
        request,
        "admin/result_form.html",
        {
            "current_user": current_user,
            "active_election": result_set.election,
            "result_set": result_set,
            "constituencies": constituencies,
            "counted_at_value": datetime_local_value(result_set.counted_at),
            "existing_candidate_results": existing_candidate_results,
            "existing_seat_results": existing_seat_results,
        },
    )


@router.post("/results/{result_set_id}")
async def update_provisional_results(
    result_set_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> Response:
    """Update a provisional result set."""
    result_set = _get_provisional_result_set_or_404(db, result_set_id)
    constituencies = get_result_form_constituencies(db, result_set.election_id)
    form = await request.form()
    try:
        update_provisional_result_set(db, result_set, form, constituencies)
    except ProvisionalResultValidationError as exc:
        db.rollback()
        existing_candidate_results = {
            f"{seat.constituency_id}:{candidate_result.candidate_id}": candidate_result
            for seat in result_set.seat_results
            for candidate_result in seat.candidate_results
        }
        existing_seat_results = {seat.constituency_id: seat for seat in result_set.seat_results}
        return templates.TemplateResponse(
            request,
            "admin/result_form.html",
            {
                "current_user": current_user,
                "active_election": result_set.election,
                "result_set": result_set,
                "constituencies": constituencies,
                "counted_at_value": str(form.get("counted_at", "")),
                "existing_candidate_results": existing_candidate_results,
                "existing_seat_results": existing_seat_results,
                "form_values": _form_values(dict(form)),
                "errors": exc.errors,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return RedirectResponse(
        url=f"/admin/results/{result_set.id}/edit",
        status_code=status.HTTP_302_FOUND,
    )


# ── Per-seat management page ───────────────────────────────────────────────────


@router.get("/seat/{constituency_id}", response_class=HTMLResponse)
def admin_seat(
    constituency_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> Response:
    """Per-seat admin page: edit writeup and enter result."""
    constituency = _get_constituency_or_404(db, constituency_id)
    parties = db.query(Party).order_by(Party.name).all()
    return templates.TemplateResponse(
        request,
        "admin/seat.html",
        {"current_user": current_user, "constituency": constituency, "parties": parties},
    )


# ── Toggle predictions open/closed ────────────────────────────────────────────


@router.post("/seat/{constituency_id}/predictions/open")
def open_predictions(
    constituency_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Response:
    """Open predictions for a seat. Returns an HTMX status badge or redirects."""
    c = _get_constituency_or_404(db, constituency_id)
    c.predictions_open = True
    db.commit()
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(request, "admin/_seat_row.html", {"c": c})
    return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)


@router.post("/seat/{constituency_id}/predictions/close")
def close_predictions(
    constituency_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Response:
    """Close predictions for a seat."""
    c = _get_constituency_or_404(db, constituency_id)
    c.predictions_open = False
    db.commit()
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(request, "admin/_seat_row.html", {"c": c})
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
    return RedirectResponse(url=f"/admin/seat/{constituency_id}", status_code=status.HTTP_302_FOUND)


# ── Writeup editing ────────────────────────────────────────────────────────────


@router.post("/seat/{constituency_id}/writeup", response_model=None)
def save_writeup(
    constituency_id: int,
    request: Request,
    writeup: str = Form(default=""),
    image_url: str = Form(default=""),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Response:
    """Save the writeup for a constituency."""
    c = _get_constituency_or_404(db, constituency_id)
    c.writeup = writeup.strip() or None
    c.image_url = image_url.strip() or None
    db.commit()
    if request.headers.get("HX-Request"):
        saved_at = datetime.now(tz=UTC).strftime("%H:%M")
        snippet = (
            f'<span id="writeup-status" class="text-sm text-green-700">'
            f"Saved at {saved_at} UTC</span>"
        )
        return HTMLResponse(content=snippet)
    return RedirectResponse(url=f"/admin/seat/{constituency_id}", status_code=status.HTTP_302_FOUND)


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


# ── Party management ───────────────────────────────────────────────────────────


@router.get("/parties", response_class=HTMLResponse)
def parties_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> Response:
    """List all parties with edit and delete controls."""
    parties = db.query(Party).order_by(Party.name).all()
    return templates.TemplateResponse(
        request,
        "admin/parties.html",
        {"current_user": current_user, "parties": parties},
    )


@router.post("/parties")
def create_party(
    name: str = Form(...),
    abbreviation: str = Form(...),
    alliance: str = Form(default=""),
    color_hex: str = Form(default="#cccccc"),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> RedirectResponse:
    """Create a new party."""
    if db.query(Party).filter_by(name=name.strip()).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Party name already exists"
        )
    db.add(
        Party(
            name=name.strip(),
            abbreviation=abbreviation.strip(),
            alliance=alliance.strip() or None,
            color_hex=color_hex,
        )
    )
    db.commit()
    return RedirectResponse(url="/admin/parties", status_code=status.HTTP_302_FOUND)


@router.post("/parties/{party_id}")
def update_party(
    party_id: int,
    name: str = Form(...),
    abbreviation: str = Form(...),
    alliance: str = Form(default=""),
    color_hex: str = Form(default="#cccccc"),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> RedirectResponse:
    """Update an existing party."""
    party = db.get(Party, party_id)
    if party is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    party.name = name.strip()
    party.abbreviation = abbreviation.strip()
    party.alliance = alliance.strip() or None
    party.color_hex = color_hex
    db.commit()
    return RedirectResponse(url="/admin/parties", status_code=status.HTTP_302_FOUND)


@router.post("/parties/{party_id}/delete")
def delete_party(
    party_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> RedirectResponse:
    """Delete a party. Constituencies using this party lose their current_party."""
    party = db.get(Party, party_id)
    if party is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    # Null out FK references before deleting
    db.query(Constituency).filter_by(current_party_id=party_id).update({"current_party_id": None})
    db.delete(party)
    db.commit()
    return RedirectResponse(url="/admin/parties", status_code=status.HTTP_302_FOUND)


# ── Candidate management ───────────────────────────────────────────────────────


@router.post("/seat/{constituency_id}/candidates")
def add_candidate(
    constituency_id: int,
    name: str = Form(...),
    party_id: str = Form(default=""),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> RedirectResponse:
    """Add a candidate to a constituency."""
    _get_constituency_or_404(db, constituency_id)
    resolved_party_id: int | None = int(party_id) if party_id.strip() else None
    db.add(
        Candidate(
            constituency_id=constituency_id,
            name=name.strip(),
            party_id=resolved_party_id,
        )
    )
    db.commit()
    return RedirectResponse(url=f"/admin/seat/{constituency_id}", status_code=status.HTTP_302_FOUND)


@router.post("/seat/{constituency_id}/candidates/{candidate_id}")
def update_candidate(
    constituency_id: int,
    candidate_id: int,
    name: str = Form(...),
    party_id: str = Form(default=""),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> RedirectResponse:
    """Update a candidate's name and party."""
    candidate = db.get(Candidate, candidate_id)
    if candidate is None or candidate.constituency_id != constituency_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    candidate.name = name.strip()
    candidate.party_id = int(party_id) if party_id.strip() else None
    db.commit()
    return RedirectResponse(url=f"/admin/seat/{constituency_id}", status_code=status.HTTP_302_FOUND)


@router.post("/seat/{constituency_id}/candidates/{candidate_id}/delete")
def delete_candidate(
    constituency_id: int,
    candidate_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> RedirectResponse:
    """Remove a candidate from a constituency."""
    candidate = db.get(Candidate, candidate_id)
    if candidate is None or candidate.constituency_id != constituency_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    db.delete(candidate)
    db.commit()
    return RedirectResponse(url=f"/admin/seat/{constituency_id}", status_code=status.HTTP_302_FOUND)
