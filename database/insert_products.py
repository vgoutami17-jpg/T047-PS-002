
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "ps002.db"

products = [
    ("P001", "Cotton T-Shirt", "Fashion", 799, 599, 50, 250, 0, 5),
    ("P002", "Blue Jeans", "Fashion", 1499, 1199, 30, 600, 0, 5),
    ("P003", "Wireless Mouse", "Electronics", 999, 799, 40, 150, 0, 18),
    ("P004", "Bluetooth Speaker", "Electronics", 2499, 1999, 20, 1200, 0, 18),
    ("P005", "Notebook", "Stationery", 100, 80, 100, 300, 0, 12),
]

connection = sqlite3.connect(DB_PATH)

connection.executemany("""
    INSERT OR IGNORE INTO products
    (sku, name, category, mrp, selling_price, stock,
     weight_grams, is_sale_item, gst_rate)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""", products)

connection.commit()
connection.close()

print("Sample products inserted successfully!")
