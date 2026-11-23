
import sqlite3
from db import DB_PATH

connection = sqlite3.connect(DB_PATH)
cursor = connection.cursor()

promotions = [
    (
        "10 Percent Discount",
        "PERCENTAGE",
        None,
        "SAVE10",
        10,
        500,
        200,
        None,
        None,
        None
    ),
    (
        "Flat 100 Discount",
        "FLAT",
        None,
        "FLAT100",
        100,
        1000,
        100,
        None,
        None,
        None
    ),
    (
        "Free Shipping Offer",
        "FREE_SHIPPING",
        None,
        "FREESHIP",
        0,
        300,
        None,
        None,
        None,
        None
    )
]

for promotion in promotions:
    cursor.execute("""
        INSERT INTO promotions (
            promotion_name,
            promotion_type,
            category,
            coupon_code,
            discount_value,
            min_order_value,
            max_discount,
            bank_name,
            buy_quantity,
            get_quantity
        )
        SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        WHERE NOT EXISTS (
            SELECT 1 FROM promotions WHERE coupon_code = ?
        )
    """, promotion + (promotion[3],))

# BOGO offer
cursor.execute("""
    INSERT INTO promotions (
        promotion_name,
        promotion_type,
        category,
        coupon_code,
        discount_value,
        min_order_value,
        buy_quantity,
        get_quantity
    )
    SELECT ?, ?, ?, ?, ?, ?, ?, ?
    WHERE NOT EXISTS (
        SELECT 1 FROM promotions WHERE coupon_code = ?
    )
""", (
    "Buy 1 Get 1 Free",
    "BOGO",
    "Chocolates",
    "BOGO1",
    0,
    0,
    1,
    1,
    "BOGO1"
))

# Bank offer
cursor.execute("""
    INSERT INTO promotions (
        promotion_name,
        promotion_type,
        coupon_code,
        discount_value,
        min_order_value,
        max_discount,
        bank_name
    )
    SELECT ?, ?, ?, ?, ?, ?, ?
    WHERE NOT EXISTS (
        SELECT 1 FROM promotions WHERE coupon_code = ?
    )
""", (
    "HDFC Bank Offer",
    "BANK_PERCENTAGE",
    "HDFC10",
    10,
    2000,
    500,
    "HDFC",
    "HDFC10"
))

# Category offer
cursor.execute("""
    INSERT INTO promotions (
        promotion_name,
        promotion_type,
        category,
        discount_value,
        min_order_value,
        max_discount
    )
    SELECT ?, ?, ?, ?, ?, ?
    WHERE NOT EXISTS (
        SELECT 1 FROM promotions
        WHERE promotion_type = 'CATEGORY_PERCENTAGE'
        AND category = 'Fashion'
        AND is_active = 1
    )
""", (
    "Fashion Category Offer",
    "CATEGORY_PERCENTAGE",
    "Fashion",
    10,
    0,
    300
))



connection.commit()
connection.close()

print("Sample promotions inserted successfully!")
