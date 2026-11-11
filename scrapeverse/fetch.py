"""Page fetching with optional Playwright rendering."""

import requests

from .config import PLAYWRIGHT_AVAILABLE

if PLAYWRIGHT_AVAILABLE:
    from playwright.sync_api import sync_playwright

def fetch_page(url, use_js=True, timeout=10):
    """
    Fetch raw HTML from a URL. Uses Playwright if available
    for JavaScript-rendered pages, falls back to requests.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    if use_js and PLAYWRIGHT_AVAILABLE:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.set_extra_http_headers(headers)
                page.goto(
                    url, wait_until="networkidle",
                    timeout=timeout * 1000,
                )
                page.wait_for_timeout(2000)
                html = page.content()
                browser.close()
                return html, "playwright"
        except Exception:
            pass
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.text, "requests"
