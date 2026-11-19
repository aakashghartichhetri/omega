from types import SimpleNamespace

import pytest

from app import engine
from app.search import Recipe


def test_batch_protocol_round_trip(monkeypatch):
    def fake_run(argv, **kwargs):
        assert kwargs["timeout"] == 120
        assert "OMEGA1|2\nW|9,8,7,6\n" in kwargs["input"]
        assert "C|0|longest|0|least_loaded|0|0|0" in kwargs["input"]
        return SimpleNamespace(returncode=0, stderr="", stdout="S|0|0|0,1,1,0\n")

    monkeypatch.setattr(engine.subprocess, "run", fake_run)
    assignments = engine.run_rust_engine(2, [[9, 8, 7, 6]], [Recipe("longest", 0, "least_loaded", 0, 0)])
    assert assignments == {(0, 0): [0, 1, 1, 0]}


def test_engine_reports_protocol_errors(monkeypatch):
    monkeypatch.setattr(engine.subprocess, "run", lambda *a, **k:
                        SimpleNamespace(returncode=0, stderr="", stdout="S|999|0|0,1\n"))
    with pytest.raises(engine.EngineError):
        engine.run_rust_engine(2, [[3, 4, 5, 6]], [Recipe("longest", 0, "least_loaded", 0, 0)])
