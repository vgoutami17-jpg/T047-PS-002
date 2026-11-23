
from calculate_discounts import calculate_discounts


def test_discount_precedence():
    items = [{
        "sku": "TEST001",
        "category": "Fashion",
        "selling_price": 3000,
        "quantity": 1,
        "is_sale_item": 0
    }]

    result = calculate_discounts(
        items,
        coupon_code="SAVE10",
        bank_name="HDFC",
        customer_tier="REGULAR"
    )

    assert result["success"] is True

    item = result["items"][0]

    assert item["category_discount"] == 300
    assert item["coupon_discount"] == 200
    assert item["bank_discount"] == 250
    assert item["final_amount"] == 2250


def test_coupon_minimum_after_category_discount():
    items = [{
        "sku": "TEST002",
        "category": "Fashion",
        "selling_price": 550,
        "quantity": 1,
        "is_sale_item": 0
    }]

    result = calculate_discounts(
        items,
        coupon_code="SAVE10"
    )

    assert result["success"] is False
    assert "Minimum coupon value" in result["message"]


def test_coupon_not_applied_to_sale_items():
    items = [{
        "sku": "TEST003",
        "category": "Fashion",
        "selling_price": 1000,
        "quantity": 1,
        "is_sale_item": 1
    }]

    result = calculate_discounts(
        items,
        coupon_code="SAVE10"
    )

    assert result["success"] is False
    assert "Minimum coupon value" in result["message"]

def test_total_discount_never_exceeds_70_percent():
    items = [{
        "sku": "TEST004",
        "category": "Fashion",
        "selling_price": 1000,
        "quantity": 1,
        "is_sale_item": 0
    }]

    result = calculate_discounts(
        items,
        coupon_code="SAVE10",
        customer_tier="REGULAR"
    )

    assert result["success"] is True

    item = result["items"][0]

    total_line_discount = (
        item["category_discount"]
        + item["coupon_discount"]
        + item["bank_discount"]
        + item["prime_discount"]
    )

    assert total_line_discount <= 700
