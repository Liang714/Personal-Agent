import json
from unittest.mock import MagicMock, patch

import pytest

from agent import config
from agent.capabilities.companion import complete_task, complete_tasks, delete_task, delete_tasks
from agent.errors import MatchExtractionError
from agent.storage import db


def test_complete_task_removes_from_open_list(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    db.init_db()

    task_id = db.add_task("water the plants", source="test")
    assert any(r["id"] == task_id for r in db.list_open_tasks())

    result = complete_task(task_id)

    assert str(task_id) in result
    assert not any(r["id"] == task_id for r in db.list_open_tasks())


def test_delete_task_removes_from_open_list(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    db.init_db()

    task_id = db.add_task("call the bank", source="test")
    assert any(r["id"] == task_id for r in db.list_open_tasks())

    result = delete_task(task_id)

    assert str(task_id) in result
    assert not any(r["id"] == task_id for r in db.list_open_tasks())


def _mock_chat_response(mock_client, payload: dict):
    mock_response = MagicMock()
    mock_response.message.content = json.dumps(payload)
    mock_client.chat.return_value = mock_response


def test_complete_tasks_no_open_tasks(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    db.init_db()

    with patch("agent.capabilities.companion.client") as mock_client:
        result = complete_tasks("the plants task")
        mock_client.chat.assert_not_called()

    assert result == "No open tasks."


def test_complete_tasks_single_match(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    plants_id = db.add_task("water the plants", source="test")
    bank_id = db.add_task("call the bank", source="test")

    with patch("agent.capabilities.companion.client") as mock_client:
        _mock_chat_response(mock_client, {"task_ids": [plants_id], "explanation": "matches plants"})
        result = complete_tasks("the plants task")

    open_ids = {r["id"] for r in db.list_open_tasks()}
    assert plants_id not in open_ids
    assert bank_id in open_ids
    assert "water the plants" in result


def test_delete_tasks_multiple_match(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    plants_id = db.add_task("water the plants", source="test")
    bank_id = db.add_task("call the bank", source="test")

    with patch("agent.capabilities.companion.client") as mock_client:
        _mock_chat_response(mock_client, {"task_ids": [plants_id, bank_id], "explanation": "both"})
        result = delete_tasks("both tasks")

    assert db.list_open_tasks() == []
    assert "water the plants" in result
    assert "call the bank" in result


def test_delete_tasks_no_confident_match(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    task_id = db.add_task("water the plants", source="test")

    with patch("agent.capabilities.companion.client") as mock_client:
        _mock_chat_response(mock_client, {"task_ids": [], "explanation": "nothing matches"})
        result = delete_tasks("the haircut task")

    open_ids = {r["id"] for r in db.list_open_tasks()}
    assert task_id in open_ids  # untouched
    assert "haircut task" in result
    assert "water the plants" in result  # real open tasks listed back


def test_complete_tasks_rejects_hallucinated_id(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    plants_id = db.add_task("water the plants", source="test")

    with patch("agent.capabilities.companion.client") as mock_client:
        _mock_chat_response(mock_client, {"task_ids": [plants_id, 9999], "explanation": "one real, one not"})
        result = complete_tasks("the plants task")

    open_ids = {r["id"] for r in db.list_open_tasks()}
    assert plants_id not in open_ids
    assert "water the plants" in result


def test_delete_tasks_raises_on_invalid_json(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    db.add_task("water the plants", source="test")

    with patch("agent.capabilities.companion.client") as mock_client:
        mock_response = MagicMock()
        mock_response.message.content = "not json"
        mock_client.chat.return_value = mock_response

        with pytest.raises(MatchExtractionError):
            delete_tasks("the plants task")
