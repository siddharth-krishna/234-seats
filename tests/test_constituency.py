"""Tests for constituency page and prediction submission."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.constituency import Constituency
from app.models.election import Election
from app.models.prediction import Prediction
from app.models.result import (
    ProvisionalResultCandidate,
    ProvisionalResultSeat,
    ProvisionalResultSet,
    Result,
)
from app.models.user import User
from app.services.auth import create_session_token, hash_password

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def election(db: Session) -> Election:
    e = Election(name="TN 2026", year=2026, active=True)
    db.add(e)
    db.flush()
    return e


@pytest.fixture()
def open_seat(db: Session, election: Election) -> Constituency:
    c = Constituency(
        election_id=election.id, number=1, name="Seat A", district="D", predictions_open=True
    )
    db.add(c)
    db.flush()
    return c


@pytest.fixture()
def closed_seat(db: Session, election: Election) -> Constituency:
    c = Constituency(
        election_id=election.id, number=2, name="Seat B", district="D", predictions_open=False
    )
    db.add(c)
    db.flush()
    return c


@pytest.fixture()
def user(db: Session) -> User:
    u = User(username="alice", hashed_password=hash_password("pass"))
    db.add(u)
    db.flush()
    return u


@pytest.fixture()
def other_user(db: Session) -> User:
    u = User(username="bob", hashed_password=hash_password("pass"))
    db.add(u)
    db.flush()
    return u


def logged_in_client(client: TestClient, user: User) -> TestClient:
    """Set a valid session cookie on the client for the given user."""
    client.cookies.set("session", create_session_token(user.id))
    return client


# ── Page rendering ────────────────────────────────────────────────────────────


def test_constituency_page_404(client: TestClient, user: User) -> None:
    logged_in_client(client, user)
    assert client.get("/seat/9999").status_code == 404


def test_constituency_page_shows_form_when_open(
    client: TestClient, user: User, open_seat: Constituency, db: Session
) -> None:
    """An open seat with no prediction shows the submission form."""
    db.commit()
    logged_in_client(client, user)
    r = client.get(f"/seat/{open_seat.id}")
    assert r.status_code == 200
    assert "Submit your prediction" in r.text
    assert "predicted_winner" in r.text


def test_constituency_page_renders_writeup_markdown(
    client: TestClient, user: User, open_seat: Constituency, db: Session
) -> None:
    """Markdown writeups render as HTML on the seat page."""
    open_seat.writeup = "## Key fight\n\n**DMK** vs *AIADMK*"
    db.commit()
    logged_in_client(client, user)
    r = client.get(f"/seat/{open_seat.id}")
    assert "<h2>Key fight</h2>" in r.text
    assert "<strong>DMK</strong>" in r.text
    assert "<em>AIADMK</em>" in r.text


def test_constituency_page_shows_remote_image(
    client: TestClient, user: User, open_seat: Constituency, db: Session
) -> None:
    """Seat page shows a configured remote image URL."""
    open_seat.image_url = "https://example.com/seat.jpg"
    db.commit()
    logged_in_client(client, user)
    r = client.get(f"/seat/{open_seat.id}")
    assert 'src="https://example.com/seat.jpg"' in r.text


def test_prediction_form_stays_below_writeup_before_submission(
    client: TestClient, user: User, open_seat: Constituency, db: Session
) -> None:
    """Open seats show the submission form below writeup content."""
    open_seat.writeup = "Seat context"
    db.commit()
    logged_in_client(client, user)

    r = client.get(f"/seat/{open_seat.id}")

    assert r.text.index("Seat context") < r.text.index("Submit your prediction")


def test_results_and_predictions_move_above_writeup_after_submission(
    client: TestClient, user: User, open_seat: Constituency, db: Session
) -> None:
    """After predicting, provisional results and predictions appear above writeup."""
    open_seat.writeup = "Seat context"
    db.add(Prediction(user_id=user.id, constituency_id=open_seat.id, predicted_winner="Alice"))
    result_set = ProvisionalResultSet(
        election_id=open_seat.election_id, counted_at=datetime(2026, 5, 4, 13, 0)
    )
    db.add(result_set)
    db.flush()
    result_set.seat_results.append(
        ProvisionalResultSeat(
            constituency_id=open_seat.id,
            candidate_results=[ProvisionalResultCandidate(candidate_name="Alice", vote_share=48.0)],
        )
    )
    db.commit()
    logged_in_client(client, user)

    r = client.get(f"/seat/{open_seat.id}")

    assert r.text.index("Provisional result") < r.text.index("All predictions")
    assert r.text.index("All predictions") < r.text.index("Seat context")


def test_constituency_page_hides_others_before_submission(
    client: TestClient, user: User, other_user: User, open_seat: Constituency, db: Session
) -> None:
    """Other users' predictions are hidden until the current user submits."""
    db.add(
        Prediction(
            user_id=other_user.id,
            constituency_id=open_seat.id,
            predicted_winner="Bob secret pick",
        )
    )
    db.commit()
    logged_in_client(client, user)
    r = client.get(f"/seat/{open_seat.id}")
    assert "Bob secret pick" not in r.text
    assert "Submit your prediction" in r.text


def test_constituency_page_shows_table_after_submission(
    client: TestClient, user: User, other_user: User, open_seat: Constituency, db: Session
) -> None:
    """After submitting, the user can see all predictions including others'."""
    db.add_all(
        [
            Prediction(
                user_id=user.id, constituency_id=open_seat.id, predicted_winner="Alice pick"
            ),
            Prediction(
                user_id=other_user.id, constituency_id=open_seat.id, predicted_winner="Bob pick"
            ),
        ]
    )
    db.commit()
    logged_in_client(client, user)
    r = client.get(f"/seat/{open_seat.id}")
    assert "Alice pick" in r.text
    assert "Bob pick" in r.text
    assert 'class="bg-red-800 text-white"' in r.text


def test_constituency_page_shows_all_when_closed(
    client: TestClient, user: User, other_user: User, closed_seat: Constituency, db: Session
) -> None:
    """Closed seats show all predictions without requiring a submission."""
    db.add(
        Prediction(
            user_id=other_user.id,
            constituency_id=closed_seat.id,
            predicted_winner="Bob pick",
        )
    )
    db.commit()
    logged_in_client(client, user)
    r = client.get(f"/seat/{closed_seat.id}")
    assert "Bob pick" in r.text


# ── Prediction submission ─────────────────────────────────────────────────────


def test_submit_prediction_redirects(
    client: TestClient, user: User, open_seat: Constituency, db: Session
) -> None:
    """Submitting a prediction redirects back to the seat page."""
    db.commit()
    logged_in_client(client, user)
    r = client.post(
        f"/seat/{open_seat.id}/predict",
        data={"predicted_winner": "Alice", "predicted_vote_share": "45.0", "comment": ""},
    )
    assert r.status_code == 302
    assert f"/seat/{open_seat.id}" in r.headers["location"]


def test_submit_prediction_persisted(
    client: TestClient, user: User, open_seat: Constituency, db: Session
) -> None:
    """Submitted prediction is saved to the database."""
    db.commit()
    logged_in_client(client, user)
    client.post(
        f"/seat/{open_seat.id}/predict",
        data={"predicted_winner": "Candidate X", "predicted_vote_share": "38.5", "comment": ""},
    )
    pred = db.query(Prediction).filter_by(user_id=user.id, constituency_id=open_seat.id).first()
    assert pred is not None
    assert pred.predicted_winner == "Candidate X"
    assert pred.predicted_vote_share == pytest.approx(38.5)


def test_submit_prediction_updates_existing(
    client: TestClient, user: User, open_seat: Constituency, db: Session
) -> None:
    """Submitting again updates the existing prediction (upsert)."""
    db.add(Prediction(user_id=user.id, constituency_id=open_seat.id, predicted_winner="Old pick"))
    db.commit()
    logged_in_client(client, user)
    client.post(
        f"/seat/{open_seat.id}/predict",
        data={"predicted_winner": "New pick", "predicted_vote_share": "", "comment": ""},
    )
    preds = db.query(Prediction).filter_by(user_id=user.id, constituency_id=open_seat.id).all()
    assert len(preds) == 1
    assert preds[0].predicted_winner == "New pick"


def test_submit_prediction_closed_seat_returns_403(
    client: TestClient, user: User, closed_seat: Constituency, db: Session
) -> None:
    """Submitting to a closed seat returns 403."""
    db.commit()
    logged_in_client(client, user)
    r = client.post(
        f"/seat/{closed_seat.id}/predict",
        data={"predicted_winner": "X", "predicted_vote_share": "", "comment": ""},
    )
    assert r.status_code == 403


def test_submit_empty_vote_share_stored_as_none(
    client: TestClient, user: User, open_seat: Constituency, db: Session
) -> None:
    """An empty vote share field is stored as None."""
    db.commit()
    logged_in_client(client, user)
    client.post(
        f"/seat/{open_seat.id}/predict",
        data={"predicted_winner": "X", "predicted_vote_share": "", "comment": ""},
    )
    pred = db.query(Prediction).filter_by(user_id=user.id).first()
    assert pred is not None
    assert pred.predicted_vote_share is None


def test_result_shown_on_constituency_page(
    client: TestClient, user: User, closed_seat: Constituency, db: Session
) -> None:
    """Declared result is shown on the constituency page."""
    db.add(
        Result(
            constituency_id=closed_seat.id,
            winner_name="The Winner",
            winner_party="DMK",
            winner_vote_share=51.2,
        )
    )
    db.commit()
    logged_in_client(client, user)
    r = client.get(f"/seat/{closed_seat.id}")
    assert "The Winner" in r.text
    assert "Official result" in r.text
