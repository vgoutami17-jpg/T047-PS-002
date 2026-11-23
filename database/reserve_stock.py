
import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).resolve().parent / "ps002.db"

connection = sqlite3.connect(DB_PATH)
connection.execute("PRAGMA foreign_keys = ON")

try:
    # Start transaction
    connection.execute("BEGIN IMMEDIATE")

    customer_id = input("Enter Customer ID: ").strip()

    now = datetime.now()
    current_time = now.strftime("%Y-%m-%d %H:%M:%S")

    # Find active cart
    cart = connection.execute("""
        SELECT cart_id, expires_at
        FROM carts
        WHERE customer_id = ?
        AND status = 'ACTIVE'
        AND expires_at > ?
    """, (customer_id, current_time)).fetchone()

    if not cart:
        raise ValueError("No active cart found!")

    cart_id, expiry_time = cart

    # Check existing reservations
    existing = connection.execute("""
        SELECT reservation_id
        FROM stock_reservations
        WHERE cart_id = ? AND status = 'RESERVED'
    """, (cart_id,)).fetchone()

    if existing:
        raise ValueError("Stock is already reserved for this cart!")

    # Get cart products
    items = connection.execute("""
        SELECT sku, quantity
        FROM cart_items
        WHERE cart_id = ?
    """, (cart_id,)).fetchall()

    if not items:
        raise ValueError("Cart is empty!")

    # Check stock availability for all products
    for sku, quantity in items:

        product = connection.execute("""
            SELECT stock FROM products
            WHERE sku = ?
        """, (sku,)).fetchone()

        if not product:
            raise ValueError("Product not found: " + sku)

        if product[0] < quantity:
            raise ValueError("Insufficient stock for: " + sku)

    # Reserve stock
    for sku, quantity in items:

        connection.execute("""
            UPDATE products
            SET stock = stock - ?
            WHERE sku = ?
        """, (quantity, sku))

        connection.execute("""
            INSERT INTO stock_reservations
            (cart_id, sku, quantity, reserved_at,
             expires_at, status)
            VALUES (?, ?, ?, ?, ?, 'RESERVED')
        """, (
            cart_id,
            sku,
            quantity,
            current_time,
            expiry_time
        ))

    connection.commit()

    print("\nSTOCK RESERVED SUCCESSFULLY!")
    print("Customer ID:", customer_id)
    print("Cart ID:", cart_id)

    for sku, quantity in items:
        print("Product:", sku, "| Reserved:", quantity)

except (ValueError, sqlite3.Error) as error:
    connection.rollback()
    print("Error:", error)

finally:
    connection.close()
