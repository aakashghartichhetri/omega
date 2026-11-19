import os

# The application engine is created on import; use SQLite for isolated API tests.
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite://")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.main import app
from app import search


@pytest.fixture
def client(tmp_path, monkeypatch):
    database = create_engine(f"sqlite+pysqlite:///{tmp_path / 'tests.db'}",
                             connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=database)
    factory = sessionmaker(bind=database, expire_on_commit=False)

    def override_db():
        with factory() as db:
            yield db

    def mock_rust(machines, workloads, recipes):
        """API tests validate web/database behavior without needing the Rust compiler."""
        result = {}
        for ordinal, recipe in enumerate(recipes):
            for case_index, jobs in enumerate(workloads):
                loads = [0] * machines
                assignments = []
                for duration in jobs:
                    machine = min(range(machines), key=lambda value: (loads[value], value))
                    assignments.append(machine)
                    loads[machine] += duration
                if recipe.canary:
                    assignments.append(0)
                result[(ordinal, case_index)] = assignments
        return result

    monkeypatch.setattr(search, "run_rust_engine", mock_rust)
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        database.dispose()
