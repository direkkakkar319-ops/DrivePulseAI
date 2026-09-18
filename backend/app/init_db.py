"""Explicitly create initial auth tables for a new database; not a migration tool."""

from app.database import Base, engine
from app.models.user import AuthSession, User  # noqa: F401

if __name__ == "__main__":
    Base.metadata.create_all(engine)
