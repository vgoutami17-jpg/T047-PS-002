
import sqlite3
from pathlib import Path

# Connect to database
db_path = Path(__file__).resolve().parent / "ps002.db"
connection = sqlite3.connect(db_path)

# Enable foreign keys
connection.execute("PRAGMA foreign_keys = ON")

# Create carts table
connection.execute("""
CREATE TABLE IF NOT EXISTS carts (
    cart_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL,
    status TEXT DEFAULT 'ACTIVE',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    FOREIGN KEY (customer_id)
    REFERENCES customers(customer_id)
)
""")

# Create cart items table
connection.execute("""
CREATE TABLE IF NOT EXISTS cart_items (
    cart_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    cart_id INTEGER NOT NULL,
    sku TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    FOREIGN KEY (cart_id) REFERENCES carts(cart_id),
    FOREIGN KEY (sku) REFERENCES products(sku),
    UNIQUE(cart_id, sku)
)
""")

# Create stock reservations table
connection.execute("""
CREATE TABLE IF NOT EXISTS stock_reservations (
    reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    cart_id INTEGER NOT NULL,
    sku TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    reserved_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    status TEXT DEFAULT 'RESERVED',
    FOREIGN KEY (cart_id) REFERENCES carts(cart_id),
    FOREIGN KEY (sku) REFERENCES products(sku)
)
""")

connection.commit()
connection.close()

print("Cart and inventory tables created successfully!")
