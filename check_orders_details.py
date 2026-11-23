import sqlite3
from database.db import DB_PATH

connection = sqlite3.connect(DB_PATH)
cursor = connection.cursor()

cursor.execute("SELECT * FROM orders")

orders = cursor.fetchall()

print("----- ORDER DETAILS -----")

for order in orders:
    print(order)

connection.close()