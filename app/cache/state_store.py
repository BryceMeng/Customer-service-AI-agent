"""Small SQLite state store for case outputs."""

import json
import sqlite3
from pathlib import Path

from app.schemas.case import AgentRunOutput


class StateStore:
    """Persist completed case outputs in SQLite."""

    def __init__(self, db_path: str) -> None:
        self._db_path = Path(db_path)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS case_runs (
                    case_id TEXT PRIMARY KEY,
                    current_state TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )

    def save_completed_run(self, output: AgentRunOutput) -> None:
        """Save a completed case run."""

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO case_runs(case_id, current_state, payload_json)
                VALUES (?, ?, ?)
                ON CONFLICT(case_id) DO UPDATE SET
                    current_state = excluded.current_state,
                    payload_json = excluded.payload_json
                """,
                (
                    output.case_id,
                    "report",
                    output.model_dump_json(),
                ),
            )

    def load_run(self, case_id: str) -> dict | None:
        """Load a completed run payload by case id."""

        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM case_runs WHERE case_id = ?",
                (case_id,),
            ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def query_similar_by_intent(self, intent: str, limit: int = 2) -> list[dict]:
        """Return the most recent completed cases matching the given intent."""

        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM case_runs "
                "WHERE json_extract(payload_json, '$.intent') = ? "
                "ORDER BY rowid DESC LIMIT ?",
                (intent, limit),
            ).fetchall()
        results = []
        for (payload_json,) in rows:
            data = json.loads(payload_json)
            results.append({
                "summary": data.get("audit_note", ""),
                "tool_sequence": data.get("tool_calls", []),
                "final_action": data.get("final_action", ""),
                "response": data.get("user_response", ""),
            })
        return results

