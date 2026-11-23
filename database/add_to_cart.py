
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

DB_PATH = Path(__file__).resolve().parent / "ps002.db"

connection = sqlite3.connect(DB_PATH)
connection.execute("PRAGMA foreign_keys = ON")

try:
    connection.execute("BEGIN IMMEDIATE")

    customer_id = input("Enter Customer ID: ").strip()
    sku = input("Enter Product SKU: ").strip()
    quantity = int(input("Enter Quantity: "))

    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero.")

    # Check customer
    customer = connection.execute(
        "SELECT customer_id FROM customers WHERE customer_id = ?",
        (customer_id,)
    ).fetchone()

    if not customer:
        raise ValueError("Customer not found!")

    # Check product
    product = connection.execute(
        "SELECT name, stock FROM products WHERE sku = ?",
        (sku,)
    ).fetchone()

    if not product:
        raise ValueError("Product not found!")

    if quantity > product[1]:
        raise ValueError("Insufficient stock!")

    now = datetime.now()
    current_time = now.strftime("%Y-%m-%d %H:%M:%S")
    expiry_time = (now + timedelta(minutes=30)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    # Find active cart
    cart = connection.execute("""
        SELECT cart_id FROM carts
        WHERE customer_id = ?
        AND status = 'ACTIVE'
        AND expires_at > ?
        ORDER BY cart_id DESC
        LIMIT 1
    """, (customer_id, current_time)).fetchone()

    # Create cart if needed
    if cart:
        cart_id = cart[0]
    else:
        cursor = connection.execute("""
            INSERT INTO carts
            (customer_id, status, created_at, updated_at, expires_at)
            VALUES (?, 'ACTIVE', ?, ?, ?)
        """, (customer_id, current_time, current_time, expiry_time))

        cart_id = cursor.lastrowid

    # Add product to cart
    connection.execute("""
        INSERT INTO cart_items (cart_id, sku, quantity)
        VALUES (?, ?, ?)
        ON CONFLICT(cart_id, sku)
        DO UPDATE SET quantity = quantity + excluded.quantity
    """, (cart_id, sku, quantity))

    # Check existing stock reservation
    reservation = connection.execute("""
        SELECT reservation_id, quantity
        FROM stock_reservations
        WHERE cart_id = ?
        AND sku = ?
        AND status = 'RESERVED'
    """, (cart_id, sku)).fetchone()

    if reservation:
        # Update existing reservation
        new_quantity = reservation[1] + quantity

        connection.execute("""
            UPDATE stock_reservations
            SET quantity = ?,
                expires_at = ?
            WHERE reservation_id = ?
        """, (new_quantity, expiry_time, reservation[0]))

    else:
        # Create new stock reservation
        connection.execute("""
    INSERT INTO stock_reservations
    (cart_id, sku, quantity, reserved_at, expires_at, status)
    VALUES (?, ?, ?, ?, ?, 'RESERVED')
""", (cart_id, sku, quantity, current_time, expiry_time))

    # Update cart time
    connection.execute("""
        UPDATE carts
        SET updated_at = ?,
            expires_at = ?
        WHERE cart_id = ?
    """, (current_time, expiry_time, cart_id))

    connection.commit()

    print("\nPRODUCT ADDED TO CART SUCCESSFULLY!")
    print("Customer ID:", customer_id)
    print("Product:", product[0])
    print("Quantity:", quantity)
    print("Cart ID:", cart_id)
    print("Stock reserved successfully!")

except (ValueError, sqlite3.Error) as error:
    connection.rollback()
    print("\nERROR:", error)

finally:
    connection.close()
