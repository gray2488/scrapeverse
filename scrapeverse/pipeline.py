"""The end-to-end search pipeline."""

import time

from .brightdata import fetch_results, trigger_collector
from .config import COLLECTORS
from .credentials import _load_collectors  # noqa: F401
from .helpers import is_valid_price, normalize_products_from_results
from .normalise import normalize_search_urls  # noqa: F401
from .search_urls import llm_generate_search_urls

# ================================================================

def run_search_pipeline(query, api_key, hf_token, progress_bar=None):
    """
    Step 1: Search all platforms, return merged list of products.
    For each platform:
      1. Generate search URL via LLM
      2. Trigger Bright Data collector
      3. Poll for results
      4. Normalize products (with self-healing if needed)
    """
    search_urls = llm_generate_search_urls(query)
    if not search_urls:
        return []

    all_products = []
    platforms = list(search_urls.keys())
    total = len(platforms)

    for i, platform in enumerate(platforms):
        collector_id = COLLECTORS.get(platform)
        if not collector_id:
            continue

        search_url = search_urls[platform]

        if progress_bar:
            progress_bar.progress(
                (i / total) if total > 0 else 0,
                text=f"Searching {platform}...",
            )

        # Trigger collector
        collection_id = trigger_collector(api_key, collector_id, search_url)
        if not collection_id:
            continue

        # Poll for results
        raw_results = fetch_results(api_key, collection_id)
        if not raw_results:
            continue

        # Normalize products (with self-healing if needed)
        products = normalize_products_from_results(
            platform, raw_results, hf_token,
        )
        all_products.extend(products)

        time.sleep(2)

    if progress_bar:
        progress_bar.progress(1.0, text="Search complete!")

    # Sort by price (valid prices first, ascending), unpriced last
    priced = [p for p in all_products if is_valid_price(p["price_num"])]
    unpriced = [p for p in all_products if not is_valid_price(p["price_num"])]
    priced.sort(key=lambda x: x["price_num"])

    return (priced + unpriced)[:5]


# ================================================================
