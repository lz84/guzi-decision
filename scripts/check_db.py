#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check database structure"""

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(r"D:\work\research\guzi-decision")
db_path = PROJECT_ROOT / "trading.db"

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print(f"Tables: {[t[0] for t in tables]}")

for table in tables:
    cursor.execute(f"PRAGMA table_info({table[0]})")
    cols = cursor.fetchall()
    print(f"\n{table[0]} columns:")
    for col in cols:
        print(f"  {col[1]} ({col[2]})")

conn.close()