import json
import sqlite3
import threading
from typing import Any, Dict, List, Optional

from src.config.settings import settings
from src.domain.exceptions import DatabaseError
from src.domain.interfaces import IRepository


class SQLiteRepository(IRepository):
    def __init__(self):
        self.db_name = settings.db.db_name
        self._local = threading.local()
        self._init_db()

    def _get_connection(self):
        """Get a thread-local persistent connection."""
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(self.db_name)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_db(self):
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Enable Write-Ahead Logging for concurrency
            cursor.execute("PRAGMA journal_mode=WAL;")

            cursor.execute("PRAGMA table_info(processed_emails)")
            columns = [col[1] for col in cursor.fetchall()]

            if not columns:
                cursor.execute("""
                    CREATE TABLE processed_emails (
                        email_id TEXT PRIMARY KEY,
                        sender TEXT,
                        subject TEXT,
                        category TEXT,
                        importance_score INTEGER,
                        reasoning TEXT,
                        action_required BOOLEAN,
                        confidence_score REAL,
                        verification_status TEXT,
                        verification_confidence REAL,
                        risk_score INTEGER,
                        risk_level TEXT,
                        verification_reason TEXT,
                        triggered_rules TEXT,
                        notification_status TEXT DEFAULT 'pending',
                        processed_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            else:
                # Migrations — add missing columns if upgrading from older schema
                migrations = {
                    "reasoning": "TEXT",
                    "action_required": "BOOLEAN",
                    "confidence_score": "REAL",
                    "verification_status": "TEXT",
                    "verification_confidence": "REAL",
                    "risk_score": "INTEGER",
                    "risk_level": "TEXT",
                    "verification_reason": "TEXT",
                    "triggered_rules": "TEXT",
                    "notification_status": "TEXT DEFAULT 'pending'",
                    "processed_at": "DATETIME DEFAULT CURRENT_TIMESTAMP",
                }
                for col_name, col_type in migrations.items():
                    if col_name not in columns:
                        cursor.execute(
                            f"ALTER TABLE processed_emails ADD COLUMN {col_name} {col_type}"
                        )

            # Issue #12: Performance indexes
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_email_id ON processed_emails(email_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_processed_at ON processed_emails(processed_at DESC)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_category ON processed_emails(category)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_notification_status ON processed_emails(notification_status)"
            )

            conn.commit()
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to initialize SQLite database at {self.db_name}: {e}")

    def is_email_processed(self, email_id: str) -> bool:
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM processed_emails WHERE email_id = ?", (email_id,))
            result = cursor.fetchone()
            return result is not None
        except sqlite3.Error as e:
            raise DatabaseError(f"Database query failed for email_id {email_id}: {e}")

    def log_email(
        self,
        email_id: str,
        sender: str,
        subject: str,
        category: str,
        score: int,
        reasoning: str,
        action_required: bool,
        confidence_score: float,
        verification_status: Optional[str] = "Legitimate",
        verification_confidence: Optional[float] = 100.0,
        risk_score: Optional[int] = 0,
        risk_level: Optional[str] = "Low",
        verification_reason: Optional[str] = "",
        triggered_rules: Optional[str] = "",
        notification_status: Optional[str] = "pending",
    ) -> None:
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR IGNORE INTO processed_emails (
                    email_id, sender, subject, category, importance_score, reasoning,
                    action_required, confidence_score, verification_status, verification_confidence,
                    risk_score, risk_level, verification_reason, triggered_rules, notification_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    email_id,
                    sender,
                    subject,
                    category,
                    score,
                    reasoning,
                    action_required,
                    confidence_score,
                    verification_status,
                    verification_confidence,
                    risk_score,
                    risk_level,
                    verification_reason,
                    triggered_rules,
                    notification_status,
                ),
            )
            conn.commit()
        except sqlite3.Error as e:
            raise DatabaseError(f"Database insert failed for email_id {email_id}: {e}")

    # ── Issue #10: Duplicate Notification Prevention ───────────────────────────

    def has_notification_been_sent(self, email_id: str) -> bool:
        """Check if a notification has already been successfully sent for this email."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT notification_status FROM processed_emails WHERE email_id = ?",
                (email_id,),
            )
            row = cursor.fetchone()
            return row is not None and row["notification_status"] == "sent"
        except sqlite3.Error as e:
            raise DatabaseError(f"Database query failed for notification check on {email_id}: {e}")

    def update_notification_status(self, email_id: str, status: str) -> None:
        """Update the notification status for an already-logged email."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE processed_emails SET notification_status = ? WHERE email_id = ?",
                (status, email_id),
            )
            conn.commit()
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to update notification status for {email_id}: {e}")

    # ── Issue #12 & #13: Dashboard & Monitoring Queries ───────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """
        Return aggregated statistics for the dashboard /api/stats endpoint.
        Runs a single efficient query with GROUP BY aggregations.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Total counts
            cursor.execute("SELECT COUNT(*) as total FROM processed_emails")
            total = cursor.fetchone()["total"]

            cursor.execute(
                "SELECT COUNT(*) as blocked FROM processed_emails WHERE verification_status = 'Suspicious'"
            )
            blocked = cursor.fetchone()["blocked"]

            cursor.execute(
                "SELECT COUNT(*) as sent FROM processed_emails WHERE notification_status = 'sent'"
            )
            sent = cursor.fetchone()["sent"]

            cursor.execute(
                "SELECT AVG(risk_score) as avg_risk FROM processed_emails WHERE risk_score IS NOT NULL"
            )
            row = cursor.fetchone()
            avg_risk = round(row["avg_risk"] or 0.0, 1)

            # Category distribution
            cursor.execute(
                """
                SELECT category, COUNT(*) as count
                FROM processed_emails
                WHERE category IS NOT NULL
                GROUP BY category
                ORDER BY count DESC
            """
            )
            categories = {row["category"]: row["count"] for row in cursor.fetchall()}

            # Risk level distribution
            cursor.execute(
                """
                SELECT risk_level, COUNT(*) as count
                FROM processed_emails
                WHERE risk_level IS NOT NULL
                GROUP BY risk_level
            """
            )
            risk_levels = {row["risk_level"]: row["count"] for row in cursor.fetchall()}

            # Emails per day (last 7 days)
            cursor.execute(
                """
                SELECT DATE(processed_at) as day, COUNT(*) as count
                FROM processed_emails
                WHERE processed_at >= DATE('now', '-7 days')
                GROUP BY day
                ORDER BY day ASC
            """
            )
            daily = [{"day": row["day"], "count": row["count"]} for row in cursor.fetchall()]

            return {
                "total_emails": total,
                "emails_blocked": blocked,
                "notifications_sent": sent,
                "avg_risk_score": avg_risk,
                "category_distribution": categories,
                "risk_level_distribution": risk_levels,
                "emails_per_day": daily,
            }
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to compute stats: {e}")

    def get_recent_emails(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Return paginated list of recent processed emails for the dashboard table."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    email_id, sender, subject, category, importance_score,
                    verification_status, risk_score, risk_level,
                    notification_status, processed_at, triggered_rules,
                    verification_reason
                FROM processed_emails
                ORDER BY processed_at DESC
                LIMIT ? OFFSET ?
            """,
                (limit, offset),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to fetch recent emails: {e}")

    def get_metrics(self) -> Dict[str, Any]:
        """Return system metrics for the /metrics monitoring endpoint."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) as total FROM processed_emails")
            total = cursor.fetchone()["total"]

            cursor.execute(
                "SELECT COUNT(*) as blocked FROM processed_emails WHERE verification_status = 'Suspicious'"
            )
            blocked = cursor.fetchone()["blocked"]

            cursor.execute(
                "SELECT COUNT(*) as sent FROM processed_emails WHERE notification_status = 'sent'"
            )
            sent = cursor.fetchone()["sent"]

            cursor.execute(
                "SELECT COUNT(*) as failed FROM processed_emails WHERE notification_status = 'failed'"
            )
            failed = cursor.fetchone()["failed"]

            cursor.execute(
                "SELECT AVG(risk_score) as avg_risk FROM processed_emails WHERE risk_score IS NOT NULL"
            )
            avg_risk = round(cursor.fetchone()["avg_risk"] or 0.0, 1)

            return {
                "emails_processed_total": total,
                "emails_blocked": blocked,
                "notifications_sent": sent,
                "notifications_failed": failed,
                "avg_risk_score": avg_risk,
            }
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to fetch metrics: {e}")
