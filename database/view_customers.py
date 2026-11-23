
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "ps002.db"

connection = sqlite3.connect(DB_PATH)

customers = connection.execute(
    "SELECT * FROM customers"
).fetchall()

print("\nCUSTOMER LIST")
print("-" * 50)

for customer in customers:
    print(customer)

connection.close()
