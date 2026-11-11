"""Phase 1b - JSON-LD extraction and schema-poisoning detection."""

import re

from bs4 import BeautifulSoup

from .config import SCHEMA_TARGET_KEYS

def find_values_by_key(obj, target_keys):
    """Recursively find all values matching target keys in a nested object."""
    results = []
    target_lower = {k.lower() for k in target_keys}

    def _recurse(current, path=""):
        if isinstance(current, dict):
            for key, value in current.items():
                if key.lower() in target_lower:
                    results.append((key, value))
                if isinstance(value, (dict, list)):
                    _recurse(value, f"{path}.{key}")
        elif isinstance(current, list):
            for i, item in enumerate(current):
                if isinstance(item, (dict, list)):
                    _recurse(item, f"{path}[{i}]")
    _recurse(obj)
    return results


def normalize_value(value):
    """Normalize a value for cross-validation comparison."""
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = re.sub(r"rs\.?\s*", "", text)
    text = re.sub(r"inr\s*", "", text)
    text = re.sub(r"[\u20b9$\u20ac\u00a3\u00a5]\s*", "", text)
    text = text.replace(",", "")
    text = re.sub(r"\.0+$", "", text)
    text = re.sub(r"/-+$", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_dom_text(dom_text):
    """Normalize DOM text for cross-validation."""
    text = dom_text.lower()
    text = re.sub(r"rs\.?\s*", "", text)
    text = re.sub(r"inr\s*", "", text)
    text = re.sub(r"[\u20b9$\u20ac\u00a3\u00a5]\s*", "", text)
    text = text.replace(",", "")
    text = re.sub(r"\.0+\b", "", text)
    text = re.sub(r"/-", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def cross_validate_json_ld(json_ld_data, dom_html):
    """
    Cross-validate JSON-LD values against visible DOM text.
    Detects schema poisoning where JSON-LD contains values
    that do not appear in the visible page content.
    Returns a dict with trust_score, status, and mismatches.
    """
    if not json_ld_data:
        return {
            "trust_score": 100,
            "status": "No JSON-LD found",
            "mismatches": [],
            "json_ld_items_found": 0,
            "fields_checked": 0,
        }

    soup = BeautifulSoup(dom_html, "html.parser")
    raw_dom_text = soup.get_text(separator=" ", strip=True)
    normalized_dom = normalize_dom_text(raw_dom_text)

    mismatches = []
    total_checked = 0

    for idx, item in enumerate(json_ld_data):
        if not isinstance(item, dict):
            continue
        found = find_values_by_key(item, SCHEMA_TARGET_KEYS)
        for field_name, field_value in found:
            total_checked += 1
            norm_val = normalize_value(field_value)
            if not norm_val:
                continue
            is_num = norm_val.replace(".", "", 1).isdigit()
            if is_num:
                pat = r"\b" + re.escape(norm_val) + r"\b"
                match = re.search(pat, normalized_dom) is not None
            else:
                match = norm_val in normalized_dom
            if not match:
                mismatches.append({
                    "json_ld_item": idx,
                    "field": field_name,
                    "json_ld_value": field_value,
                    "normalized_value": norm_val,
                    "reason": "Not in visible DOM",
                })

    if total_checked == 0:
        trust_score = 100
        status = "NO FIELDS FOUND"
    else:
        ratio = len(mismatches) / total_checked
        trust_score = max(0, int(100 * (1 - ratio)))
        if trust_score >= 75:
            status = "TRUSTED"
        elif trust_score >= 50:
            status = "SUSPICIOUS"
        else:
            status = "POISONED"

    return {
        "trust_score": trust_score,
        "status": status,
        "mismatches": mismatches,
        "json_ld_items_found": len(json_ld_data),
        "fields_checked": total_checked,
    }


# ================================================================
