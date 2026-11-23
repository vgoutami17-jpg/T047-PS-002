
import sqlite3
from database.db import DB_PATH


def update_status(order_id, new_status):

    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    try:
        connection.execute("BEGIN IMMEDIATE")

        # Add cancellation_fee column if it does not exist
        columns = [
            row[1] for row in cursor.execute(
                "PRAGMA table_info(orders)"
            ).fetchall()
        ]

        if "cancellation_fee" not in columns:
            cursor.execute("""
                ALTER TABLE orders
                ADD COLUMN cancellation_fee REAL DEFAULT 0
            """)

        # Find order
        cursor.execute("""
            SELECT status, total_amount
            FROM orders
            WHERE order_id = ?
        """, (order_id,))

        order = cursor.fetchone()

        if order is None:
            print("Order not found!")
            connection.rollback()
            return

        current_status, total_amount = order
        cancellation_fee = 0

        # Allowed order transitions
        allowed_transitions = {
            "CREATED": "CONFIRMED",
            "CONFIRMED": "PACKED",
            "PACKED": "SHIPPED",
            "SHIPPED": "DELIVERED"
        }

        # Cancellation rules
        if new_status == "CANCELLED":

            if current_status in ["CREATED", "CONFIRMED"]:
                cancellation_fee = 0

            elif current_status == "PACKED":
                cancellation_fee = round(
                    total_amount * 0.02, 2
                )

            else:
                print("Order cannot be cancelled!")
                connection.rollback()
                return

            cursor.execute("""
                UPDATE orders
                SET status = ?,
                    cancellation_fee = ?
                WHERE order_id = ?
            """, (
                "CANCELLED",
                cancellation_fee,
                order_id
            ))

        # Normal order status changes
        elif allowed_transitions.get(current_status) == new_status:

            if new_status == "DELIVERED":
                cursor.execute("""
                    UPDATE orders
                    SET status = ?,
                        delivery_date = CURRENT_TIMESTAMP
                    WHERE order_id = ?
                """, (new_status, order_id))

            else:
                cursor.execute("""
                    UPDATE orders
                    SET status = ?
                    WHERE order_id = ?
                """, (new_status, order_id))

        else:
            print("Invalid order status change!")
            connection.rollback()
            return

        connection.commit()

        print("Order status updated successfully!")
        print("Order ID:", order_id)
        print("New Status:", new_status)

        if new_status == "CANCELLED":
            print("Original Order Amount: ₹", total_amount)
            print("Cancellation Fee: ₹", cancellation_fee)

    except sqlite3.Error as error:
        connection.rollback()
        print("Database Error:", error)

    finally:
        connection.close()


if __name__ == "__main__":

    order_id = input("Enter order ID: ")
    new_status = input("Enter new status: ").upper()

    update_status(order_id, new_status)
