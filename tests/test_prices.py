"""Tests for price parsing and formatting helpers."""

import math

from scrapeverse.helpers import format_price, is_valid_price, parse_price


def test_parse_rupee_formats():
    assert parse_price("Rs. 1,299") == 1299.0
    assert parse_price("\u20b92,499.00") == 2499.0
    assert parse_price("1299/-") == 1299.0


def test_parse_dollar():
    assert parse_price("$19.99") == 19.99


def test_parse_numeric_passthrough():
    assert parse_price(1499) == 1499.0
    assert parse_price(1499.5) == 1499.5


def test_parse_rejects_junk():
    for junk in ("N/A", "None", "", "nan", "failed", "error", None):
        assert parse_price(junk) is None


def test_is_valid_price():
    assert is_valid_price(10) is True
    assert is_valid_price(10.5) is True
    assert is_valid_price(float("nan")) is False
    assert is_valid_price(float("inf")) is False
    assert is_valid_price(None) is False
    assert is_valid_price("1299") is False


def test_format_price():
    assert format_price(1299.0) == "Rs. 1,299"
    assert format_price(float("nan")) == "N/A"
