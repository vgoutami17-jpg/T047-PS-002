
import sqlite3
import csv
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "evaluation.db"

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "sample_data" / "T047-PS-002-sample-data"


def read_csv(filename):
    file_path = DATA_DIR / filename

    with open(file_path, "r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def to_bool(value):
    return 1 if value.strip().lower() == "true" else 0


def load_data():
    connection = sqlite3.connect(DB_PATH)

    try:
        products = read_csv("catalogue.csv")
        customers = read_csv("customers.csv")
        promotions = read_csv("promotions.csv")

        cursor = connection.cursor()

        # Clear only the evaluation database tables.
        cursor.execute("DELETE FROM stock_reservations")
        cursor.execute("DELETE FROM cart_items")
        cursor.execute("DELETE FROM carts")
        cursor.execute("DELETE FROM order_items")
        cursor.execute("DELETE FROM returns")
        cursor.execute("DELETE FROM orders")
        cursor.execute("DELETE FROM promotions")
        cursor.execute("DELETE FROM customers")
        cursor.execute("DELETE FROM products")

        # Load official products.
        for p in products:
            cursor.execute("""
                INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                p["sku_id"],
                p["name"],
                p["category"],
                float(p["mrp"]),
                float(p["selling_price"]),
                int(p["stock"]),
                int(p["weight_g"]),
                to_bool(p["on_sale"]),
                float(p["gst_slab"]),
                to_bool(p["returnable"])
            ))

        # Load official customers.
        for c in customers:
            cursor.execute("""
                INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                c["customer_id"],
                c["name"],
                c["tier"],
                c["state"],
                c["city"],
                c["mobile"],
                float(c["wallet_balance"])
            ))

        # Load official promotions.
        for p in promotions:
            cursor.execute("""
                INSERT INTO promotions VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """, (
                p["promo_id"],
                p["type"],
                p["code"] or None,
                p["category"] or None,
                p["bank"] or None,
                float(p["discount_pct"] or 0),
                float(p["discount_flat"] or 0),
                float(p["cap_amount"] or 0),
                float(p["min_cart_value"] or 0),
                int(p["buy_qty"]) if p["buy_qty"] else None,
                int(p["get_qty"]) if p["get_qty"] else None,
                p["valid_from"],
                p["valid_to"],
                p["tier"]
            ))

        connection.commit()

        print("OFFICIAL DATA LOADED SUCCESSFULLY!")
        print("Products:", len(products))
        print("Customers:", len(customers))
        print("Promotions:", len(promotions))

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    load_data()
