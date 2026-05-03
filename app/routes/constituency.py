"""Constituency detail page and prediction submission."""

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_login
from app.models.candidate import Candidate
from app.models.constituency import Constituency
from app.models.prediction import Prediction
from app.models.user import User
from app.services.provisional_results import (
    get_latest_provisional_result_for_constituency,
    provisional_winner,
)
from app.templates_config import templates

router = APIRouter()


def _get_constituency_or_404(db: Session, constituency_id: int) -> Constituency:
    """Return the constituency or raise 404."""
    c = db.get(Constituency, constituency_id)
    if c is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Constituency not found")
    return c


def _build_context(
    constituency: Constituency,
    current_user: User,
    db: Session,
) -> dict:
    """Build the template context for the predictions section."""
    user_prediction = (
        db.query(Prediction)
        .filter_by(user_id=current_user.id, constituency_id=constituency.id)
        .first()
    )
    show_predictions = (not constituency.predictions_open) or (user_prediction is not None)
    all_predictions = (
        db.query(Prediction)
        .filter_by(constituency_id=constituency.id)
        .join(User)
        .order_by(Prediction.submitted_at)
        .all()
        if show_predictions
        else []
    )
    candidates = (
        db.query(Candidate)
        .filter_by(constituency_id=constituency.id)
        .order_by(Candidate.name)
        .all()
    )
    latest_provisional_result = get_latest_provisional_result_for_constituency(db, constituency.id)
    provisional_leader = (
        provisional_winner(latest_provisional_result)
        if latest_provisional_result is not None
        else None
    )
    return {
        "current_user": current_user,
        "constituency": constituency,
        "user_prediction": user_prediction,
        "show_predictions": show_predictions,
        "predictions": all_predictions,
        "candidates": candidates,
        "latest_provisional_result": latest_provisional_result,
        "provisional_leader": provisional_leader,
    }


@router.get("/seat/{constituency_id}", response_class=HTMLResponse)
def constituency_page(
    constituency_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_login),
) -> Response:
    """Render the constituency detail page."""
    constituency = _get_constituency_or_404(db, constituency_id)
    return templates.TemplateResponse(
        request, "constituency.html", _build_context(constituency, current_user, db)
    )


@router.post("/seat/{constituency_id}/predict", response_class=HTMLResponse)
def submit_prediction(
    constituency_id: int,
    request: Request,
    predicted_winner: str = Form(...),
    predicted_vote_share_raw: str = Form(default="", alias="predicted_vote_share"),
    comment: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_login),
) -> Response:
    """Submit or update a prediction for a constituency."""
    constituency = _get_constituency_or_404(db, constituency_id)

    if not constituency.predictions_open:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Predictions are closed for this seat"
        )

    # Parse optional float from form field (empty string → None)
    try:
        predicted_vote_share: float | None = (
            float(predicted_vote_share_raw) if predicted_vote_share_raw.strip() else None
        )
    except ValueError:
        predicted_vote_share = None

    # Upsert
    prediction = (
        db.query(Prediction)
        .filter_by(user_id=current_user.id, constituency_id=constituency_id)
        .first()
    )
    if prediction is None:
        prediction = Prediction(user_id=current_user.id, constituency_id=constituency_id)
        db.add(prediction)

    prediction.predicted_winner = predicted_winner.strip()
    prediction.predicted_vote_share = predicted_vote_share
    prediction.comment = comment.strip() or None
    db.commit()
    db.refresh(prediction)

    # HTMX request: reload so the result/prediction tables move above the writeup.
    if request.headers.get("HX-Request"):
        return Response(
            status_code=status.HTTP_204_NO_CONTENT,
            headers={"HX-Redirect": f"/seat/{constituency_id}"},
        )

    return RedirectResponse(url=f"/seat/{constituency_id}", status_code=status.HTTP_302_FOUND)
