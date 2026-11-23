
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "ps002.db"

connection = sqlite3.connect(DB_PATH)

tables = connection.execute("""
SELECT name
FROM sqlite_master
WHERE type = 'table'
""").fetchall()

print("\nDATABASE TABLES")
print("-" * 40)

for table in tables:
    print("\nTable:", table[0])

    columns = connection.execute(
        f"PRAGMA table_info({table[0]})"
    ).fetchall()

    for column in columns:
        print(column[1], "-", column[2])

connection.close()

