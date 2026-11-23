
import sqlite3
from database.db import DB_PATH


# BOGO OFFER
def apply_bogo(category, items):

    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute("""
        SELECT buy_quantity, get_quantity
        FROM promotions
        WHERE coupon_code = 'BOGO1'
        AND promotion_type = 'BOGO'
        AND LOWER(TRIM(category)) = LOWER(TRIM(?))
        AND is_active = 1
    """, (category,))

    offer = cursor.fetchone()
    connection.close()

    if offer is None:
        return {
            "success": False,
            "message": "BOGO offer not available"
        }

    buy_qty, get_qty = offer

    if buy_qty <= 0 or get_qty <= 0:
        return {
            "success": False,
            "message": "Invalid BOGO promotion"
        }

    total_quantity = sum(item["quantity"] for item in items)

    free_items = (total_quantity // (buy_qty + get_qty)) * get_qty

    if free_items == 0:
        return {
            "success": True,
            "free_items": 0,
            "discount": 0,
            "total_items_received": total_quantity
        }

    # Get the individual prices of all eligible items
    prices = []

    for item in items:

        if item["quantity"] < 0 or item["unit_price"] < 0:
            return {
                "success": False,
                "message": "Invalid item quantity or price"
            }

        for _ in range(item["quantity"]):
            prices.append(item["unit_price"])

    if free_items > len(prices):
        return {
            "success": False,
            "message": "Not enough eligible items"
        }

    # Cheapest items are free
    prices.sort()

    discount = sum(prices[:free_items])

    return {
        "success": True,
        "free_items": free_items,
        "discount": round(discount, 2),
        "total_items_received": total_quantity
    }


# BANK OFFER
def apply_bank_offer(bank_name, order_total):

    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute("""
        SELECT discount_value, min_order_value, max_discount
        FROM promotions
        WHERE coupon_code = 'HDFC10'
        AND promotion_type = 'BANK_PERCENTAGE'
        AND bank_name = ?
        AND is_active = 1
    """, (bank_name.upper(),))

    offer = cursor.fetchone()
    connection.close()

    if offer is None:
        return {
            "success": False,
            "message": "Bank offer not available"
        }

    discount_rate, min_order, max_discount = offer

    if order_total < min_order:
        return {
            "success": False,
            "message": f"Minimum order amount is Rs. {min_order}"
        }

    discount = order_total * discount_rate / 100
    discount = min(discount, max_discount)

    final_amount = order_total - discount

    return {
        "success": True,
        "discount": round(discount, 2),
        "final_amount": round(final_amount, 2)
    }


# MAIN PROGRAM
if __name__ == "__main__":

    print("1. BOGO Offer")
    print("2. Bank Offer")

    choice = input("Choose offer: ")

    if choice == "1":

        category = input("Enter category: ")

        items = [
            {
                "unit_price": float(input("Enter first item price: ")),
                "quantity": int(input("Enter first item quantity: "))
            },
            {
                "unit_price": float(input("Enter second item price: ")),
                "quantity": int(input("Enter second item quantity: "))
            }
        ]

        result = apply_bogo(category, items)

    elif choice == "2":

        bank = input("Enter bank name: ")
        amount = float(input("Enter order amount: "))

        result = apply_bank_offer(bank, amount)

    else:

        result = {
            "success": False,
            "message": "Invalid choice"
        }

    print("\n----- OFFER RESULT -----")

    for key, value in result.items():
        print(f"{key}: {value}")
