
import sqlite3
from pathlib import Path

# Create the database file inside the database folder
DB_PATH = Path(__file__).resolve().parent / "ps002.db"


def create_database():
    connection = sqlite3.connect(DB_PATH)

    connection.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            sku TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            mrp REAL NOT NULL,
            selling_price REAL NOT NULL,
            stock INTEGER NOT NULL,
            weight_grams INTEGER NOT NULL,
            is_sale_item INTEGER DEFAULT 0,
            gst_rate REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS customers (
            customer_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            tier TEXT NOT NULL CHECK(tier IN ('REGULAR', 'PRIME')),
            state TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS promotions (
            promotion_id INTEGER PRIMARY KEY AUTOINCREMENT,
            promotion_name TEXT NOT NULL,
            promotion_type TEXT NOT NULL,
            category TEXT,
            coupon_code TEXT,
            discount_value REAL DEFAULT 0,
            min_order_value REAL DEFAULT 0,
            max_discount REAL,
            bank_name TEXT,
            buy_quantity INTEGER,
            get_quantity INTEGER,
            is_active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            order_date TEXT DEFAULT CURRENT_TIMESTAMP,
            total_amount REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'CREATED',
            delivery_date TEXT,
            FOREIGN KEY (customer_id)
                REFERENCES customers(customer_id)
        );
                CREATE TABLE IF NOT EXISTS returns (
            return_id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT NOT NULL,
            customer_id TEXT NOT NULL,
            reason TEXT,
            return_date TEXT DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'REQUESTED',
            FOREIGN KEY (order_id) REFERENCES orders(order_id),
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        );
  """)

    connection.commit()
    connection.close()

    print("Database created successfully!")
    print("Products table created!")
    print("Customers table created!")
    print("Promotions table created!")


if __name__ == "__main__":
    create_database()
