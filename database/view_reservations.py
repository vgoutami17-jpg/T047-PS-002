
import sqlite3
from db import DB_PATH

connection = sqlite3.connect(DB_PATH)
cursor = connection.cursor()

cursor.execute("""
    SELECT reservation_id, cart_id, sku, quantity,
           reserved_at, expires_at, status
    FROM stock_reservations
""")

records = cursor.fetchall()

print("\nSTOCK RESERVATION RECORDS")
print("-" * 70)

if records:
    for row in records:
        print(row)
else:
    print("No reservation records found!")

connection.close()
