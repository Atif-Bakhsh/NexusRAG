from alembic import context
from sqlalchemy import create_engine

from nexusrag.config import Settings
from nexusrag.db import Base

engine = create_engine(Settings().database_url.get_secret_value())
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
