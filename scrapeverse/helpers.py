"""Price parsing and product record helpers."""

import math
import re

import pandas as pd

from .config import TARGET_SCHEMA
from .fetch import fetch_page
from .healer import self_healing_extract
from .sanitizer import sanitize_html_for_ai
from .schema import cross_validate_json_ld

# ================================================================

def is_valid_price(val):
    """Check if a value is a valid numeric price (not NaN/Inf/None)."""
    if val is None:
        return False
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return False
    if isinstance(val, (int, float)):
        return True
    return False


def parse_price(val):
    """Parse a price value from string/number, return float or None."""
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    if val is None:
        return None
    s = str(val).strip()
    if s.lower() in ("n/a", "none", "null", "", "nan", "failed", "error"):
        return None

    # Strip currency words first. Without this, "Rs. 1,299" loses the "s" and
    # the space but keeps the dot from "Rs.", leaving ".1299" -> 0.1299.
    s = re.sub(r"(?i)\b(?:rs|inr|usd|eur|gbp)\b\.?", " ", s)

    # Take the last number-like group: handles "1,299", "19.99", "1299/-".
    groups = re.findall(r"\d[\d,]*\.?\d*", s)
    if not groups:
        return None
    cleaned = groups[-1].replace(",", "")
    if not cleaned or cleaned == ".":
        return None
    try:
        r = float(cleaned)
        if math.isnan(r) or math.isinf(r):
            return None
        return r
    except (ValueError, TypeError):
        return None


def format_price(val):
    """Format a price value for display."""
    if not is_valid_price(val):
        return "N/A"
    return f"Rs. {val:,.0f}"


def find_value(data, keys, default="N/A"):
    """
    Search for a value in a dict using multiple possible key names.
    Also searches one level deep into nested dicts.
    """
    for key in keys:
        if key in data and data[key] is not None:
            val = str(data[key]).strip()
            if val and val.lower() not in ("none", "null", "", "nan"):
                return val
    for pv in data.values():
        if isinstance(pv, dict):
            for key in keys:
                if key in pv and pv[key] is not None:
                    val = str(pv[key]).strip()
                    if val and val.lower() not in ("none", "null", "", "nan"):
                        return val
    return default


def needs_healing(raw_record):
    """
    Check if a scraper result record has missing or empty
    critical fields. If so, the self-healing engine should
    be triggered to fill in the gaps.
    """
    title_keys = ["title", "product_title", "name", "product_name",
                  "Title", "Product_Title", "productTitle"]
    price_keys = ["price", "product_price", "Price", "Product_Price",
                  "discounted_price", "sale_price", "final_price",
                  "selling_price", "offer_price", "deal_price", "amount"]
    avail_keys = ["availability", "availability_status", "stock",
                  "Availability", "in_stock", "stock_status"]

    title = find_value(raw_record, title_keys, default="")
    price = find_value(raw_record, price_keys, default="")
    avail = find_value(raw_record, avail_keys, default="")

    if not title or title == "N/A":
        return True
    if not price or price == "N/A":
        return True
    if not avail or avail == "N/A":
        return True
    return False


def heal_product_data(raw_record, product_url, hf_token):
    """
    Trigger the self-healing pipeline for a product with incomplete data.
    1. Fetch the product page HTML
    2. Sanitize HTML (Phase 1)
    3. Cross-validate JSON-LD (Phase 1)
    4. AI self-healing extraction (Phase 2)
    5. Merge healed data back into the record
    Returns updated record dict.
    """
    if not product_url:
        return raw_record

    try:
        html_content, method = fetch_page(product_url, use_js=True)
    except Exception:
        return raw_record

    try:
        cleaned_html, json_ld_data = sanitize_html_for_ai(html_content)
    except Exception:
        return raw_record

    try:
        validation = cross_validate_json_ld(json_ld_data, cleaned_html)
    except Exception:
        validation = {"status": "error", "trust_score": 0}

    try:
        ai_result = self_healing_extract(
            cleaned_html, TARGET_SCHEMA, hf_token, max_retries=2,
        )
    except Exception:
        ai_result = None

    if ai_result and ai_result.get("extracted_data"):
        extracted = ai_result["extracted_data"]

        title_keys = ["title", "product_title", "name", "product_name",
                      "Title", "Product_Title", "productTitle"]
        price_keys = ["price", "product_price", "Price", "Product_Price",
                      "discounted_price", "sale_price", "final_price",
                      "selling_price", "offer_price", "deal_price", "amount"]
        avail_keys = ["availability", "availability_status", "stock",
                      "Availability", "in_stock", "stock_status"]

        # Only fill in missing fields
        existing_title = find_value(raw_record, title_keys, default="")
        if not existing_title or existing_title == "N/A":
            healed_title = extracted.get("product_name", "")
            if healed_title:
                raw_record["_healed_title"] = healed_title

        existing_price = find_value(raw_record, price_keys, default="")
        if not existing_price or existing_price == "N/A":
            healed_price = extracted.get("product_price", "")
            if healed_price:
                raw_record["_healed_price"] = healed_price

        existing_avail = find_value(raw_record, avail_keys, default="")
        if not existing_avail or existing_avail == "N/A":
            healed_avail = extracted.get("availability_status", "")
            if healed_avail:
                raw_record["_healed_availability"] = healed_avail

        raw_record["_healing_confidence"] = ai_result.get(
            "final_confidence", 0
        )
        raw_record["_healing_status"] = "healed"
        raw_record["_trust_score"] = validation.get("trust_score", 0)
        raw_record["_trust_status"] = validation.get("status", "unknown")

    return raw_record


def normalize_products_from_results(platform, raw_results, hf_token=None):
    """
    Parse a list of products from scraper results.
    For each product, check if fields are missing. If missing,
    trigger the self-healing pipeline to fill in gaps.
    Returns a list of clean product dicts.
    """
    if not raw_results:
        return []

    if isinstance(raw_results, dict):
        raw_results = [raw_results]
    elif not isinstance(raw_results, list):
        return []

    title_keys = ["title", "product_title", "name", "product_name",
                  "Title", "Product_Title", "productTitle"]
    price_keys = ["price", "product_price", "Price", "Product_Price",
                  "discounted_price", "sale_price", "final_price",
                  "selling_price", "offer_price", "deal_price", "amount"]
    avail_keys = ["availability", "availability_status", "stock",
                  "Availability", "in_stock", "stock_status"]
    url_keys = ["url", "product_url", "link", "product_link",
                "input_url", "source_url"]
    image_keys = ["product_image_url", "image_url", "image", "img_url",
                  "product_image", "Image_URL", "productImage",
                  "thumbnail", "photo", "picture_url"]

    products = []
    for raw in raw_results:
        if not isinstance(raw, dict):
            continue

        # Check if self-healing is needed
        should_heal = needs_healing(raw)
        if should_heal and hf_token:
            product_url_val = find_value(raw, url_keys, default="")
            if product_url_val and product_url_val != "N/A":
                raw = heal_product_data(raw, product_url_val, hf_token)

        # Extract title (check healed fields first)
        title = raw.get("_healed_title") or find_value(raw, title_keys)
        if title == "N/A" or not title:
            continue

        # Extract price (check healed fields first)
        price_raw = raw.get("_healed_price") or find_value(
            raw, price_keys, default=""
        )
        price_num = parse_price(price_raw)

        # Extract availability (check healed fields first)
        availability = raw.get("_healed_availability") or find_value(
            raw, avail_keys
        )

        product_url = find_value(raw, url_keys, default="")
        image_url = find_value(raw, image_keys, default="")

        if image_url == "" or image_url == "N/A":
            image_url = None
        if product_url == "" or product_url == "N/A":
            product_url = None

        products.append({
            "platform": platform,
            "title": str(title)[:200],
            "price_num": price_num,
            "price_str": format_price(price_num),
            "availability": (
                str(availability).strip()
                if availability and availability != "N/A"
                else "N/A"
            ),
            "product_url": product_url,
            "image_url": image_url,
            "healing_confidence": raw.get("_healing_confidence", None),
            "healing_status": raw.get("_healing_status", "direct"),
            "trust_score": raw.get("_trust_score", None),
            "trust_status": raw.get("_trust_status", None),
        })

    return products


# ================================================================
