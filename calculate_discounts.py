
import sqlite3
from database.db import DB_PATH


def calculate_discounts(
    items,
    coupon_code=None,
    bank_name=None,
    customer_tier="REGULAR"
):

    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    results = []
    total_discount = 0

    try:
        # STEP 1: Category offer
        for item in items:

            sku = item["sku"]
            category = item["category"]
            price = item["selling_price"]
            quantity = item["quantity"]
            is_sale_item = item.get("is_sale_item", 0)

            original_amount = price * quantity
            category_discount = 0

            if not is_sale_item:
                cursor.execute("""
                    SELECT discount_value, max_discount
                    FROM promotions
                    WHERE promotion_type = 'CATEGORY_PERCENTAGE'
                    AND LOWER(TRIM(category)) = LOWER(TRIM(?))
                    AND is_active = 1
                """, (category,))

                offer = cursor.fetchone()

                if offer:
                    rate, cap = offer
                    category_discount = original_amount * rate / 100

                    if cap is not None:
                        category_discount = min(category_discount, cap)

                    # BR-03: Maximum 70% discount per line
                    category_discount = min(
                        category_discount,
                        original_amount * 0.70
                    )

            after_category = original_amount - category_discount
            total_discount += category_discount

            results.append({
                "sku": sku,
                "original_amount": original_amount,
                "category_discount": category_discount,
                "coupon_discount": 0,
                "bank_discount": 0,
                "prime_discount": 0,
                "final_amount": after_category,
                "category": category,
                "is_sale_item": is_sale_item
            })

        # STEP 2: Coupon
        if coupon_code:

            cursor.execute("""
                SELECT promotion_type, discount_value,
                       min_order_value, max_discount
                FROM promotions
                WHERE coupon_code = ?
                AND is_active = 1
            """, (coupon_code.upper(),))

            coupon = cursor.fetchone()

            if coupon is None:
                return {
                    "success": False,
                    "message": "Invalid coupon code"
                }

            p_type, value, minimum, cap = coupon

            eligible_total = sum(
                row["final_amount"]
                for row in results
                if not row["is_sale_item"]
            )

            if eligible_total < minimum:
                return {
                    "success": False,
                    "message": "Minimum coupon value not reached after category offers"
                }

            if p_type in ("PERCENTAGE", "FLAT"):

                if p_type == "PERCENTAGE":
                    discount = eligible_total * value / 100
                else:
                    discount = value

                if cap is not None:
                    discount = min(discount, cap)

                remaining = discount

                for row in results:

                    if row["is_sale_item"]:
                        continue

                    available = max(
                        0,
                        row["original_amount"] * 0.70
                        - row["category_discount"]
                    )

                    applied = min(
                        remaining,
                        row["final_amount"],
                        available
                    )

                    row["coupon_discount"] += applied
                    row["final_amount"] -= applied
                    remaining -= applied

                    if remaining <= 0:
                        break

                total_discount += discount - remaining

            elif p_type == "FREE_SHIPPING":
                pass

            else:
                return {
                    "success": False,
                    "message": "Unsupported coupon type"
                }

        # STEP 3: Bank offer
        if bank_name:

            cursor.execute("""
                SELECT discount_value, min_order_value, max_discount
                FROM promotions
                WHERE promotion_type = 'BANK_PERCENTAGE'
                AND bank_name = ?
                AND is_active = 1
            """, (bank_name.upper(),))

            bank_offer = cursor.fetchone()

            if bank_offer:
                rate, minimum, cap = bank_offer

                bank_base = sum(
                    row["final_amount"] for row in results
                )

                if bank_base >= minimum:

                    discount = bank_base * rate / 100

                    if cap is not None:
                        discount = min(discount, cap)

                    remaining = discount

                    for row in results:

                        available = max(
                            0,
                            row["original_amount"] * 0.70
                            - row["category_discount"]
                            - row["coupon_discount"]
                        )

                        applied = min(
                            remaining,
                            row["final_amount"],
                            available
                        )

                        row["bank_discount"] += applied
                        row["final_amount"] -= applied
                        remaining -= applied

                        if remaining <= 0:
                            break

                    total_discount += discount - remaining

        # STEP 4: PRIME customer electronics discount
        if customer_tier.upper() == "PRIME":

            electronics_total = sum(
                row["final_amount"]
                for row in results
                if row["category"].strip().lower() == "electronics"
            )

            prime_discount = min(
                electronics_total * 5 / 100,
                1000
            )

            remaining = prime_discount

            for row in results:

                if row["category"].strip().lower() != "electronics":
                    continue

                available = max(
                    0,
                    row["original_amount"] * 0.70
                    - row["category_discount"]
                    - row["coupon_discount"]
                    - row["bank_discount"]
                )

                applied = min(
                    remaining,
                    row["final_amount"],
                    available
                )

                row["prime_discount"] += applied
                row["final_amount"] -= applied
                remaining -= applied

                if remaining <= 0:
                    break

            total_discount += prime_discount - remaining

        return {
            "success": True,
            "items": results,
            "total_discount": round(total_discount, 2),
            "final_amount": round(
                sum(row["final_amount"] for row in results), 2
            )
        }

    finally:
        connection.close()


if __name__ == "__main__":
    print("Discount calculation module ready.")
