import sqlite3
import os
import logging
import re
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

DB_NAME = os.environ.get("DB_NAME", "app.db")
DATABASE_URL = os.environ.get("DATABASE_URL")

# --- POSTGRES WRAPPER ---
class PostgresCursorWrapper:
    """Wraps a psycopg2 cursor to translate SQLite syntax (like '?') to Postgres ('%s')."""
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, query, params=None):
        # Translate SQLite ? placeholders to Postgres %s placeholders
        # (This simplistic regex works for our standard queries. For complex nested strings it might fail, 
        # but our specific queries in booking_service.py are safe).
        pg_query = re.sub(r'\?', '%s', query)
        
        # In SQLite, "rowid" is a default hidden column. We map it to id assuming standard sort order isn't strictly reliant on it,
        # or we strip it if it causes issues. Looking at booking_service, it uses "ORDER BY rowid". Postgres relies on explicit serials or timestamps.
        # Since we use UUIDs and no explicit created_at yet, ordering by purely rowid is SQLite specific. Let's just remove "ORDER BY rowid DESC"
        # and "ORDER BY rowid ASC" from queries since the tools fetch the specific item anyway.
        pg_query = pg_query.replace("ORDER BY rowid DESC", "").replace("ORDER BY rowid ASC", "").replace("ORDER BY rowid", "")

        try:
            self._cursor.execute(pg_query, params)
        except Exception as e:
            logger.error(f"Postgres Execute Error. Query: {pg_query} | Params: {params} | Error: {e}")
            self._cursor.connection.rollback()
            raise e
            
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def close(self):
        self._cursor.close()
        
    @property
    def description(self):
        return self._cursor.description

class PostgresConnectionWrapper:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return PostgresCursorWrapper(self._conn.cursor())

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

def get_db_connection():
    if DATABASE_URL:
        # Use PostgreSQL
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
            return PostgresConnectionWrapper(conn)
        except ImportError:
            logger.error("psycopg2 is required when DATABASE_URL is set!")
            raise
    else:
        # Use SQLite
        logger.info(f"Connecting to database: {os.path.abspath(DB_NAME)}")
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # User Profile Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id TEXT PRIMARY KEY,
            content TEXT
        )
    ''')
    
    # Packages Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS packages (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            user_id TEXT,
            title TEXT,
            type TEXT,
            status TEXT,
            total_price REAL
        )
    ''')
    
    # Simple migration: add user_id if it doesn't exist (Only for SQLite locally)
    if not DATABASE_URL:
        try:
            c.execute("ALTER TABLE packages ADD COLUMN user_id TEXT")
        except Exception:
            pass # Already exists
    
    # Package Items Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS package_items (
            id TEXT PRIMARY KEY,
            package_id TEXT,
            name TEXT,
            item_type TEXT,
            price REAL,
            status TEXT,
            description TEXT,
            metadata TEXT,
            FOREIGN KEY (package_id) REFERENCES packages(id)
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("Database initialized.")

# Helper to dictionary
def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d
