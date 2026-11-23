
import sqlite3
from database.db import DB_PATH


def apply_coupon(coupon_code, order_total):

    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    # Find the coupon
    cursor.execute("""
        SELECT promotion_type, discount_value,
               min_order_value, max_discount
        FROM promotions
        WHERE coupon_code = ? AND is_active = 1
    """, (coupon_code,))

    promotion = cursor.fetchone()

    connection.close()

    # Check whether coupon exists
    if promotion is None:
        return {
            "success": False,
            "message": "Invalid coupon code"
        }

    promotion_type, discount_value, min_order, max_discount = promotion

    # Check minimum order value
    if order_total < min_order:
        return {
            "success": False,
            "message": f"Minimum order value is Rs. {min_order}"
        }

    # Calculate discount
    if promotion_type == "PERCENTAGE":
        discount = order_total * discount_value / 100

    elif promotion_type == "FLAT":
        discount = discount_value

    elif promotion_type == "FREE_SHIPPING":
        discount = 0

    else:
        return {
            "success": False,
            "message": "Unsupported promotion type"
        }

    # Apply maximum discount limit
    if max_discount is not None:
        discount = min(discount, max_discount)

    # Discount cannot exceed order amount
    discount = min(discount, order_total)

    final_amount = order_total - discount

    return {
        "success": True,
        "message": "Coupon applied successfully",
        "discount": round(discount, 2),
        "final_amount": round(final_amount, 2),
        "free_shipping": promotion_type == "FREE_SHIPPING"
    }


# Test the coupon
if __name__ == "__main__":

    coupon = input("Enter coupon code: ").strip().upper()
    amount = float(input("Enter order amount: "))

    result = apply_coupon(coupon, amount)

    print("\n----- COUPON RESULT -----")

    for key, value in result.items():
        print(f"{key}: {value}")
