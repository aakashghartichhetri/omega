"""The v1 migration must preserve rows written by the original MVP."""
import json

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text


def test_upgrade_preserves_legacy_runs(tmp_path, monkeypatch):
    url = f"sqlite+pysqlite:///{tmp_path / 'legacy.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config("alembic.ini")
    command.upgrade(config, "0001")

    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text('''
            INSERT INTO runs (
                id, created_at, seed, machines, job_count, case_count,
                candidate_limit, workload_digest, workloads, winner_ordinal,
                winner_ratio, valid_count, invalid_count
            ) VALUES (
                'legacy', '2026-01-01 00:00:00', 42, 4, 4, 2,
                2, 'old-digest', :workloads, 0, 1.0, 1, 1
            )
        '''), {"workloads": json.dumps([[9, 8, 7, 6], [5, 4, 3, 2]])})
    command.upgrade(config, "head")
    with engine.connect() as connection:
        row = connection.execute(text(
            "SELECT id, holdout_count, holdout_digest, winner_ratio FROM runs WHERE id='legacy'"
        )).one()
        table = connection.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='search_jobs'")).scalar()
    assert row == ("legacy", 0, None, 1.0)
    assert table == "search_jobs"
    engine.dispose()
