
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "ps002.db"

connection = sqlite3.connect(DB_PATH)

products = connection.execute(
    "SELECT sku, name, category, selling_price, stock FROM products"
).fetchall()

print("\nPRODUCT CATALOGUE")
print("-" * 65)

for product in products:
    print(product)

connection.close()
