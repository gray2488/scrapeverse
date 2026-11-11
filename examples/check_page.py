"""Offline demo: sanitise a page and score its JSON-LD trust.

Run with no arguments to use the bundled sample, or pass a URL to try a live
page (network required):

    python examples/check_page.py
    python examples/check_page.py examples/sample_poisoned.html
    python examples/check_page.py https://example.com/product
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scrapeverse.sanitizer import estimate_tokens, sanitize_html_for_ai
from scrapeverse.schema import cross_validate_json_ld

SAMPLE = Path(__file__).parent / "sample_product.html"


def main() -> None:
    target = sys.argv[1] if len(sys.argv) > 1 else None
    if target and target.startswith(("http://", "https://")):
        from scrapeverse.fetch import fetch_page

        html, source = fetch_page(target), target
    elif target:
        path = Path(target)
        html, source = path.read_text(encoding="utf-8"), path.name
    else:
        html, source = SAMPLE.read_text(encoding="utf-8"), SAMPLE.name

    clean, json_ld = sanitize_html_for_ai(html)
    trust = cross_validate_json_ld(json_ld, html)

    print(f"source            : {source}")
    print(f"raw size          : {len(html):>7} chars  (~{estimate_tokens(html):>6} tokens)")
    print(f"sanitised size    : {len(clean):>7} chars  (~{estimate_tokens(clean):>6} tokens)")
    print(f"reduction         : {100 * (1 - len(clean) / len(html)):.1f}%")
    print(f"JSON-LD blocks    : {len(json_ld)}")
    print(f"trust score       : {trust['trust_score']}")
    print(f"verdict           : {trust['status']}")
    print(f"fields checked    : {trust['fields_checked']}")
    for mismatch in trust["mismatches"][:5]:
        print(f"  mismatch        : {mismatch}")
    print("\n--- first 400 characters of the sanitised page ---")
    print(clean[:400])


if __name__ == "__main__":
    main()
