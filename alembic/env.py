from __future__ import annotations

from alembic import context
from sqlalchemy import engine_from_config, pool

from packer.api.db import models  # noqa: F401  (import registers tables on Base.metadata)
from packer.api.db.base import Base
from packer.engine.common.config_schema import compose_config

config = context.config
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", compose_config().db.dsn)

target_metadata = Base.metadata


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
