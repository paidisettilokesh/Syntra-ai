import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from src.domain.exceptions import DatabaseError
from src.infrastructure.database.sqlite_repo import SQLiteRepository


@pytest.fixture
def temp_repo(tmp_path):
    db_file = tmp_path / "test_agent_logs.db"
    with patch("src.infrastructure.database.sqlite_repo.settings.db.db_name", str(db_file)):
        repo = SQLiteRepository()
        yield repo


def test_db_initialization(temp_repo):
    assert temp_repo.db_name is not None
    conn = sqlite3.connect(temp_repo.db_name)
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode")
    mode = cursor.fetchone()[0]
    assert mode in ["wal", "memory", "delete"]

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='processed_emails';")
    assert cursor.fetchone() is not None
    conn.close()


def test_log_and_check_processed(temp_repo):
    email_id = "msg-12345"
    assert not temp_repo.is_email_processed(email_id)

    temp_repo.log_email(
        email_id=email_id,
        sender="test@example.com",
        subject="Hello Test",
        category="Job Offer",
        score=8,
        reasoning="Important interview invitation.",
        action_required=True,
        confidence_score=0.98,
    )

    assert temp_repo.is_email_processed(email_id)


def test_database_exceptions():
    with patch("sqlite3.connect") as mock_connect:
        mock_connect.side_effect = sqlite3.Error("Mocked Connection Error")
        with pytest.raises(DatabaseError):
            SQLiteRepository()


def test_database_migrations(tmp_path):
    db_file = tmp_path / "migration_test.db"

    # 1. Create table with ONLY email_id, sender, subject, category, importance_score
    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE processed_emails (
            email_id TEXT PRIMARY KEY,
            sender TEXT,
            subject TEXT,
            category TEXT,
            importance_score INTEGER
        )
    """)
    conn.commit()
    conn.close()

    # 2. Run repository init to trigger migrations
    with patch("src.infrastructure.database.sqlite_repo.settings.db.db_name", str(db_file)):
        SQLiteRepository()

    # 3. Verify columns were added
    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(processed_emails)")
    columns = [col[1] for col in cursor.fetchall()]
    conn.close()

    assert "reasoning" in columns
    assert "action_required" in columns
    assert "confidence_score" in columns


def test_is_email_processed_exception(temp_repo):
    with patch.object(temp_repo, "_get_connection") as mock_get_conn:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = sqlite3.Error("Mocked query failure")
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        with pytest.raises(DatabaseError) as exc_info:
            temp_repo.is_email_processed("123")
        assert "Database query failed" in str(exc_info.value)


def test_log_email_exception(temp_repo):
    with patch.object(temp_repo, "_get_connection") as mock_get_conn:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = sqlite3.Error("Mocked insert failure")
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        with pytest.raises(DatabaseError) as exc_info:
            temp_repo.log_email("123", "s", "sub", "cat", 5, "reason", False, 0.9)
        assert "Database insert failed" in str(exc_info.value)
