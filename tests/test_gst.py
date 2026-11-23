
from checkout import calculate_gst


def test_gst_12_percent():
    assert calculate_gst(160, 12) == 19.2


def test_gst_18_percent():
    assert calculate_gst(1000, 18) == 180.0


def test_zero_gst():
    assert calculate_gst(500, 0) == 0.0
