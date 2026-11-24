
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "evaluation.db"


def create_evaluation_database():
    connection = sqlite3.connect(DB_PATH)

    connection.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            sku_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            mrp REAL NOT NULL,
            selling_price REAL NOT NULL,
            stock INTEGER NOT NULL,
            weight_g INTEGER NOT NULL,
            on_sale INTEGER NOT NULL,
            gst_slab REAL NOT NULL,
            returnable INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS customers (
            customer_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            tier TEXT NOT NULL,
            state TEXT NOT NULL,
            city TEXT NOT NULL,
            mobile TEXT NOT NULL,
            wallet_balance REAL NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS promotions (
            promo_id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            code TEXT,
            category TEXT,
            bank TEXT,
            discount_pct REAL DEFAULT 0,
            discount_flat REAL DEFAULT 0,
            cap_amount REAL DEFAULT 0,
            min_cart_value REAL DEFAULT 0,
            buy_qty INTEGER,
            get_qty INTEGER,
            valid_from TEXT NOT NULL,
            valid_to TEXT NOT NULL,
            tier TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS carts (
            cart_id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_activity TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'ACTIVE',
            coupon_code TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        );

        CREATE TABLE IF NOT EXISTS cart_items (
            cart_id TEXT NOT NULL,
            sku_id TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            PRIMARY KEY (cart_id, sku_id),
            FOREIGN KEY (cart_id) REFERENCES carts(cart_id),
            FOREIGN KEY (sku_id) REFERENCES products(sku_id)
        );

        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            cart_id TEXT NOT NULL,
            customer_id TEXT NOT NULL,
            checkout_ts TEXT NOT NULL,
            payment_mode TEXT NOT NULL,
            bank TEXT,
            status TEXT NOT NULL,
            gross_selling_value REAL DEFAULT 0,
            invoice_total REAL DEFAULT 0,
            cancellation_fee REAL DEFAULT 0,
            FOREIGN KEY (cart_id) REFERENCES carts(cart_id),
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        );

        CREATE TABLE IF NOT EXISTS order_items (
            order_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT NOT NULL,
            sku_id TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_selling_price REAL NOT NULL,
            line_discount REAL DEFAULT 0,
            line_taxable REAL DEFAULT 0,
            gst_slab REAL NOT NULL,
            line_gst REAL DEFAULT 0,
            line_total REAL DEFAULT 0,
            returned_quantity INTEGER DEFAULT 0,
            shipped_quantity INTEGER DEFAULT 0,
            FOREIGN KEY (order_id) REFERENCES orders(order_id)
        );

        CREATE TABLE IF NOT EXISTS stock_reservations (
            cart_id TEXT NOT NULL,
            sku_id TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            status TEXT NOT NULL,
            reserved_at TEXT NOT NULL,
            PRIMARY KEY (cart_id, sku_id)
        );

        CREATE TABLE IF NOT EXISTS returns (
            return_id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT NOT NULL,
            sku_id TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            refund_mode TEXT NOT NULL,
            refund_amount REAL DEFAULT 0,
            status TEXT NOT NULL,
            requested_at TEXT NOT NULL,
            received_at TEXT
        );
    """)

    connection.commit()
    connection.close()

    print("Evaluation database created successfully!")
    print("Database:", DB_PATH)


if __name__ == "__main__":
    create_evaluation_database()
