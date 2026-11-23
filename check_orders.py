import sqlite3
from database.db import DB_PATH

connection = sqlite3.connect(DB_PATH)
cursor = connection.cursor()

cursor.execute("""
    SELECT name
    FROM sqlite_master
    WHERE type = 'table'
""")

print("DATABASE TABLES:")
print(cursor.fetchall())

connection.close()