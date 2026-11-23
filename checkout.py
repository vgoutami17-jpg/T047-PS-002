
import sqlite3
from pathlib import Path
from datetime import datetime
import math

from database.db import DB_PATH
from calculate_discounts import calculate_discounts


# -----------------------------
# GST CALCULATION
# -----------------------------
def calculate_gst(amount, gst_rate):
    return round(amount * gst_rate / 100, 2)


# -----------------------------
# SHIPPING CALCULATION
# -----------------------------
def calculate_shipping(
    order_amount,
    weight_grams,
    customer_tier,
    state,
    free_shipping=False
):
    if customer_tier.upper().strip() == "PRIME":
        return 0

    if order_amount >= 499 or free_shipping:
        return 0

    shipping = 49

    if weight_grams > 2000:
        extra_weight = weight_grams - 2000
        extra_blocks = math.ceil(extra_weight / 500)
        shipping += extra_blocks * 30

    north_east_states = [
        "ASSAM", "ARUNACHAL PRADESH", "MANIPUR",
        "MEGHALAYA", "MIZORAM", "NAGALAND",
        "SIKKIM", "TRIPURA"
    ]

    if state.upper().strip() in north_east_states:
        shipping += 100

    return shipping


# -----------------------------
# BOGO DISCOUNT CALCULATION
# -----------------------------
def calculate_bogo_discounts(connection, cart_items, discounted_items):

    cursor = connection.cursor()

    cursor.execute("""
        SELECT category, buy_quantity, get_quantity
        FROM promotions
        WHERE promotion_type = 'BOGO'
        AND is_active = 1
    """)

    offers = cursor.fetchall()

    bogo_discounts = {}
    total_bogo_discount = 0
    total_free_items = 0

    discounted_by_sku = {
        item["sku"]: item
        for item in discounted_items
    }

    for category, buy_qty, get_qty in offers:

        if buy_qty <= 0 or get_qty <= 0:
            continue

        eligible_products = []

        for original in cart_items:

            sku = original[0]
            quantity = original[1]
            product_category = original[3]
            unit_price = original[4]

            if product_category.strip().lower() != category.strip().lower():
                continue

            discounted = discounted_by_sku.get(sku)

            if not discounted:
                continue

            eligible_products.append({
                "sku": sku,
                "quantity": quantity,
                "unit_price": unit_price,
                "final_amount": discounted["final_amount"]
            })

        total_quantity = sum(
            product["quantity"]
            for product in eligible_products
        )

        free_count = (
            total_quantity // (buy_qty + get_qty)
        ) * get_qty

        if free_count == 0:
            continue

        units = []

        for product in eligible_products:

            for _ in range(product["quantity"]):

                units.append({
                    "sku": product["sku"],
                    "unit_price": product["unit_price"],
                    "discounted_unit_price": (
                        product["final_amount"]
                        / product["quantity"]
                    )
                })

        units.sort(
            key=lambda item: (
                item["unit_price"],
                item["sku"]
            )
        )

        free_units = units[:free_count]

        for unit in free_units:

            sku = unit["sku"]

            discount = round(
                unit["discounted_unit_price"], 2
            )

            bogo_discounts[sku] = round(
                bogo_discounts.get(sku, 0) + discount, 2
            )

            total_bogo_discount += discount
            total_free_items += 1

    for item in discounted_items:

        sku = item["sku"]

        bogo_discount = bogo_discounts.get(sku, 0)

        item["bogo_discount"] = round(
            bogo_discount, 2
        )

        item["final_amount"] = round(
            max(0, item["final_amount"] - bogo_discount),
            2
        )

    return {
        "discounts": bogo_discounts,
        "total_discount": round(total_bogo_discount, 2),
        "free_items": total_free_items
    }


# -----------------------------
# ENSURE GST DATABASE COLUMNS
# -----------------------------
def ensure_gst_columns(connection):

    cursor = connection.cursor()

    cursor.execute("PRAGMA table_info(order_items)")
    existing_columns = [
        column[1] for column in cursor.fetchall()
    ]

    required_columns = {
        "cgst_amount": "REAL DEFAULT 0",
        "sgst_amount": "REAL DEFAULT 0",
        "igst_amount": "REAL DEFAULT 0"
    }

    for column_name, column_type in required_columns.items():

        if column_name not in existing_columns:

            cursor.execute(
                f"""
                ALTER TABLE order_items
                ADD COLUMN {column_name} {column_type}
                """
            )


# -----------------------------
# CHECKOUT FUNCTION
# -----------------------------
def checkout():

    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON")

    try:

        connection.execute("BEGIN IMMEDIATE")

        # STEP 1: Get customer details

        customer_id = input("Enter Customer ID: ").strip()
        order_id = input("Enter new Order ID: ").strip()

        entered_code = input(
            "Enter coupon code (press Enter to skip): "
        ).strip().upper() or None

        bank_name = input(
            "Enter bank name (press Enter to skip): "
        ).strip().upper() or None

        # BOGO1 is a BOGO trigger, not a normal coupon
        coupon_code = (
            None if entered_code == "BOGO1"
            else entered_code
        )

        # STEP 2: Validate customer

        customer = connection.execute("""
            SELECT name, tier, state
            FROM customers
            WHERE customer_id = ?
        """, (customer_id,)).fetchone()

        if not customer:
            raise ValueError("Customer not found!")

        customer_name, tier, state = customer

        # STEP 3: Find active cart

        current_time = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        cart = connection.execute("""
            SELECT cart_id, expires_at
            FROM carts
            WHERE customer_id = ?
            AND status = 'ACTIVE'
            AND expires_at > ?
            ORDER BY cart_id DESC
            LIMIT 1
        """, (customer_id, current_time)).fetchone()

        if not cart:
            raise ValueError(
                "No active cart found or cart expired!"
            )

        cart_id, cart_expiry = cart

        # STEP 4: Read cart products

        cart_items = connection.execute("""
            SELECT
                ci.sku,
                ci.quantity,
                p.name,
                p.category,
                p.selling_price,
                p.gst_rate,
                p.weight_grams,
                p.is_sale_item
            FROM cart_items ci
            JOIN products p ON ci.sku = p.sku
            WHERE ci.cart_id = ?
        """, (cart_id,)).fetchall()

        if not cart_items:
            raise ValueError("Cart is empty!")

        # STEP 5: Validate stock reservations

        reservations = connection.execute("""
            SELECT sku, quantity, expires_at
            FROM stock_reservations
            WHERE cart_id = ?
            AND status = 'RESERVED'
        """, (cart_id,)).fetchall()

        reserved_quantities = {}

        for sku, quantity, expiry in reservations:

            if expiry <= current_time:
                raise ValueError(
                    "A stock reservation has expired!"
                )

            reserved_quantities[sku] = (
                reserved_quantities.get(sku, 0) + quantity
            )

        cart_quantities = {
            item[0]: item[1]
            for item in cart_items
        }

        if cart_quantities != reserved_quantities:
            raise ValueError(
                "Cart quantities and stock reservations do not match!"
            )

        # STEP 6: Prepare discount input

        discount_items = []

        for item in cart_items:

            discount_items.append({
                "sku": item[0],
                "category": item[3],
                "selling_price": item[4],
                "quantity": item[1],
                "is_sale_item": item[7]
            })

        # STEP 7: Calculate normal discounts

        discount_result = calculate_discounts(
            discount_items,
            coupon_code,
            bank_name,
            tier
        )

        if not discount_result["success"]:
            raise ValueError(discount_result["message"])

        discounted_items = discount_result["items"]

        # STEP 8: Calculate BOGO discounts

        bogo_result = calculate_bogo_discounts(
            connection,
            cart_items,
            discounted_items
        )

        total_bogo_discount = bogo_result["total_discount"]

        product_total = round(
            sum(item["final_amount"] for item in discounted_items),
            2
        )

        total_discount = round(
            discount_result["total_discount"]
            + total_bogo_discount,
            2
        )

        # STEP 9: Check free shipping coupon

        free_shipping = False

        if coupon_code:

            coupon = connection.execute("""
                SELECT promotion_type
                FROM promotions
                WHERE coupon_code = ?
                AND is_active = 1
            """, (coupon_code,)).fetchone()

            if coupon and coupon[0] == "FREE_SHIPPING":
                free_shipping = True

        # STEP 10: Calculate GST

        total_gst = 0
        total_cgst = 0
        total_sgst = 0
        total_igst = 0

        total_weight = 0
        invoice_items = []

        store_state = "Karnataka"

        for original, discounted in zip(
            cart_items, discounted_items
        ):

            sku = original[0]
            quantity = original[1]
            name = original[2]
            price = original[4]
            gst_rate = original[5]
            weight = original[6]

            final_item_amount = discounted["final_amount"]

            gst = calculate_gst(
                final_item_amount,
                gst_rate
            )

            # Intrastate: CGST + SGST
            if state.strip().lower() == store_state.lower():

                cgst = round(gst / 2, 2)
                sgst = round(gst - cgst, 2)
                igst = 0.0

            # Interstate: IGST
            else:

                cgst = 0.0
                sgst = 0.0
                igst = gst

            total_gst += gst
            total_cgst += cgst
            total_sgst += sgst
            total_igst += igst

            total_weight += weight * quantity

            invoice_items.append({
                "sku": sku,
                "name": name,
                "quantity": quantity,
                "unit_price": price,
                "category_discount": discounted["category_discount"],
                "coupon_discount": discounted["coupon_discount"],
                "bank_discount": discounted["bank_discount"],
                "prime_discount": discounted["prime_discount"],
                "bogo_discount": discounted["bogo_discount"],
                "gst_rate": gst_rate,
                "gst": gst,
                "cgst": cgst,
                "sgst": sgst,
                "igst": igst,
                "final_amount": final_item_amount
            })

        total_gst = round(total_gst, 2)
        total_cgst = round(total_cgst, 2)
        total_sgst = round(total_sgst, 2)
        total_igst = round(total_igst, 2)

        # STEP 11: Calculate shipping and final amount

        shipping = calculate_shipping(
            product_total,
            total_weight,
            tier,
            state,
            free_shipping
        )

        final_amount = round(
            product_total + total_gst + shipping,
            2
        )

        # STEP 12: Save coupon details

        coupon_min_order_value = 0

        if coupon_code:

            coupon_data = connection.execute("""
                SELECT min_order_value
                FROM promotions
                WHERE coupon_code = ?
                AND is_active = 1
            """, (coupon_code,)).fetchone()

            if coupon_data:
                coupon_min_order_value = coupon_data[0] or 0

        # STEP 13: Create order

        connection.execute("""
            INSERT INTO orders (
                order_id,
                customer_id,
                total_amount,
                status,
                coupon_code,
                coupon_min_order_value
            )
            VALUES (?, ?, ?, 'CREATED', ?, ?)
        """, (
            order_id,
            customer_id,
            final_amount,
            coupon_code,
            coupon_min_order_value
        ))

        # STEP 14: Ensure GST columns exist

        ensure_gst_columns(connection)

        # STEP 15: Save order items

        for item in invoice_items:

            connection.execute("""
                INSERT INTO order_items (
                    order_id,
                    sku,
                    quantity,
                    unit_price,
                    category_discount,
                    coupon_discount,
                    bank_discount,
                    prime_discount,
                    gst_rate,
                    is_returnable,
                    bogo_discount,
                    cgst_amount,
                    sgst_amount,
                    igst_amount
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
            """, (
                order_id,
                item["sku"],
                item["quantity"],
                item["unit_price"],
                item["category_discount"],
                item["coupon_discount"],
                item["bank_discount"],
                item["prime_discount"],
                item["gst_rate"],
                item["bogo_discount"],
                item["cgst"],
                item["sgst"],
                item["igst"]
            ))

        # STEP 16: Consume reservations

        connection.execute("""
            UPDATE stock_reservations
            SET status = 'CONSUMED'
            WHERE cart_id = ?
            AND status = 'RESERVED'
        """, (cart_id,))

        # STEP 17: Close cart

        connection.execute("""
            UPDATE carts
            SET status = 'CHECKED_OUT',
                updated_at = ?
            WHERE cart_id = ?
        """, (current_time, cart_id))

        # STEP 18: Commit transaction

        connection.commit()

        # STEP 19: Generate invoice

        invoice = f"""
========================================
             PS-002 INVOICE
========================================

Order ID       : {order_id}
Customer ID    : {customer_id}
Customer Name  : {customer_name}
Customer Tier  : {tier}
Delivery State : {state}

----------------------------------------
PRODUCT DETAILS
----------------------------------------
"""

        for item in invoice_items:

            invoice += f"""
Product        : {item['name']}
SKU            : {item['sku']}
Quantity       : {item['quantity']}
Unit Price     : Rs. {item['unit_price']}
Category Disc. : Rs. {item['category_discount']:.2f}
Coupon Disc.   : Rs. {item['coupon_discount']:.2f}
Bank Disc.     : Rs. {item['bank_discount']:.2f}
PRIME Disc.    : Rs. {item['prime_discount']:.2f}
BOGO Disc.     : Rs. {item['bogo_discount']:.2f}
GST ({item['gst_rate']}%)       : Rs. {item['gst']:.2f}
CGST           : Rs. {item['cgst']:.2f}
SGST           : Rs. {item['sgst']:.2f}
IGST           : Rs. {item['igst']:.2f}
Product Total  : Rs. {item['final_amount']:.2f}
----------------------------------------
"""

        invoice += f"""
Product Amount : Rs. {product_total:.2f}
Total Discount : Rs. {total_discount:.2f}
BOGO Free Items: {bogo_result['free_items']}

GST Amount     : Rs. {total_gst:.2f}
CGST Total     : Rs. {total_cgst:.2f}
SGST Total     : Rs. {total_sgst:.2f}
IGST Total     : Rs. {total_igst:.2f}

Shipping       : Rs. {shipping:.2f}

========================================
FINAL AMOUNT   : Rs. {final_amount:.2f}
========================================

Order Status: CREATED

       THANK YOU FOR SHOPPING!
========================================
"""

        output_folder = Path("output")
        output_folder.mkdir(exist_ok=True)

        with open(
            output_folder / "invoice.txt",
            "w",
            encoding="utf-8"
        ) as file:
            file.write(invoice)

        print("\nCHECKOUT SUCCESSFUL!")
        print(invoice)
        print("Invoice saved in output/invoice.txt")

    except (ValueError, sqlite3.Error) as error:

        connection.rollback()

        print("\nCHECKOUT FAILED!")
        print("Reason:", error)

    finally:
        connection.close()


if __name__ == "__main__":
    checkout()
