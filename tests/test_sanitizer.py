"""Tests for the HTML sanitiser and JSON-LD schema-poisoning detector."""

import json

from scrapeverse.sanitizer import sanitize_html_for_ai
from scrapeverse.schema import cross_validate_json_ld

PAGE = """
<html><head>
  <script type="application/ld+json">
  {"@context":"https://schema.org","@type":"Product",
   "name":"Wireless Mouse","offers":{"@type":"Offer","price":"1299"}}
  </script>
  <script>console.log('tracking')</script>
  <style>.x{color:red}</style>
</head>
<body>
  <nav>Home | Shop</nav>
  <div style="display:none">SECRET_PROMO_CODE</div>
  <div aria-hidden="true">hidden text</div>
  <h1 itemprop="name">Wireless Mouse</h1>
  <p>Price: <b>Rs. 1,299</b> <span data-lazy="x.jpg">in stock</span></p>
  <!-- tracking comment -->
  <footer>Copyright</footer>
</body></html>
"""


def test_sanitizer_strips_noise():
    clean, _ = sanitize_html_for_ai(PAGE)
    assert "<script" not in clean.lower()
    assert "<style" not in clean.lower()
    assert "<nav" not in clean.lower()
    assert "<footer" not in clean.lower()
    assert "SECRET_PROMO_CODE" not in clean
    assert "hidden text" not in clean
    assert "tracking comment" not in clean


def test_sanitizer_keeps_content():
    clean, _ = sanitize_html_for_ai(PAGE)
    assert "Wireless Mouse" in clean
    assert "1,299" in clean


def test_sanitizer_drops_lazy_attributes():
    clean, _ = sanitize_html_for_ai(PAGE)
    assert "data-lazy" not in clean


def test_sanitizer_extracts_json_ld():
    _, ld = sanitize_html_for_ai(PAGE)
    assert isinstance(ld, list) and ld, "JSON-LD should survive sanitisation"
    assert ld[0]["name"] == "Wireless Mouse"


def test_schema_trusted_when_price_visible():
    _, ld = sanitize_html_for_ai(PAGE)
    result = cross_validate_json_ld(ld, PAGE)
    assert result["status"].startswith("TRUSTED")
    assert result["trust_score"] >= 75


def test_schema_flags_mismatch_when_price_absent():
    """JSON-LD claims 999 while the page shows 1,299 -> not trusted."""
    tampered = PAGE.replace('"price":"1299"', '"price":"999"')
    _, ld = sanitize_html_for_ai(tampered)
    result = cross_validate_json_ld(ld, tampered)
    assert not result["status"].startswith("TRUSTED")
    assert result["trust_score"] < 75
    assert result["mismatches"], "a mismatch should be recorded"


def test_schema_poisoned_when_every_field_is_fake():
    """Name and price both absent from the visible page -> POISONED."""
    fake = PAGE.replace('"price":"1299"', '"price":"999"')
    fake = fake.replace('"name":"Wireless Mouse"', '"name":"Imaginary Product XZ"')
    fake = fake.replace("<h1 itemprop=\"name\">Wireless Mouse</h1>", "<h1>Some Other Thing</h1>")
    _, ld = sanitize_html_for_ai(fake)
    result = cross_validate_json_ld(ld, fake)
    assert result["status"].startswith("POISONED")
    assert result["trust_score"] < 50


def test_schema_no_json_ld():
    result = cross_validate_json_ld([], "<html><body>nothing</body></html>")
    assert result["status"] == "No JSON-LD found"
    assert result["trust_score"] == 100
