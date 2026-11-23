
from checkout import calculate_shipping


def test_prime_free_shipping():
    assert calculate_shipping(300, 3000, "PRIME", "Karnataka") == 0


def test_regular_shipping_below_499():
    assert calculate_shipping(300, 1000, "REGULAR", "Karnataka") == 49


def test_regular_free_shipping_above_499():
    assert calculate_shipping(500, 1000, "REGULAR", "Karnataka") == 0


def test_north_east_shipping():
    assert calculate_shipping(300, 1000, "REGULAR", "Assam") == 149

