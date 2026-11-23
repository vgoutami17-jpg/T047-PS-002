
import sqlite3
from datetime import datetime, timedelta
from database.db import DB_PATH


def update_return_status(return_id, new_status, refund_method=None):

    connection = sqlite3.connect(DB_PATH)

    try:
        cursor = connection.cursor()
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN IMMEDIATE")

        # Add refund columns if they do not exist
        cursor.execute("PRAGMA table_info(returns)")
        columns = [column[1] for column in cursor.fetchall()]

        if "refund_method" not in columns:
            cursor.execute("""
                ALTER TABLE returns
                ADD COLUMN refund_method TEXT
            """)

        if "refund_amount" not in columns:
            cursor.execute("""
                ALTER TABLE returns
                ADD COLUMN refund_amount REAL DEFAULT 0
            """)

        if "refund_date" not in columns:
            cursor.execute("""
                ALTER TABLE returns
                ADD COLUMN refund_date TEXT
            """)

        # Get return request details
        cursor.execute("""
            SELECT status, return_date
            FROM returns
            WHERE return_id = ?
        """, (return_id,))

        result = cursor.fetchone()

        if result is None:
            print("Return request not found!")
            return

        current_status, return_date = result

        # APPROVE OR REJECT RETURN
        if new_status in ["APPROVED", "REJECTED"]:

            if current_status != "REQUESTED":
                print("Return status cannot be changed!")
                return

            # If rejected, restore the returned quantity
            if new_status == "REJECTED":

                cursor.execute("""
                    SELECT order_item_id, quantity
                    FROM return_items
                    WHERE return_id = ?
                """, (return_id,))

                returned_items = cursor.fetchall()

                for order_item_id, quantity in returned_items:

                    cursor.execute("""
                        UPDATE order_items
                        SET returned_quantity =
                            returned_quantity - ?
                        WHERE order_item_id = ?
                    """, (quantity, order_item_id))

                print("Returned quantity restored successfully!")

            # Update return status
            cursor.execute("""
                UPDATE returns
                SET status = ?
                WHERE return_id = ?
            """, (new_status, return_id))

            connection.commit()

            print("Return status updated successfully!")
            print("Return ID:", return_id)
            print("New Status:", new_status)

            return

        # PROCESS REFUND
        if new_status == "REFUNDED":

            if current_status != "APPROVED":
                print("Only approved returns can be refunded!")
                return

            if refund_method not in ["ORIGINAL", "WALLET"]:
                print("Invalid refund method!")
                return

            # Calculate total refund amount
            cursor.execute("""
                SELECT COALESCE(SUM(refund_amount), 0)
                FROM return_items
                WHERE return_id = ?
            """, (return_id,))

            base_refund = cursor.fetchone()[0]

            if base_refund <= 0:
                print("No valid refund amount found!")
                return

            # ORIGINAL PAYMENT REFUND
            if refund_method == "ORIGINAL":

                request_date = datetime.strptime(
                    return_date[:19],
                    "%Y-%m-%d %H:%M:%S"
                )

                if datetime.now() - request_date > timedelta(days=5):
                    print("Original payment refund period expired!")
                    return

                final_refund = round(base_refund, 2)

            # WALLET REFUND WITH 2% BONUS
            else:

                bonus = round(base_refund * 0.02, 2)

                final_refund = round(
                    base_refund + bonus, 2
                )

            refund_date = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            # Save refund details
            cursor.execute("""
                UPDATE returns
                SET status = 'REFUNDED',
                    refund_method = ?,
                    refund_amount = ?,
                    refund_date = ?
                WHERE return_id = ?
            """, (
                refund_method,
                final_refund,
                refund_date,
                return_id
            ))

            connection.commit()

            print("\nREFUND PROCESSED SUCCESSFULLY!")
            print("Return ID:", return_id)
            print("Refund Method:", refund_method)
            print("Original Refund: Rs.", round(base_refund, 2))

            if refund_method == "WALLET":
                print("Wallet Bonus (2%): Rs.", bonus)

            print("Final Refund: Rs.", final_refund)
            print("Status: REFUNDED")

            return

        print("Invalid return status!")

    except (sqlite3.Error, ValueError) as error:

        connection.rollback()
        print("Error:", error)

    finally:
        connection.close()


if __name__ == "__main__":

    return_id = int(input("Enter return ID: "))

    new_status = input(
        "Enter status (APPROVED/REJECTED/REFUNDED): "
    ).upper().strip()

    if new_status == "REFUNDED":

        refund_method = input(
            "Enter refund method (ORIGINAL/WALLET): "
        ).upper().strip()

        update_return_status(
            return_id,
            new_status,
            refund_method
        )

    else:

        update_return_status(
            return_id,
            new_status
        )
