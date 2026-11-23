import sqlite3
from database.db import DB_PATH

connection = sqlite3.connect(DB_PATH)
cursor = connection.cursor()

cursor.execute("SELECT * FROM customers")

print("CUSTOMER DETAILS:")
for customer in cursor.fetchall():
    print(customer)

connection.close()