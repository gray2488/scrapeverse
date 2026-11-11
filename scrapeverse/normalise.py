"""Normalisation of platform keys and search URLs."""

import difflib

from .config import COLLECTORS, COLLECTORS_LOWER

# ================================================================

def normalize_platform_key(raw_key):
    """
    Case-insensitive and fuzzy key matching.
    Maps LLM output keys (e.g. 'amazon', 'AMAZON') to canonical
    platform names (e.g. 'Amazon') that exist in COLLECTORS.
    """
    if not raw_key or not isinstance(raw_key, str):
        return None
    key = raw_key.strip()
    if key in COLLECTORS:
        return key
    key_lower = key.lower()
    if key_lower in COLLECTORS_LOWER:
        return COLLECTORS_LOWER[key_lower]
    canonical_keys = list(COLLECTORS.keys())
    matches = difflib.get_close_matches(
        key_lower, [k.lower() for k in canonical_keys],
        n=1, cutoff=0.6,
    )
    if matches:
        for c in canonical_keys:
            if c.lower() == matches[0]:
                return c
    for c in canonical_keys:
        if c.lower() in key_lower or key_lower in c.lower():
            return c
    return None


def normalize_search_urls(raw_urls):
    """Normalize LLM output keys to match COLLECTORS dict."""
    if not raw_urls or not isinstance(raw_urls, dict):
        return {}
    normalized = {}
    for raw_key, url_value in raw_urls.items():
        canonical = normalize_platform_key(raw_key)
        if canonical:
            normalized[canonical] = url_value
    return normalized


# ================================================================
