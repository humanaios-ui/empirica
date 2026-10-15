"""Tests for `empirica session-close` (closed-unassessed session ending)."""

import json
from types import SimpleNamespace

import pytest


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "session_close.db")


@pytest.fixture
def seeded(db_path, monkeypatch):
    """Two open sessions and one already ended. Handler opens a fresh DB each call."""
    from empirica.data.session_database import SessionDatabase

    db = SessionDatabase(db_path=db_path)
    open_a = db.create_session(ai_id="test-ai")
    open_b = db.create_session(ai_id="test-ai")
    ended = db.create_session(ai_id="test-ai")
    db.end_session(ended)
    db.close()

    monkeypatch.setattr(
        "empirica.data.session_database.SessionDatabase",
        lambda *a, **k: SessionDatabase(db_path=db_path),
    )
    return SimpleNamespace(open_a=open_a, open_b=open_b, ended=ended)


def _read(db_path, sid):
    from empirica.data.session_database import SessionDatabase

    db = SessionDatabase(db_path=db_path)
    try:
        return db.sessions.get_session(sid)
    finally:
        db.close()


def test_status_column_exists_on_fresh_db(db_path):
    from empirica.data.session_database import SessionDatabase

    db = SessionDatabase(db_path=db_path)
    cols = [r[1] for r in db.conn.execute("PRAGMA table_info(sessions)").fetchall()]
    db.close()
    assert "status" in cols


def test_repo_close_sets_status_and_writes_no_vectors(db_path):
    from empirica.data.session_database import SessionDatabase

    db = SessionDatabase(db_path=db_path)
    sid = db.create_session(ai_id="test-ai")
    assert db.sessions.close_session_unassessed(sid, "no grounded state") is True
    row = db.sessions.get_session(sid)
    db.close()
    assert row["end_time"] is not None
    assert row["status"] == "closed-unassessed"
    assert row["session_notes"] == "closed-unassessed: no grounded state"
    assert row["avg_confidence"] is None  # no assessment written


def test_repo_close_refuses_ended_and_missing(db_path):
    from empirica.data.session_database import SessionDatabase

    db = SessionDatabase(db_path=db_path)
    sid = db.create_session(ai_id="test-ai")
    db.end_session(sid)
    assert db.sessions.close_session_unassessed(sid, "late") is False
    assert db.sessions.close_session_unassessed("does-not-exist", "x") is False
    db.close()


def test_handler_preview_writes_nothing(seeded, db_path, capsys):
    from empirica.cli.command_handlers.session_close import handle_session_close_command

    args = SimpleNamespace(session_ids=[seeded.open_a], reason="r", apply=False, output="json")
    handle_session_close_command(args)
    payload = json.loads(capsys.readouterr().out)
    assert payload["applied"] is False
    assert payload["results"][0]["action"] == "would_close"
    assert _read(db_path, seeded.open_a)["end_time"] is None


def test_handler_apply_closes_open_and_reports_ended(seeded, db_path, capsys):
    from empirica.cli.command_handlers.session_close import handle_session_close_command

    args = SimpleNamespace(
        session_ids=[seeded.open_a, seeded.open_b, seeded.ended, "missing-id", seeded.open_a],
        reason="batch cleanup",
        apply=True,
        output="json",
    )
    handle_session_close_command(args)
    payload = json.loads(capsys.readouterr().out)
    actions = {r["session_id"]: r["action"] for r in payload["results"]}
    assert actions[seeded.open_a] == "closed-unassessed"  # duplicate id collapsed to one result
    assert actions[seeded.open_b] == "closed-unassessed"
    assert actions[seeded.ended] == "already_ended"
    assert actions["missing-id"] == "not_found"
    assert len(payload["results"]) == 4
    assert payload["closed"] == 2
    assert _read(db_path, seeded.open_a)["status"] == "closed-unassessed"
    assert _read(db_path, seeded.ended)["status"] is None  # normal end untouched


def test_parser_accepts_multiple_ids_and_flags():
    import argparse

    from empirica.cli.parsers.session_parsers import add_session_parsers

    root = argparse.ArgumentParser()
    add_session_parsers(root.add_subparsers(dest="cmd"))
    ns = root.parse_args(["session-close", "a1", "b2", "--reason", "why", "--apply"])
    assert ns.session_ids == ["a1", "b2"]
    assert ns.reason == "why"
    assert ns.apply is True
