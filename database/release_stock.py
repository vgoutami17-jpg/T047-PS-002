
import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).resolve().parent / "ps002.db"

connection = sqlite3.connect(DB_PATH)
connection.execute("PRAGMA foreign_keys = ON")

try:
    connection.execute("BEGIN IMMEDIATE")

    customer_id = input("Enter Customer ID: ").strip()

    # Find active cart
    cart = connection.execute("""
        SELECT cart_id FROM carts
        WHERE customer_id = ?
        AND status = 'ACTIVE'
    """, (customer_id,)).fetchone()

    if not cart:
        raise ValueError("Cart not found!")

    cart_id = cart[0]

    # Find reserved products
    reservations = connection.execute("""
        SELECT reservation_id, sku, quantity
        FROM stock_reservations
        WHERE cart_id = ?
        AND status = 'RESERVED'
    """, (cart_id,)).fetchall()

    if not reservations:
        raise ValueError("No reserved stock found!")

    # Release stock
    for reservation_id, sku, quantity in reservations:

        connection.execute("""
            UPDATE products
            SET stock = stock + ?
            WHERE sku = ?
        """, (quantity, sku))

        connection.execute("""
            UPDATE stock_reservations
            SET status = 'RELEASED'
            WHERE reservation_id = ?
        """, (reservation_id,))

        print("Released:", sku, "| Quantity:", quantity)

    # Close cart
    connection.execute("""
        UPDATE carts
        SET status = 'CANCELLED',
            updated_at = ?
        WHERE cart_id = ?
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        cart_id
    ))

    connection.commit()

    print("\nSTOCK RELEASED SUCCESSFULLY!")

except (ValueError, sqlite3.Error) as error:
    connection.rollback()
    print("Error:", error)

finally:
    connection.close()
