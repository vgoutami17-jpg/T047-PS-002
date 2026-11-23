
import sqlite3
from checkout import calculate_bogo_discounts


def create_test_connection():
    connection = sqlite3.connect(":memory:")

    connection.execute("""
        CREATE TABLE promotions (
            category TEXT,
            buy_quantity INTEGER,
            get_quantity INTEGER,
            promotion_type TEXT,
            is_active INTEGER
        )
    """)

    connection.execute("""
        INSERT INTO promotions
        VALUES ('Chocolates', 1, 1, 'BOGO', 1)
    """)

    return connection


def test_buy_one_get_one_free():
    connection = create_test_connection()

    try:
        cart_items = [
            ("CH001", 2, "Chocolate Bar", "Chocolates", 100.0, 5, 100, 0)
        ]

        discounted_items = [{
            "sku": "CH001",
            "final_amount": 200.0
        }]

        result = calculate_bogo_discounts(
            connection, cart_items, discounted_items
        )

        assert result["free_items"] == 1
        assert result["total_discount"] == 100.0
        assert discounted_items[0]["final_amount"] == 100.0

    finally:
        connection.close()


def test_cheapest_item_is_free():
    connection = create_test_connection()

    try:
        cart_items = [
            ("CH001", 1, "Chocolate A", "Chocolates", 100.0, 5, 100, 0),
            ("CH002", 1, "Chocolate B", "Chocolates", 50.0, 5, 100, 0)
        ]

        discounted_items = [
            {"sku": "CH001", "final_amount": 100.0},
            {"sku": "CH002", "final_amount": 50.0}
        ]

        result = calculate_bogo_discounts(
            connection, cart_items, discounted_items
        )

        assert result["free_items"] == 1
        assert result["total_discount"] == 50.0
        assert discounted_items[0]["final_amount"] == 100.0
        assert discounted_items[1]["final_amount"] == 0.0

    finally:
        connection.close()


def test_five_items_give_two_free_items():
    connection = create_test_connection()

    try:
        cart_items = [
            ("CH001", 5, "Chocolate Bar", "Chocolates", 100.0, 5, 100, 0)
        ]

        discounted_items = [{
            "sku": "CH001",
            "final_amount": 500.0
        }]

        result = calculate_bogo_discounts(
            connection, cart_items, discounted_items
        )

        assert result["free_items"] == 2
        assert result["total_discount"] == 200.0
        assert discounted_items[0]["final_amount"] == 300.0

    finally:
        connection.close()


def test_one_item_does_not_get_free_item():
    connection = create_test_connection()

    try:
        cart_items = [
            ("CH001", 1, "Chocolate Bar", "Chocolates", 100.0, 5, 100, 0)
        ]

        discounted_items = [{
            "sku": "CH001",
            "final_amount": 100.0
        }]

        result = calculate_bogo_discounts(
            connection, cart_items, discounted_items
        )

        assert result["free_items"] == 0
        assert result["total_discount"] == 0
        assert discounted_items[0]["final_amount"] == 100.0

    finally:
        connection.close()
