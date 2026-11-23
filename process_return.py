
import sqlite3
from datetime import datetime
from database.db import DB_PATH


def process_return(order_id, order_item_id, quantity, reason):

    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        cursor = connection.cursor()
        connection.execute("BEGIN IMMEDIATE")

        # 1. Get order, customer and coupon details
        cursor.execute("""
            SELECT
                o.status,
                o.delivery_date,
                c.tier,
                o.coupon_code,
                o.coupon_min_order_value
            FROM orders o
            JOIN customers c
                ON o.customer_id = c.customer_id
            WHERE o.order_id = ?
        """, (order_id,))

        order = cursor.fetchone()

        if order is None:
            raise ValueError("Order not found!")

        (order_status, delivery_date, customer_tier,
         coupon_code, coupon_min_order_value) = order

        if order_status != "DELIVERED":
            raise ValueError(
                "Return is allowed only for delivered orders!"
            )

        if not delivery_date:
            raise ValueError("Delivery date not available!")

        # 2. Check return window
        delivered = datetime.strptime(
            delivery_date[:19], "%Y-%m-%d %H:%M:%S"
        )

        days_passed = (datetime.now() - delivered).days

        customer_tier = customer_tier.upper().strip()

        if customer_tier == "REGULAR":
            return_days = 10
        elif customer_tier == "PRIME":
            return_days = 30
        else:
            raise ValueError("Invalid customer type!")

        if days_passed < 0 or days_passed > return_days:
            raise ValueError("Return period expired!")

        # 3. Get purchased item details
        cursor.execute("""
            SELECT
                quantity,
                unit_price,
                category_discount,
                coupon_discount,
                bank_discount,
                prime_discount,
                gst_rate,
                is_returnable,
                returned_quantity,
                bogo_discount
            FROM order_items
            WHERE order_item_id = ?
            AND order_id = ?
        """, (order_item_id, order_id))

        item = cursor.fetchone()

        if item is None:
            raise ValueError("Order item not found!")

        (purchased_quantity, unit_price, category_discount,
         coupon_discount, bank_discount, prime_discount,
         gst_rate, is_returnable, returned_quantity,
         bogo_discount) = item

        # 4. Check return eligibility
        if not is_returnable:
            raise ValueError("This product cannot be returned!")

        if quantity <= 0:
            raise ValueError(
                "Return quantity must be greater than zero!"
            )

        available_quantity = purchased_quantity - returned_quantity

        if quantity > available_quantity:
            raise ValueError(
                "Return quantity exceeds available quantity!"
            )

        if purchased_quantity <= 0:
            raise ValueError("Invalid purchased quantity!")

        # 5. Calculate proportional discounts
        # BOGO discount is included here.
        total_discount = (
            (category_discount or 0)
            + (coupon_discount or 0)
            + (bank_discount or 0)
            + (prime_discount or 0)
            + (bogo_discount or 0)
        )

        discount_per_item = (
            total_discount / purchased_quantity
        )

        discounted_price = max(
            0,
            unit_price - discount_per_item
        )

        # 6. Calculate refund including GST
        refund_before_gst = discounted_price * quantity

        gst_amount = round(
            refund_before_gst * gst_rate / 100, 2
        )

        refund_amount = round(
            refund_before_gst + gst_amount, 2
        )

        # 7. Check coupon minimum after proposed return
        coupon_forfeited = False
        coupon_recovery = 0.0
        remaining_order_value = 0.0

        if coupon_code and (coupon_min_order_value or 0) > 0:

            cursor.execute("""
                SELECT
                    order_item_id,
                    quantity,
                    unit_price,
                    category_discount,
                    coupon_discount,
                    gst_rate,
                    returned_quantity
                FROM order_items
                WHERE order_id = ?
            """, (order_id,))

            order_lines = cursor.fetchall()

            for line in order_lines:

                (line_id, line_quantity, line_price,
                 line_category_discount, line_coupon_discount,
                 line_gst_rate, line_returned_quantity) = line

                proposed_return_quantity = (
                    quantity if line_id == order_item_id else 0
                )

                remaining_quantity = (
                    line_quantity
                    - line_returned_quantity
                    - proposed_return_quantity
                )

                if remaining_quantity < 0:
                    raise ValueError(
                        "Return quantity exceeds remaining quantity!"
                    )

                category_discount_per_unit = (
                    (line_category_discount or 0) / line_quantity
                )

                remaining_order_value += (
                    line_price - category_discount_per_unit
                ) * remaining_quantity

            remaining_order_value = round(
                remaining_order_value, 2
            )

            if remaining_order_value < coupon_min_order_value:

                coupon_forfeited = True

                # Recover coupon discount from retained items
                for line in order_lines:

                    (line_id, line_quantity, line_price,
                     line_category_discount, line_coupon_discount,
                     line_gst_rate, line_returned_quantity) = line

                    proposed_return_quantity = (
                        quantity if line_id == order_item_id else 0
                    )

                    remaining_quantity = (
                        line_quantity
                        - line_returned_quantity
                        - proposed_return_quantity
                    )

                    if remaining_quantity <= 0:
                        continue

                    coupon_discount_per_unit = (
                        (line_coupon_discount or 0) / line_quantity
                    )

                    retained_coupon_discount = (
                        coupon_discount_per_unit * remaining_quantity
                    )

                    retained_coupon_gst = round(
                        retained_coupon_discount
                        * line_gst_rate / 100,
                        2
                    )

                    coupon_recovery += (
                        retained_coupon_discount
                        + retained_coupon_gst
                    )

                coupon_recovery = round(coupon_recovery, 2)

                refund_amount = round(
                    max(0, refund_amount - coupon_recovery), 2
                )

        # 8. Create return request
        cursor.execute("""
            INSERT INTO returns (order_id, customer_id, reason)
            SELECT order_id, customer_id, ?
            FROM orders
            WHERE order_id = ?
        """, (reason, order_id))

        return_id = cursor.lastrowid

        # 9. Save returned item
        cursor.execute("""
            INSERT INTO return_items (
                return_id,
                order_item_id,
                quantity,
                refund_amount
            )
            VALUES (?, ?, ?, ?)
        """, (return_id, order_item_id, quantity, refund_amount))

        # 10. Update returned quantity
        cursor.execute("""
            UPDATE order_items
            SET returned_quantity = returned_quantity + ?
            WHERE order_item_id = ?
        """, (quantity, order_item_id))

        connection.commit()

        print("\nRETURN REQUEST SAVED SUCCESSFULLY!")
        print("Return ID:", return_id)
        print("Order ID:", order_id)
        print("Returned quantity:", quantity)
        print("Refund amount: Rs.", refund_amount)
        print("BOGO discount included: Rs.", bogo_discount or 0)
        print("Customer tier:", customer_tier)
        print("Allowed return days:", return_days)

        if coupon_forfeited:
            print("Coupon status: FORFEITED")
            print("Coupon code:", coupon_code)
            print(
                "Remaining order value: Rs.",
                remaining_order_value
            )
            print(
                "Coupon minimum value: Rs.",
                coupon_min_order_value
            )
            print(
                "Coupon recovery including GST: Rs.",
                coupon_recovery
            )

        elif coupon_code:
            print("Coupon status: RETAINED")
            print("Coupon code:", coupon_code)

    except (sqlite3.Error, ValueError, ZeroDivisionError) as error:

        connection.rollback()
        print("\nRETURN FAILED!")
        print("Reason:", error)

    finally:
        connection.close()


if __name__ == "__main__":

    order_id = input("Enter order ID: ").strip()
    order_item_id = int(input("Enter order item ID: "))
    quantity = int(input("Enter return quantity: "))
    reason = input("Enter return reason: ")

    process_return(
        order_id,
        order_item_id,
        quantity,
        reason
    )
