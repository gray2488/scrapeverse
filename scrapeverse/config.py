"""Configuration constants for ScrapeVerse."""



# ================================================================

# Bright Data Scraper Studio API endpoints
BRD_TRIGGER_URL = "https://api.brightdata.com/dca/trigger"
BRD_DATASET_URL = "https://api.brightdata.com/dca/dataset"

# Collector IDs are read from environment variables or Kaggle secrets.
# This keeps the submission clean with no hardcoded credentials.
COLLECTORS = {}
COLLECTORS_LOWER = {}

# HuggingFace Router API (OpenAI-compatible format)
HF_ROUTER_URL = "https://router.huggingface.co/v1/chat/completions"
HF_MODELS = [
    "Qwen/Qwen2.5-72B-Instruct",
    "Qwen/Qwen2.5-7B-Instruct",
    "mistralai/Mixtral-8x7B-Instruct-v0.1",
]

# Polling and retry configuration
POLL_INTERVAL = 5          # seconds between poll attempts
MAX_POLL_TIME = 300        # maximum seconds to wait for scraper results
MAX_RETRIES = 3           # retry attempts for API calls
RETRY_DELAY = 2           # base delay for exponential backoff
CONFIDENCE_THRESHOLD = 50  # minimum confidence score for self-healing

# Phase 1: HTML Sanitizer configuration
KEEP_ATTRS = {
    "id", "class", "itemprop", "itemtype",
    "aria-label", "role", "name", "type",
}
BLOCKED_DATA_ATTRS = {
    "data-src", "data-srcset", "data-lazy",
    "data-lazy-src", "data-original", "data-bg",
    "data-bgset", "data-thumb", "data-placeholder",
    "data-defer", "data-async", "data-href",
    "data-action", "data-event", "data-params",
    "data-config", "data-nonce",
}
UNWRAP_TAGS = {
    "b", "i", "strong", "em", "u", "small",
    "sup", "sub", "mark", "abbr", "cite", "q",
    "code", "kbd", "s", "del", "ins", "font",
}
SCHEMA_TARGET_KEYS = [
    "price", "lowPrice", "highPrice",
    "name", "description", "availability",
    "sku", "mpn", "gtin",
]
HIDDEN_CLASSES = {
    "hidden", "invisible", "sr-only",
    "visually-hidden", "display-none", "hide",
    "is-hidden", "hidden-element",
}

# Target schema for AI self-healing extraction
TARGET_SCHEMA = {
    "product_name": "String",
    "product_price": "Number",
    "availability_status": "String (In Stock / Out of Stock)",
}

# Optional: Playwright for JS-rendered page fetching
try:
    from playwright.sync_api import sync_playwright  # noqa: F401
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


# ================================================================
