
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "ps002.db"

customers = [
    ("C001", "Ananya", "REGULAR", "Karnataka"),
    ("C002", "Rahul", "PRIME", "Karnataka"),
    ("C003", "Priya", "REGULAR", "Telangana"),
    ("C004", "Arjun", "PRIME", "Maharashtra"),
    ("C005", "Sneha", "REGULAR", "Tamil Nadu"),
    ("C006", "Kiran", "PRIME", "Kerala"),
    ("C007", "Divya", "REGULAR", "Andhra Pradesh"),
    ("C008", "Rohit", "PRIME", "Delhi"),
    ("C009", "Meena", "REGULAR", "Assam"),
    ("C010", "Varun", "PRIME", "Karnataka"),
]

connection = sqlite3.connect(DB_PATH)

connection.executemany("""
    INSERT OR IGNORE INTO customers
    (customer_id, name, tier, state)
    VALUES (?, ?, ?, ?)
""", customers)

connection.commit()
connection.close()

print("10 sample customers inserted successfully!")
