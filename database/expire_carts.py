
import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).resolve().parent / "ps002.db"

connection = sqlite3.connect(DB_PATH)
connection.execute("PRAGMA foreign_keys = ON")

try:
    connection.execute("BEGIN IMMEDIATE")

    current_time = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    # Find expired carts
    expired_carts = connection.execute("""
        SELECT cart_id
        FROM carts
        WHERE status = 'ACTIVE'
        AND expires_at <= ?
    """, (current_time,)).fetchall()

    if not expired_carts:
        print("No expired carts found!")

    for cart in expired_carts:

        cart_id = cart[0]

        # Find reserved stock
        reservations = connection.execute("""
            SELECT reservation_id, sku, quantity
            FROM stock_reservations
            WHERE cart_id = ?
            AND status = 'RESERVED'
        """, (cart_id,)).fetchall()

        # Release reserved stock safely
        for reservation_id, sku, quantity in reservations:

            result = connection.execute("""
                UPDATE stock_reservations
                SET status = 'EXPIRED'
                WHERE reservation_id = ?
                AND status = 'RESERVED'
            """, (reservation_id,))

            # Return stock only if reservation was updated
            if result.rowcount == 1:

                connection.execute("""
                    UPDATE products
                    SET stock = stock + ?
                    WHERE sku = ?
                """, (quantity, sku))

                print(
                    "Released:", sku,
                    "Quantity:", quantity
                )

        # Mark cart as expired
        connection.execute("""
            UPDATE carts
            SET status = 'EXPIRED',
                updated_at = ?
            WHERE cart_id = ?
            AND status = 'ACTIVE'
        """, (current_time, cart_id))

        print("Cart", cart_id, "expired successfully!")

    connection.commit()

    print("\nCART EXPIRY PROCESS COMPLETED!")

except sqlite3.Error as error:
    connection.rollback()
    print("Database Error:", error)

finally:
    connection.close()
