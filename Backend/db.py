import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("inverter.db")
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect():
    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = connect()
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    finally:
        conn.close()