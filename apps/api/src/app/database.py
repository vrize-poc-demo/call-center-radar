import sqlite3
from pathlib import Path


class Database:
    """Small SQLite connection factory for the local-first POC."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def check_connection(self) -> None:
        with self.connect() as connection:
            connection.execute("SELECT 1").fetchone()
