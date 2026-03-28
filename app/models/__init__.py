"""ORM models — import all here so Alembic can discover them."""

from app.models.candidate import Candidate
from app.models.constituency import Constituency, Party
from app.models.election import Election
from app.models.prediction import Prediction
from app.models.result import Result
from app.models.user import User

__all__ = ["Candidate", "Constituency", "Election", "Party", "Prediction", "Result", "User"]
