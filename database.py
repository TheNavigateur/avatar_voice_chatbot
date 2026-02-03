import sqlite3
import os
import logging
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

DB_NAME = "app.db"

def get_db_connection():
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
            title TEXT,
            type TEXT,
            status TEXT,
            total_price REAL
        )
    ''')
    
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
