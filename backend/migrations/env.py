"""Run Alembic migrations against the configured PostgreSQL database."""

from alembic import context

from app.config import get_settings
from app.database import Base, build_engine
from app.models.user import UserProfile  # noqa: F401

if context.is_offline_mode():
    context.configure(
        url=get_settings().database_url.get_secret_value(),
        target_metadata=Base.metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = build_engine(get_settings())
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
