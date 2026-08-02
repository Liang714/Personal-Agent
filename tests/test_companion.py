from agent import config
from agent.capabilities.companion import complete_task, delete_task
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
