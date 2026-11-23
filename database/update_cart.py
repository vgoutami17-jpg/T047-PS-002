
import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).resolve().parent / "ps002.db"

connection = sqlite3.connect(DB_PATH)
connection.execute("PRAGMA foreign_keys = ON")

try:
    customer_id = input("Enter Customer ID: ").strip()

    # Find active cart
    cart = connection.execute("""
        SELECT cart_id FROM carts
        WHERE customer_id = ?
        AND status = 'ACTIVE'
        AND expires_at > ?
    """, (
        customer_id,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )).fetchone()

    if not cart:
        raise ValueError("No active cart found!")

    cart_id = cart[0]

    # Display cart
    items = connection.execute("""
        SELECT ci.sku, p.name, ci.quantity
        FROM cart_items ci
        JOIN products p ON ci.sku = p.sku
        WHERE ci.cart_id = ?
    """, (cart_id,)).fetchall()

    if not items:
        raise ValueError("Your cart is empty!")

    print("\nYOUR CART")
    print("-" * 40)

    for item in items:
        print(item)

    print("\n1. Update product quantity")
    print("2. Remove product")

    choice = input("Enter your choice: ").strip()
    sku = input("Enter Product SKU: ").strip()

    # Check whether product exists in cart
    item = connection.execute("""
        SELECT quantity FROM cart_items
        WHERE cart_id = ? AND sku = ?
    """, (cart_id, sku)).fetchone()

    if not item:
        raise ValueError("Product not found in cart!")

    if choice == "1":

        new_quantity = int(input("Enter new quantity: "))

        if new_quantity <= 0:
            raise ValueError("Quantity must be greater than zero!")

        # Check available stock
        stock = connection.execute("""
            SELECT stock FROM products WHERE sku = ?
        """, (sku,)).fetchone()

        if not stock or new_quantity > stock[0]:
            raise ValueError("Insufficient stock!")

        connection.execute("""
            UPDATE cart_items
            SET quantity = ?
            WHERE cart_id = ? AND sku = ?
        """, (new_quantity, cart_id, sku))

        print("Product quantity updated successfully!")

    elif choice == "2":

        connection.execute("""
            DELETE FROM cart_items
            WHERE cart_id = ? AND sku = ?
        """, (cart_id, sku))

        print("Product removed from cart successfully!")

    else:
        raise ValueError("Invalid choice!")

    connection.execute("""
        UPDATE carts
        SET updated_at = ?
        WHERE cart_id = ?
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        cart_id
    ))

    connection.commit()

except ValueError as error:
    connection.rollback()
    print("Error:", error)

except sqlite3.Error as error:
    connection.rollback()
    print("Database Error:", error)

finally:
    connection.close()
