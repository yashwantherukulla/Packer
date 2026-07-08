from alembic.command import upgrade
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_baseline_migration_builds_all_tables(tmp_path):
    db = tmp_path / "m.sqlite"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db}")
    upgrade(cfg, "head")
    tables = set(inspect(create_engine(f"sqlite:///{db}")).get_table_names())
    assert {"jobs", "models", "artifacts", "reports"} <= tables
