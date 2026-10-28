import pytest

from agent import config
from agent.storage import db


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point every test at a fresh database, never the real data/agent.db."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "agent.db")
    db.init_db()
