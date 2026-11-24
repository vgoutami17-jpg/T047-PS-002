
import csv
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "database" / "evaluation.db"
COMMAND_FILE = BASE_DIR / "sample_data" / "T047-PS-002-sample-data" / "commands.txt"
OUTPUT_DIR = BASE_DIR / "output"

OUTPUT_DIR.mkdir(exist_ok=True)

INVOICE_HEADERS = [
    "order_id", "customer_id", "checkout_ts", "gross_selling_value",
    "category_discount", "coupon_code", "coupon_discount",
    "bank_discount", "prime_discount", "bxgy_free_value",
    "taxable_value", "cgst", "sgst", "igst", "shipping",
    "invoice_total", "promotions_applied"
]

LINE_HEADERS = [
    "order_id", "sku_id", "qty", "unit_selling_price",
    "line_discount", "line_taxable", "gst_slab",
    "line_gst", "line_total"
]

LOG_HEADERS = [
    "line_no", "command", "entity_id", "status", "error_code", "message"
]

STATE_HEADERS = [
    "order_id", "final_state", "cancellation_fee",
    "refund_amount", "refund_mode", "wallet_bonus"
]

INVOICE_ROWS = []
INVOICE_LINE_ROWS = []
COMMAND_LOG = []


def money(value):
    return Decimal(str(value)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def connect_db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def timestamp(value):
    return datetime.strptime(value.strip(), "%Y-%m-%d %H:%M:%S")


def result(status, code="", message=""):
    return status, code, message


def ensure_extra_columns():
    """Add fields needed by the evaluation engine without deleting data."""
    connection = connect_db()
    try:
        additions = {
            "orders": {
                "delivered_ts": "TEXT",
                "refund_amount": "REAL DEFAULT 0",
                "refund_mode": "TEXT",
                "wallet_bonus": "REAL DEFAULT 0"
            },
            "order_items": {
                "returnable": "INTEGER DEFAULT 1"
            }
        }

        for table, columns in additions.items():
            existing = {
                row["name"]
                for row in connection.execute(
                    f"PRAGMA table_info({table})"
                ).fetchall()
            }
            for column, definition in columns.items():
                if column not in existing:
                    connection.execute(
                        f"ALTER TABLE {table} ADD COLUMN "
                        f"{column} {definition}"
                    )
        connection.commit()
    finally:
        connection.close()


def allocate(total, weights):
    """Allocate a rounded discount proportionally across line weights."""
    total = money(total)
    positive = {
        key: money(value)
        for key, value in weights.items()
        if money(value) > 0
    }
    denominator = sum(positive.values(), Decimal("0.00"))

    if not positive or denominator <= 0:
        return {}

    output = {}
    assigned = Decimal("0.00")
    keys = list(positive)

    for key in keys[:-1]:
        part = money(total * positive[key] / denominator)
        output[key] = part
        assigned += part

    output[keys[-1]] = money(total - assigned)
    return output


def get_promotion(cursor, promo_type, when, code=None,
                  category=None, bank=None, tier="REGULAR"):
    day = timestamp(when).date().isoformat()

    query = """
        SELECT * FROM promotions
        WHERE type = ?
          AND valid_from <= ?
          AND valid_to >= ?
          AND (tier = 'ALL' OR tier = ?)
    """
    params = [promo_type, day, day, tier]

    if code is not None:
        query += " AND code = ?"
        params.append(code)

    if category is not None:
        query += " AND category = ?"
        params.append(category)

    if bank is not None:
        query += " AND bank = ?"
        params.append(bank)

    return cursor.execute(query, params).fetchall()


def expire_inactive_carts(when):
    cutoff = timestamp(when) - timedelta(minutes=30)
    connection = connect_db()

    try:
        cursor = connection.cursor()
        cursor.execute("BEGIN IMMEDIATE")

        carts = cursor.execute("""
            SELECT cart_id
            FROM carts
            WHERE status = 'ACTIVE'
              AND last_activity < ?
        """, (cutoff.strftime("%Y-%m-%d %H:%M:%S"),)).fetchall()

        for cart in carts:
            cart_id = cart["cart_id"]
            reservations = cursor.execute("""
                SELECT sku_id, quantity
                FROM stock_reservations
                WHERE cart_id = ? AND status = 'RESERVED'
            """, (cart_id,)).fetchall()

            for item in reservations:
                cursor.execute("""
                    UPDATE products
                    SET stock = stock + ?
                    WHERE sku_id = ?
                """, (item["quantity"], item["sku_id"]))

            cursor.execute("""
                UPDATE stock_reservations
                SET status = 'EXPIRED'
                WHERE cart_id = ? AND status = 'RESERVED'
            """, (cart_id,))

            cursor.execute("""
                UPDATE carts SET status = 'EXPIRED'
                WHERE cart_id = ?
            """, (cart_id,))

        connection.commit()
        return len(carts)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def active_cart(cursor, cart_id):
    return cursor.execute("""
        SELECT * FROM carts
        WHERE cart_id = ? AND status = 'ACTIVE'
    """, (cart_id,)).fetchone()


def handle_cart_create(parts):
    cart_id, customer_id, when = parts[1:4]
    timestamp(when)

    connection = connect_db()
    try:
        cursor = connection.cursor()

        if not cursor.execute(
            "SELECT 1 FROM customers WHERE customer_id = ?",
            (customer_id,)
        ).fetchone():
            return result("REJECTED", "CUSTOMER_NOT_FOUND",
                          "Customer does not exist")

        if cursor.execute(
            "SELECT 1 FROM carts WHERE cart_id = ?", (cart_id,)
        ).fetchone():
            return result("REJECTED", "CART_EXISTS", "Cart already exists")

        cursor.execute("""
            INSERT INTO carts
            (cart_id, customer_id, created_at, last_activity, status)
            VALUES (?, ?, ?, ?, 'ACTIVE')
        """, (cart_id, customer_id, when, when))

        connection.commit()
        return result("OK", "", "Cart created")
    finally:
        connection.close()


def handle_cart_add(parts):
    cart_id, sku, qty, when = parts[1:5]
    qty = int(qty)
    timestamp(when)

    if qty <= 0:
        return result("REJECTED", "INVALID_QUANTITY",
                      "Quantity must be positive")

    connection = connect_db()
    try:
        cursor = connection.cursor()
        cursor.execute("BEGIN IMMEDIATE")

        cart = active_cart(cursor, cart_id)
        if not cart:
            return result("REJECTED", "CART_NOT_ACTIVE",
                          "Cart is not active")

        product = cursor.execute(
            "SELECT stock FROM products WHERE sku_id = ?", (sku,)
        ).fetchone()

        if not product:
            return result("REJECTED", "SKU_NOT_FOUND",
                          "Product does not exist")

        old = cursor.execute("""
            SELECT quantity FROM cart_items
            WHERE cart_id = ? AND sku_id = ?
        """, (cart_id, sku)).fetchone()

        old_qty = old["quantity"] if old else 0

        reservation = cursor.execute("""
            SELECT quantity, status FROM stock_reservations
            WHERE cart_id = ? AND sku_id = ?
        """, (cart_id, sku)).fetchone()

        reserved = (
            reservation["quantity"]
            if reservation and reservation["status"] == "RESERVED"
            else 0
        )

        new_qty = old_qty + qty
        additional = new_qty - reserved

        if additional > product["stock"]:
            return result("REJECTED", "STOCK_SHORT",
                          "Insufficient stock")

        if old:
            cursor.execute("""
                UPDATE cart_items SET quantity = ?
                WHERE cart_id = ? AND sku_id = ?
            """, (new_qty, cart_id, sku))
        else:
            cursor.execute("""
                INSERT INTO cart_items VALUES (?, ?, ?)
            """, (cart_id, sku, new_qty))

        if reservation:
            cursor.execute("""
                UPDATE stock_reservations
                SET quantity = ?, status = 'RESERVED', reserved_at = ?
                WHERE cart_id = ? AND sku_id = ?
            """, (new_qty, when, cart_id, sku))
        else:
            cursor.execute("""
                INSERT INTO stock_reservations
                (cart_id, sku_id, quantity, status, reserved_at)
                VALUES (?, ?, ?, 'RESERVED', ?)
            """, (cart_id, sku, new_qty, when))

        cursor.execute("""
            UPDATE products SET stock = stock - ?
            WHERE sku_id = ?
        """, (additional, sku))

        cursor.execute("""
            UPDATE carts SET last_activity = ?
            WHERE cart_id = ?
        """, (when, cart_id))

        connection.commit()
        return result("OK", "", "Product added and stock reserved")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def handle_cart_remove(parts):
    cart_id, sku, when = parts[1:4]
    timestamp(when)

    connection = connect_db()
    try:
        cursor = connection.cursor()
        cursor.execute("BEGIN IMMEDIATE")

        if not active_cart(cursor, cart_id):
            return result("REJECTED", "CART_NOT_ACTIVE",
                          "Cart is not active")

        item = cursor.execute("""
            SELECT quantity FROM cart_items
            WHERE cart_id = ? AND sku_id = ?
        """, (cart_id, sku)).fetchone()

        if not item:
            return result("REJECTED", "ITEM_NOT_FOUND",
                          "Product is not in cart")

        reservation = cursor.execute("""
            SELECT quantity, status FROM stock_reservations
            WHERE cart_id = ? AND sku_id = ?
        """, (cart_id, sku)).fetchone()

        if reservation and reservation["status"] == "RESERVED":
            cursor.execute("""
                UPDATE products SET stock = stock + ?
                WHERE sku_id = ?
            """, (reservation["quantity"], sku))

            cursor.execute("""
                UPDATE stock_reservations
                SET quantity = 0, status = 'RELEASED'
                WHERE cart_id = ? AND sku_id = ?
            """, (cart_id, sku))

        cursor.execute("""
            DELETE FROM cart_items WHERE cart_id = ? AND sku_id = ?
        """, (cart_id, sku))

        cursor.execute("""
            UPDATE carts SET last_activity = ? WHERE cart_id = ?
        """, (when, cart_id))

        connection.commit()
        return result("OK", "", "Product removed")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def handle_cart_update(parts):
    cart_id, sku, qty, when = parts[1:5]
    qty = int(qty)
    timestamp(when)

    if qty <= 0:
        return result("REJECTED", "INVALID_QUANTITY",
                      "Quantity must be positive")

    connection = connect_db()
    try:
        cursor = connection.cursor()
        cursor.execute("BEGIN IMMEDIATE")

        if not active_cart(cursor, cart_id):
            return result("REJECTED", "CART_NOT_ACTIVE",
                          "Cart is not active")

        item = cursor.execute("""
            SELECT quantity FROM cart_items
            WHERE cart_id = ? AND sku_id = ?
        """, (cart_id, sku)).fetchone()

        if not item:
            return result("REJECTED", "ITEM_NOT_FOUND",
                          "Product is not in cart")

        product = cursor.execute(
            "SELECT stock FROM products WHERE sku_id = ?", (sku,)
        ).fetchone()

        reservation = cursor.execute("""
            SELECT quantity, status FROM stock_reservations
            WHERE cart_id = ? AND sku_id = ?
        """, (cart_id, sku)).fetchone()

        old_reserved = (
            reservation["quantity"]
            if reservation and reservation["status"] == "RESERVED"
            else 0
        )

        change = qty - old_reserved

        if change > product["stock"]:
            return result("REJECTED", "STOCK_SHORT",
                          "Insufficient stock")

        cursor.execute("""
            UPDATE products SET stock = stock - ? WHERE sku_id = ?
        """, (change, sku))

        cursor.execute("""
            UPDATE cart_items SET quantity = ?
            WHERE cart_id = ? AND sku_id = ?
        """, (qty, cart_id, sku))

        if reservation:
            cursor.execute("""
                UPDATE stock_reservations
                SET quantity = ?, status = 'RESERVED', reserved_at = ?
                WHERE cart_id = ? AND sku_id = ?
            """, (qty, when, cart_id, sku))
        else:
            cursor.execute("""
                INSERT INTO stock_reservations
                (cart_id, sku_id, quantity, status, reserved_at)
                VALUES (?, ?, ?, 'RESERVED', ?)
            """, (cart_id, sku, qty, when))

        cursor.execute("""
            UPDATE carts SET last_activity = ? WHERE cart_id = ?
        """, (when, cart_id))

        connection.commit()
        return result("OK", "", "Cart quantity updated")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def handle_apply_coupon(parts):
    cart_id, code, when = parts[1:4]
    timestamp(when)

    connection = connect_db()
    try:
        cursor = connection.cursor()
        cursor.execute("BEGIN IMMEDIATE")

        cart = active_cart(cursor, cart_id)
        if not cart:
            return result("REJECTED", "CART_NOT_ACTIVE",
                          "Cart is not active")

        if cart["coupon_code"]:
            return result("REJECTED", "COUPON_ALREADY_APPLIED",
                          "Only one coupon is allowed")

        promo = cursor.execute("""
            SELECT promo_id FROM promotions
            WHERE code = ?
              AND type IN ('PERCENT_COUPON', 'FLAT_COUPON')
        """, (code,)).fetchone()

        if not promo:
            return result("REJECTED", "INVALID_COUPON",
                          "Coupon does not exist")

        cursor.execute("""
            UPDATE carts SET coupon_code = ?, last_activity = ?
            WHERE cart_id = ?
        """, (code, when, cart_id))

        connection.commit()
        return result("OK", "", "Coupon recorded for checkout validation")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def handle_stock_adjust(parts):
    sku, delta, when, reason = parts[1:5]
    delta = int(delta)
    timestamp(when)

    if delta == 0:
        return result("REJECTED", "INVALID_ADJUSTMENT",
                      "Adjustment cannot be zero")

    connection = connect_db()
    try:
        cursor = connection.cursor()
        cursor.execute("BEGIN IMMEDIATE")

        product = cursor.execute(
            "SELECT stock FROM products WHERE sku_id = ?", (sku,)
        ).fetchone()

        if not product:
            return result("REJECTED", "SKU_NOT_FOUND",
                          "Product does not exist")

        new_stock = product["stock"] + delta
        if new_stock < 0:
            return result("REJECTED", "INSUFFICIENT_STOCK",
                          "Stock cannot become negative")

        cursor.execute(
            "UPDATE products SET stock = ? WHERE sku_id = ?",
            (new_stock, sku)
        )
        connection.commit()
        return result("OK", "", f"Stock adjusted: {reason}")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def calculate_discount(cursor, items, when, tier, coupon_code, bank):
    """Calculate category, coupon, bank and PRIME discounts in order."""
    paid = {x["sku_id"]: x for x in items}
    gross = {
        sku: money(x["selling_price"] * x["quantity"])
        for sku, x in paid.items()
    }

    category = {}
    for sku, item in paid.items():
        promos = get_promotion(
            cursor, "CATEGORY_OFFER", when,
            category=item["category"], tier=tier
        )
        if promos and not item["on_sale"]:
            promo = promos[0]
            amount = money(
                gross[sku] * Decimal(str(promo["discount_pct"])) / 100
            )
            cap = money(promo["cap_amount"])
            if cap > 0:
                amount = min(amount, cap)
            category[sku] = amount

    coupon = {}
    coupon_promo = None

    if coupon_code:
        for kind in ("PERCENT_COUPON", "FLAT_COUPON"):
            found = get_promotion(
                cursor, kind, when, code=coupon_code, tier=tier
            )
            if found:
                coupon_promo = found[0]
                break

        if coupon_promo:
            eligible = {
                sku: max(Decimal("0.00"), gross[sku] - category.get(sku, 0))
                for sku, x in paid.items() if not x["on_sale"]
            }
            subtotal = sum(eligible.values(), Decimal("0.00"))
            if subtotal >= money(coupon_promo["min_cart_value"]):
                if coupon_promo["type"] == "PERCENT_COUPON":
                    amount = money(
                        subtotal * Decimal(str(coupon_promo["discount_pct"])) / 100
                    )
                else:
                    amount = money(coupon_promo["discount_flat"])

                cap = money(coupon_promo["cap_amount"])
                if cap > 0:
                    amount = min(amount, cap)
                coupon = allocate(min(amount, subtotal), eligible)

    bank_discount = {}
    bank_promo = None

    if bank:
        found = get_promotion(
            cursor, "BANK_OFFER", when, bank=bank, tier=tier
        )
        if found:
            bank_promo = found[0]
            eligible = {
                sku: max(
                    Decimal("0.00"),
                    gross[sku] - category.get(sku, 0) - coupon.get(sku, 0)
                )
                for sku, x in paid.items() if not x["on_sale"]
            }
            subtotal = sum(eligible.values(), Decimal("0.00"))
            if subtotal >= money(bank_promo["min_cart_value"]):
                amount = money(
                    subtotal * Decimal(str(bank_promo["discount_pct"])) / 100
                )
                cap = money(bank_promo["cap_amount"])
                if cap > 0:
                    amount = min(amount, cap)
                bank_discount = allocate(min(amount, subtotal), eligible)

    prime = {}
    if tier == "PRIME":
        eligible = {
            sku: gross[sku]
            for sku, x in paid.items()
            if x["category"] == "ELECTRONICS" and not x["on_sale"]
        }
        subtotal = sum(eligible.values(), Decimal("0.00"))
        amount = min(money(subtotal * Decimal("0.05")), Decimal("1000.00"))
        prime = allocate(amount, eligible)

    # Apply the 70% cap to paid lines, reducing lower-priority discounts first.
    for sku in paid:
        limit = money(gross[sku] * Decimal("0.70"))
        values = [
            category.get(sku, Decimal("0.00")),
            coupon.get(sku, Decimal("0.00")),
            bank_discount.get(sku, Decimal("0.00")),
            prime.get(sku, Decimal("0.00"))
        ]
        excess = max(Decimal("0.00"), sum(values) - limit)

        for index in (3, 2, 1, 0):
            reduction = min(values[index], excess)
            values[index] -= reduction
            excess -= reduction

        category[sku], coupon[sku], bank_discount[sku], prime[sku] = values

    return category, coupon, bank_discount, prime, coupon_promo, bank_promo


def handle_checkout(parts):
    cart_id, payment, bank, when = parts[1:5]
    payment = payment.upper()
    bank = bank.upper() or None
    timestamp(when)

    if payment not in ("UPI", "CARD", "COD", "WALLET"):
        return result("REJECTED", "INVALID_PAYMENT_MODE",
                      "Invalid payment mode")

    if payment == "CARD" and not bank:
        return result("REJECTED", "BANK_REQUIRED",
                      "CARD payment requires a bank")

    if payment != "CARD" and bank:
        return result("REJECTED", "INVALID_BANK",
                      "Bank is allowed only for CARD")

    expire_inactive_carts(when)

    connection = connect_db()
    try:
        cursor = connection.cursor()
        cursor.execute("BEGIN IMMEDIATE")

        cart = active_cart(cursor, cart_id)
        if not cart:
            return result("REJECTED", "CART_EXPIRED_OR_INACTIVE",
                          "Cart is not active or reservation expired")

        customer = cursor.execute("""
            SELECT * FROM customers WHERE customer_id = ?
        """, (cart["customer_id"],)).fetchone()

        if not customer:
            return result("REJECTED", "CUSTOMER_NOT_FOUND",
                          "Customer does not exist")

        rows = cursor.execute("""
            SELECT ci.sku_id, ci.quantity, p.name, p.category,
                   p.selling_price, p.weight_g, p.on_sale,
                   p.gst_slab, p.returnable, p.stock
            FROM cart_items ci
            JOIN products p ON p.sku_id = ci.sku_id
            WHERE ci.cart_id = ?
            ORDER BY ci.sku_id
        """, (cart_id,)).fetchall()

        if not rows:
            return result("REJECTED", "EMPTY_CART", "Cart is empty")

        items = []
        for row in rows:
            items.append({
                "sku_id": row["sku_id"],
                "quantity": int(row["quantity"]),
                "name": row["name"],
                "category": row["category"],
                "selling_price": money(row["selling_price"]),
                "weight_g": int(row["weight_g"]),
                "on_sale": bool(row["on_sale"]),
                "gst_slab": money(row["gst_slab"]),
                "returnable": bool(row["returnable"]),
                "stock": int(row["stock"])
            })

        reservations = cursor.execute("""
            SELECT sku_id, quantity, status
            FROM stock_reservations
            WHERE cart_id = ?
        """, (cart_id,)).fetchall()

        reserved = {
            x["sku_id"]: x["quantity"]
            for x in reservations if x["status"] == "RESERVED"
        }
        quantities = {x["sku_id"]: x["quantity"] for x in items}

        if reserved != quantities:
            return result("REJECTED", "RESERVATION_MISMATCH",
                          "Reservations do not match cart quantities")

        for item in items:
            if item["stock"] < 0:
                return result("REJECTED", "STOCK_SHORT",
                              "Insufficient stock")

        # Buy-X-get-Y: cheapest eligible units are free.
        bogo_free = {}
        promos = get_promotion(
            cursor, "BUY_X_GET_Y", when,
            category="FASHION", tier=customer["tier"]
        )

        if promos:
            promo = promos[0]
            buy = int(promo["buy_qty"] or 0)
            get = int(promo["get_qty"] or 0)

            if buy > 0 and get > 0:
                units = []
                for item in items:
                    if item["category"] == "FASHION" and not item["on_sale"]:
                        for _ in range(item["quantity"]):
                            units.append((item["selling_price"], item["sku_id"]))

                units.sort()
                group_size = buy + get
                for start in range(0, len(units) // group_size * group_size,
                                   group_size):
                    for _, sku in units[start:start + get]:
                        bogo_free[sku] = bogo_free.get(sku, 0) + 1

        paid_items = []
        for item in items:
            paid_qty = item["quantity"] - bogo_free.get(item["sku_id"], 0)
            if paid_qty > 0:
                copy = item.copy()
                copy["quantity"] = paid_qty
                paid_items.append(copy)

        category, coupon, bank_discounts, prime, coupon_promo, bank_promo = (
            calculate_discount(
                cursor, paid_items, when, customer["tier"],
                cart["coupon_code"], bank if payment == "CARD" else None
            )
        )

        order_id = "ORD-" + cart_id.split("-")[-1]
        if cursor.execute(
            "SELECT 1 FROM orders WHERE order_id = ?", (order_id,)
        ).fetchone():
            return result("REJECTED", "ORDER_EXISTS", "Order already exists")

        totals = {
            "gross": Decimal("0.00"),
            "category": Decimal("0.00"),
            "coupon": Decimal("0.00"),
            "bank": Decimal("0.00"),
            "prime": Decimal("0.00"),
            "bogo": Decimal("0.00"),
            "taxable": Decimal("0.00"),
            "cgst": Decimal("0.00"),
            "sgst": Decimal("0.00"),
            "igst": Decimal("0.00")
        }

        invoice_lines = []
        total_weight = 0

        for item in items:
            sku = item["sku_id"]
            price = item["selling_price"]
            qty = item["quantity"]
            free_qty = bogo_free.get(sku, 0)
            paid_qty = qty - free_qty
            totals["gross"] += money(price * qty)
            total_weight += item["weight_g"] * qty

            if paid_qty:
                line_discount = money(
                    category.get(sku, 0) + coupon.get(sku, 0)
                    + bank_discounts.get(sku, 0) + prime.get(sku, 0)
                )
                taxable = money(price * paid_qty - line_discount)
                gst = money(taxable * item["gst_slab"] / 100)

                if customer["state"].strip().upper() == "KARNATAKA":
                    cgst = money(gst / 2)
                    sgst = money(gst - cgst)
                    igst = Decimal("0.00")
                else:
                    cgst = Decimal("0.00")
                    sgst = Decimal("0.00")
                    igst = gst

                line_total = money(taxable + gst)

                invoice_lines.append({
                    "order_id": order_id, "sku_id": sku, "qty": paid_qty,
                    "unit_selling_price": f"{price:.2f}",
                    "line_discount": f"{line_discount:.2f}",
                    "line_taxable": f"{taxable:.2f}",
                    "gst_slab": f"{item['gst_slab']:.2f}",
                    "line_gst": f"{gst:.2f}",
                    "line_total": f"{line_total:.2f}",
                    "returnable": int(item["returnable"])
                })

                totals["category"] += category.get(sku, 0)
                totals["coupon"] += coupon.get(sku, 0)
                totals["bank"] += bank_discounts.get(sku, 0)
                totals["prime"] += prime.get(sku, 0)
                totals["taxable"] += taxable
                totals["cgst"] += cgst
                totals["sgst"] += sgst
                totals["igst"] += igst

            if free_qty:
                free_value = money(price * free_qty)
                totals["bogo"] += free_value
                invoice_lines.append({
                    "order_id": order_id, "sku_id": sku, "qty": free_qty,
                    "unit_selling_price": "0.00",
                    "line_discount": f"{free_value:.2f}",
                    "line_taxable": "0.00",
                    "gst_slab": f"{item['gst_slab']:.2f}",
                    "line_gst": "0.00",
                    "line_total": "0.00",
                    "returnable": int(item["returnable"])
                })

        discounted_value = money(
            totals["gross"] - totals["category"] - totals["coupon"]
            - totals["bank"] - totals["prime"] - totals["bogo"]
        )

        free_ship = get_promotion(
            cursor, "FREE_SHIP_THRESHOLD", when,
            category="BOOKS", tier=customer["tier"]
        )
        books_total = sum(
            (x["selling_price"] * x["quantity"]
             for x in items if x["category"] == "BOOKS"),
            Decimal("0.00")
        )
        free_shipping = bool(
            free_ship and books_total >= money(free_ship[0]["min_cart_value"])
        )

        if customer["tier"] == "PRIME" or discounted_value >= 499 or free_shipping:
            shipping = Decimal("0.00")
        else:
            shipping = Decimal("49.00")
            if total_weight > 2000:
                blocks = (total_weight - 2000 + 499) // 500
                shipping += Decimal(blocks) * Decimal("30.00")

            north_east = {
                "ASSAM", "ARUNACHAL PRADESH", "MANIPUR",
                "MEGHALAYA", "MIZORAM", "NAGALAND", "SIKKIM", "TRIPURA"
            }
            if customer["state"].strip().upper() in north_east:
                shipping += Decimal("100.00")

        gst_total = money(totals["cgst"] + totals["sgst"] + totals["igst"])
        invoice_total = money(totals["taxable"] + gst_total + shipping)

        if payment == "WALLET":
            balance = money(customer["wallet_balance"])
            if balance < invoice_total:
                return result("REJECTED", "INSUFFICIENT_WALLET",
                              "Wallet balance is insufficient")
            cursor.execute("""
                UPDATE customers SET wallet_balance = wallet_balance - ?
                WHERE customer_id = ?
            """, (float(invoice_total), customer["customer_id"]))

        cursor.execute("""
            INSERT INTO orders (
                order_id, cart_id, customer_id, checkout_ts,
                payment_mode, bank, status, gross_selling_value,
                invoice_total
            )
            VALUES (?, ?, ?, ?, ?, ?, 'CREATED', ?, ?)
        """, (
            order_id, cart_id, customer["customer_id"], when,
            payment, bank if payment == "CARD" else None,
            float(totals["gross"]), float(invoice_total)
        ))

        for line in invoice_lines:
            cursor.execute("""
                INSERT INTO order_items (
                    order_id, sku_id, quantity, unit_selling_price,
                    line_discount, line_taxable, gst_slab, line_gst,
                    line_total, returnable
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                order_id, line["sku_id"], line["qty"],
                float(line["unit_selling_price"]),
                float(line["line_discount"]),
                float(line["line_taxable"]),
                float(line["gst_slab"]),
                float(line["line_gst"]),
                float(line["line_total"]),
                line["returnable"]
            ))

        cursor.execute("""
            UPDATE stock_reservations SET status = 'CONSUMED'
            WHERE cart_id = ? AND status = 'RESERVED'
        """, (cart_id,))

        cursor.execute("""
            UPDATE carts SET status = 'CHECKED_OUT' WHERE cart_id = ?
        """, (cart_id,))

        connection.commit()

        promotions = []
        if totals["category"]:
            promotions.append("CATEGORY_OFFER")
        if totals["coupon"]:
            promotions.append("COUPON:" + str(cart["coupon_code"]))
        if totals["bank"]:
            promotions.append("BANK:" + str(bank))
        if totals["prime"]:
            promotions.append("PRIME_5_PERCENT")
        if totals["bogo"]:
            promotions.append("BXGY")

        INVOICE_ROWS.append({
            "order_id": order_id,
            "customer_id": customer["customer_id"],
            "checkout_ts": when,
            "gross_selling_value": f"{totals['gross']:.2f}",
            "category_discount": f"{totals['category']:.2f}",
            "coupon_code": cart["coupon_code"] or "",
            "coupon_discount": f"{totals['coupon']:.2f}",
            "bank_discount": f"{totals['bank']:.2f}",
            "prime_discount": f"{totals['prime']:.2f}",
            "bxgy_free_value": f"{totals['bogo']:.2f}",
            "taxable_value": f"{totals['taxable']:.2f}",
            "cgst": f"{totals['cgst']:.2f}",
            "sgst": f"{totals['sgst']:.2f}",
            "igst": f"{totals['igst']:.2f}",
            "shipping": f"{shipping:.2f}",
            "invoice_total": f"{invoice_total:.2f}",
            "promotions_applied": ";".join(promotions)
        })

        for line in invoice_lines:
            INVOICE_LINE_ROWS.append({
                key: value for key, value in line.items()
                if key != "returnable"
            })

        return result("OK", "",
                      f"Checkout successful. Order {order_id}. Total Rs. {invoice_total:.2f}")

    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def handle_order_status(parts):
    order_id, new_state, when = parts[1:4]
    new_state = new_state.upper()
    sku = parts[4].strip() if len(parts) > 4 else None
    timestamp(when)

    transitions = {
        "CONFIRMED": ("CREATED",),
        "PACKED": ("CONFIRMED",),
        "SHIPPED": ("PACKED", "SHIPPED"),
        "DELIVERED": ("SHIPPED",)
    }

    if new_state not in transitions:
        return result("REJECTED", "INVALID_STATUS", "Invalid order status")

    connection = connect_db()
    try:
        cursor = connection.cursor()
        cursor.execute("BEGIN IMMEDIATE")

        order = cursor.execute("""
            SELECT status FROM orders WHERE order_id = ?
        """, (order_id,)).fetchone()

        if not order:
            return result("REJECTED", "ORDER_NOT_FOUND", "Order not found")

        if order["status"] not in transitions[new_state]:
            return result("REJECTED", "ILLEGAL_TRANSITION",
                          "Order transition is not allowed")

        if new_state == "SHIPPED":
            if sku:
                item = cursor.execute("""
                    SELECT quantity, shipped_quantity FROM order_items
                    WHERE order_id = ? AND sku_id = ?
                """, (order_id, sku)).fetchone()

                if not item:
                    return result("REJECTED", "ITEM_NOT_FOUND",
                                  "SKU is not in this order")

                if item["shipped_quantity"] >= item["quantity"]:
                    return result("REJECTED", "ALREADY_SHIPPED",
                                  "Item is already shipped")

                cursor.execute("""
                    UPDATE order_items
                    SET shipped_quantity = quantity
                    WHERE order_id = ? AND sku_id = ?
                """, (order_id, sku))
            else:
                cursor.execute("""
                    UPDATE order_items SET shipped_quantity = quantity
                    WHERE order_id = ?
                """, (order_id,))

        if new_state == "DELIVERED":
            pending = cursor.execute("""
                SELECT COUNT(*) AS n FROM order_items
                WHERE order_id = ? AND shipped_quantity < quantity
            """, (order_id,)).fetchone()["n"]

            if pending:
                return result("REJECTED", "ITEMS_NOT_SHIPPED",
                              "All items must be shipped first")

            cursor.execute("""
                UPDATE orders SET delivered_ts = ? WHERE order_id = ?
            """, (when, order_id))

        cursor.execute("""
            UPDATE orders SET status = ? WHERE order_id = ?
        """, (new_state, order_id))

        connection.commit()
        return result("OK", "", f"Order status updated to {new_state}")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def handle_cancel(parts):
    order_id, when = parts[1:3]
    timestamp(when)

    connection = connect_db()
    try:
        cursor = connection.cursor()
        cursor.execute("BEGIN IMMEDIATE")

        order = cursor.execute("""
            SELECT status, invoice_total FROM orders WHERE order_id = ?
        """, (order_id,)).fetchone()

        if not order:
            return result("REJECTED", "ORDER_NOT_FOUND", "Order not found")

        state = order["status"]
        if state in ("SHIPPED", "DELIVERED", "CANCELLED",
                     "RETURN_REQUESTED", "RETURNED", "REFUNDED"):
            return result("REJECTED", "CANCEL_NOT_ALLOWED",
                          "Order cannot be cancelled in this state")

        if state not in ("CREATED", "CONFIRMED", "PACKED"):
            return result("REJECTED", "INVALID_ORDER_STATE",
                          "Order cannot be cancelled")

        fee = (
            money(Decimal(str(order["invoice_total"])) * Decimal("0.02"))
            if state == "PACKED" else Decimal("0.00")
        )

        items = cursor.execute("""
            SELECT sku_id, quantity, shipped_quantity
            FROM order_items WHERE order_id = ?
        """, (order_id,)).fetchall()

        for item in items:
            remaining = item["quantity"] - item["shipped_quantity"]
            if remaining > 0:
                cursor.execute("""
                    UPDATE products SET stock = stock + ?
                    WHERE sku_id = ?
                """, (remaining, item["sku_id"]))

        cursor.execute("""
            UPDATE orders SET status = 'CANCELLED',
                cancellation_fee = ?
            WHERE order_id = ?
        """, (float(fee), order_id))

        connection.commit()
        return result("OK", "", f"Order cancelled; fee Rs. {fee:.2f}")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def handle_return_request(parts):
    order_id, sku, qty, mode, when = parts[1:6]
    qty = int(qty)
    mode = mode.upper()
    timestamp(when)

    if qty <= 0:
        return result("REJECTED", "INVALID_QUANTITY",
                      "Return quantity must be positive")

    if mode not in ("ORIGINAL", "WALLET"):
        return result("REJECTED", "INVALID_REFUND_MODE",
                      "Refund mode must be ORIGINAL or WALLET")

    connection = connect_db()
    try:
        cursor = connection.cursor()
        cursor.execute("BEGIN IMMEDIATE")

        order = cursor.execute("""
            SELECT o.status, o.delivered_ts, c.tier
            FROM orders o JOIN customers c
              ON c.customer_id = o.customer_id
            WHERE o.order_id = ?
        """, (order_id,)).fetchone()

        if not order:
            return result("REJECTD", "ORDER_NOT_FOUND", "Order not found")

        if order["status"] not in ("DELIVERED", "RETURN_REQUESTED"):
            return result("REJECTED", "ORDER_NOT_DELIVERED",
                          "Only delivered orders can be returned")

        if not order["delivered_ts"]:
            return result("REJECTED", "DELIVERY_DATE_MISSING",
                          "Delivery timestamp is missing")

        delivered = timestamp(order["delivered_ts"])
        requested = timestamp(when)
        allowed_days = 30 if order["tier"] == "PRIME" else 10

        if requested.date() > (delivered + timedelta(days=allowed_days)).date():
            return result("REJECTED", "RETURN_WINDOW_EXPIRED",
                          "Return window has expired")

        item = cursor.execute("""
            SELECT quantity, returned_quantity, returnable
            FROM order_items
            WHERE order_id = ? AND sku_id = ?
        """, (order_id, sku)).fetchone()

        if not item:
            return result("REJECTED", "ITEM_NOT_FOUND",
                          "SKU is not in this order")

        if not item["returnable"]:
            return result("REJECTED", "NON_RETURNABLE",
                          "This product cannot be returned")

        available = item["quantity"] - item["returned_quantity"]
        if qty > available:
            return result("REJECTED", "RETURN_QUANTITY_EXCEEDED",
                          "Return quantity exceeds unreturned quantity")

        cursor.execute("""
            INSERT INTO returns
            (order_id, sku_id, quantity, refund_mode,
             refund_amount, status, requested_at)
            VALUES (?, ?, ?, ?, 0, 'REQUESTED', ?)
        """, (order_id, sku, qty, mode, when))

        cursor.execute("""
            UPDATE orders SET status = 'RETURN_REQUESTED'
            WHERE order_id = ?
        """, (order_id,))

        connection.commit()
        return result("OK", "", "Return request accepted")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()



def handle_return_received(parts):
    order_id, sku, when = parts[1:4]
    timestamp(when)

    connection = connect_db()

    try:
        cursor = connection.cursor()
        cursor.execute("BEGIN IMMEDIATE")

        request = cursor.execute("""
            SELECT * FROM returns
            WHERE order_id = ? AND sku_id = ? AND status = 'REQUESTED'
            ORDER BY return_id LIMIT 1
        """, (order_id, sku)).fetchone()

        if not request:
            connection.rollback()
            return result(
                "REJECTED",
                "RETURN_NOT_FOUND",
                "No pending return request"
            )

        item = cursor.execute("""
            SELECT * FROM order_items
            WHERE order_id = ? AND sku_id = ?
            AND quantity > returned_quantity
            ORDER BY order_item_id LIMIT 1
        """, (order_id, sku)).fetchone()

        if not item:
            connection.rollback()
            return result(
                "REJECTED",
                "RETURN_QUANTITY_EXCEEDED",
                "No remaining quantity available for return"
            )

        qty = request["quantity"]

        remaining_qty = (
            item["quantity"] - item["returned_quantity"]
        )

        if qty > remaining_qty:
            connection.rollback()
            return result(
                "REJECTED",
                "RETURN_QUANTITY_EXCEEDED",
                "Return quantity exceeds remaining quantity"
            )

        # Calculate proportional refund
        if item["quantity"] > 0:
            unit_refund = (
                Decimal(str(item["line_total"])) /
                Decimal(str(item["quantity"]))
            )
            refund = money(unit_refund * qty)
        else:
            refund = Decimal("0.00")

        # Calculate 2% wallet bonus
        bonus = (
            money(refund * Decimal("0.02"))
            if request["refund_mode"] == "WALLET"
            else Decimal("0.00")
        )

        # Credit wallet when WALLET refund is selected
        if request["refund_mode"] == "WALLET":
            cursor.execute("""
                UPDATE customers
                SET wallet_balance = wallet_balance + ?
                WHERE customer_id = (
                    SELECT customer_id
                    FROM orders
                    WHERE order_id = ?
                )
            """, (float(refund + bonus), order_id))

        # Update returned quantity
        cursor.execute("""
            UPDATE order_items
            SET returned_quantity = returned_quantity + ?
            WHERE order_item_id = ?
        """, (qty, item["order_item_id"]))

        # Restore returned product stock
        cursor.execute("""
            UPDATE products
            SET stock = stock + ?
            WHERE sku_id = ?
        """, (qty, sku))

        # Complete this return request
        cursor.execute("""
            UPDATE returns
            SET status = 'REFUNDED',
                refund_amount = ?,
                received_at = ?
            WHERE return_id = ?
        """, (
            float(refund),
            when,
            request["return_id"]
        ))

        # Update refund details
        cursor.execute("""
            UPDATE orders
            SET refund_amount = COALESCE(refund_amount, 0) + ?,
                refund_mode = ?,
                wallet_bonus = COALESCE(wallet_bonus, 0) + ?
            WHERE order_id = ?
        """, (
            float(refund),
            request["refund_mode"],
            float(bonus),
            order_id
        ))

        # Check whether other return requests are pending
        pending = cursor.execute("""
            SELECT COUNT(*) AS n
            FROM returns
            WHERE order_id = ?
            AND status = 'REQUESTED'
        """, (order_id,)).fetchone()["n"]

        # Check whether every ordered unit has been returned
        quantities = cursor.execute("""
            SELECT
                COALESCE(SUM(quantity), 0) AS ordered,
                COALESCE(SUM(returned_quantity), 0) AS returned
            FROM order_items
            WHERE order_id = ?
        """, (order_id,)).fetchone()

        if pending > 0:
            new_status = "RETURN_REQUESTED"

        elif quantities["ordered"] == quantities["returned"]:
            new_status = "REFUNDED"

        else:
            new_status = "RETURNED"

        cursor.execute("""
            UPDATE orders
            SET status = ?
            WHERE order_id = ?
        """, (new_status, order_id))

        connection.commit()

        return result(
            "OK",
            "",
            f"Return received. Refund Rs. {refund:.2f}"
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def write_csv(filename, headers, rows):
    path = OUTPUT_DIR / filename
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def generate_order_states():
    connection = connect_db()
    try:
        rows = connection.execute("""
            SELECT order_id, status, cancellation_fee,
                   refund_amount, refund_mode, wallet_bonus
            FROM orders ORDER BY rowid
        """).fetchall()

        output = []
        for row in rows:
            output.append({
                "order_id": row["order_id"],
                "final_state": row["status"],
                "cancellation_fee": f"{money(row['cancellation_fee'] or 0):.2f}",
                "refund_amount": f"{money(row['refund_amount'] or 0):.2f}",
                "refund_mode": row["refund_mode"] or "",
                "wallet_bonus": f"{money(row['wallet_bonus'] or 0):.2f}"
            })
        return output
    finally:
        connection.close()
HANDLERS = {
    "CART_CREATE": handle_cart_create,
    "CART_ADD": handle_cart_add,
    "CART_REMOVE": handle_cart_remove,
    "CART_UPDATE": handle_cart_update,
    "APPLY_COUPON": handle_apply_coupon,
    "STOCK_ADJUST": handle_stock_adjust,
    "CHECKOUT": handle_checkout,
    "ORDER_STATUS": handle_order_status,
    "CANCEL": handle_cancel,
    "RETURN_REQUEST": handle_return_request,
    "RETURN_RECEIVED": handle_return_received,
}


def process_commands():
    global INVOICE_ROWS, INVOICE_LINE_ROWS, COMMAND_LOG

    INVOICE_ROWS = []
    INVOICE_LINE_ROWS = []
    COMMAND_LOG = []

    if not COMMAND_FILE.exists():
        raise FileNotFoundError(f"Command file not found: {COMMAND_FILE}")

    with COMMAND_FILE.open("r", encoding="utf-8-sig") as file:
        for line_no, raw in enumerate(file, start=1):
            line = raw.strip()

            if not line or line.startswith("#"):
                continue

            parts = [part.strip() for part in line.split("|")]
            command = parts[0].upper()
            entity_id = parts[1] if len(parts) > 1 else ""

            handler = HANDLERS.get(command)

            if not handler:
                status, code, message = (
                    "REJECTED", "UNKNOWN_COMMAND", "Unknown command"
                )
            else:
                try:
                    status, code, message = handler(parts)
                except (ValueError, IndexError) as error:
                    status, code, message = (
                        "REJECTED", "INVALID_ARGUMENT",
                        str(error)
                    )
                except sqlite3.Error as error:
                    status, code, message = (
                        "REJECTED", "DATABASE_ERROR",
                        str(error)
                    )
                except Exception as error:
                    status, code, message = (
                        "REJECTED", "PROCESSING_ERROR",
                        str(error)
                    )

            COMMAND_LOG.append({
                "line_no": line_no,
                "command": command,
                "entity_id": entity_id,
                "status": status,
                "error_code": code,
                "message": message
            })

            print(
                f"Line {line_no}: {command} -> {status}"
                + (f" ({code})" if code else "")
            )

    write_csv("invoices.csv", INVOICE_HEADERS, INVOICE_ROWS)
    write_csv("invoice_lines.csv", LINE_HEADERS, INVOICE_LINE_ROWS)
    write_csv("command_log.csv", LOG_HEADERS, COMMAND_LOG)
    write_csv("order_states.csv", STATE_HEADERS, generate_order_states())

    print("\nProcessing completed.")
    print("Commands logged:", len(COMMAND_LOG))
    print("Successful checkouts:", len(INVOICE_ROWS))
    print("Output folder:", OUTPUT_DIR)


if __name__ == "__main__":
    print("PS-002 ORDER, PROMOTION AND RETURNS ENGINE")
    ensure_extra_columns()
    process_commands()
