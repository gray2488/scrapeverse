# ScrapeVerse

**A price extractor that does not trust the page.**

ScrapeVerse turns a product page into a small, AI-readable document, then checks
whether the structured data on that page actually matches what a human can see.
When the two disagree, it says so, and it re-extracts the fields with an LLM
instead of believing the markup.

Built for the *Into The Scrape-Verse* hackathon and released as a working
reference implementation.

---

## The problem

Three failures show up in almost every scraping pipeline that feeds an LLM:

1. **DOM overload.** A product page is 200-900 KB of markup wrapped around 400
   bytes of price. Sending it to a model burns the context window on navigation,
   footers and tracking scripts, and the model starts hallucinating fields.
2. **Silent breakage.** CSS selectors are the fragile part. A class rename
   upstream returns an empty string, the pipeline reports "no price", and nobody
   notices until a customer does.
3. **Schema poisoning.** Product pages carry JSON-LD so search engines can read
   them. Nothing forces that JSON-LD to be true. A page can declare a price of
   Rs. 399 in structured data while displaying Rs. 1,299 to the buyer — and a
   scraper that trusts JSON-LD will record the wrong number, confidently.

ScrapeVerse addresses all three, and treats the third as the important one.

---

## How it works

### Phase 1 — Sanitise, then cross-validate

`sanitize_html_for_ai()` reduces a page in seven passes: it lifts the JSON-LD
first (before the `&lt;script&gt;` tags are destroyed), drops non-content tags
(`script`, `style`, `nav`, `footer`, `form`, `iframe`, `svg`), unwraps inline
formatting, strips HTML comments, deletes hidden elements (`display:none`,
`visibility:hidden`, `aria-hidden`, and a list of hidden class names), filters
attributes down to a structural whitelist, removes empty tags iteratively, and
collapses whitespace.

On the bundled sample this takes a page from 941 characters to 191 — a **79.7 %
reduction**, or roughly 235 tokens down to 47.

`cross_validate_json_ld()` then takes every value in the JSON-LD and looks for it
in the *visible* text of the page. Values are normalised first, so `Rs. 1,299`,
`₹1,299.00` and `1299` all compare equal.

| Trust score | Verdict | Meaning |
|---|---|---|
| 75 – 100 | `TRUSTED` | Structured data matches what the page shows |
| 50 – 74 | `SUSPICIOUS` | Some declared fields are not visible |
| 0 – 49 | `POISONED` | Declared values contradict the page — do not trust |

### Phase 2 — Self-healing extraction

If a record is incomplete or the trust score is low, `self_healing_extract()`
asks an LLM (via the HuggingFace router) to pull the target schema out of the
*sanitised* HTML. The selectors the model proposes are then validated against
the actual DOM and given a confidence score; below the threshold the extraction
is retried rather than accepted.

### Phase 3 — Bright Data Scraper Studio

For marketplaces that block plain HTTP, the pipeline can trigger a Bright Data
collector and poll for the dataset. Collector IDs and the API key come from the
environment, never from the source.

---

## Architecture

```
                       ┌──────────────────────────┐
   user query ────────▶│  search_urls             │  LLM builds marketplace URLs
                       └────────────┬─────────────┘
                                    ▼
                       ┌──────────────────────────┐
                       │  brightdata / fetch      │  trigger + poll, or direct GET
                       └────────────┬─────────────┘
                                    ▼
              ┌─────────────────────────────────────────┐
              │  Phase 1                                │
              │    sanitizer.sanitize_html_for_ai()     │  HTML  ──▶  compact HTML
              │    schema.cross_validate_json_ld()      │  JSON-LD ──▶  trust score
              └────────────────────┬────────────────────┘
                                   ▼
              ┌─────────────────────────────────────────┐
              │  Phase 2  healer.self_healing_extract() │  LLM + selector validation
              └────────────────────┬────────────────────┘
                                   ▼
                       ┌──────────────────────────┐
                       │  helpers.normalize_…     │  prices, records, dedupe
                       └────────────┬─────────────┘
                                    ▼
                       ┌──────────────────────────┐
                       │  ui  (Streamlit, 2 steps)│  search grid ─▶ comparison
                       └──────────────────────────┘
```

---

## Quickstart

The sanitiser and the trust scorer need no API keys. This runs offline:

```bash
git clone https://github.com/gray2488/scrapeverse.git
cd scrapeverse
pip install -r requirements.txt

python examples/check_page.py
```

```
source            : sample_product.html
raw size          :     941 chars  (~   235 tokens)
sanitised size    :     191 chars  (~    47 tokens)
reduction         : 79.7%
JSON-LD blocks    : 1
trust score       : 50
verdict           : SUSPICIOUS
```

Now the same page with one number changed — the JSON-LD claims Rs. 399 while the
page displays Rs. 1,299:

```bash
python examples/check_page.py examples/sample_poisoned.html
```

```
trust score       : 25
verdict           : POISONED
```

The full Streamlit application needs credentials:

```bash
cp .env.example .env      # fill in HF_TOKEN, BRD_API_KEY and collector IDs
streamlit run app.py
```

---

## Configuration

| Variable | Required for | Purpose |
|---|---|---|
| `HF_TOKEN` | Phase 2 | HuggingFace router token for self-healing extraction |
| `BRD_API_KEY` | Phase 3 | Bright Data API key |
| `AMAZON_COLLECTOR_ID` | Phase 3 | Bright Data collector for Amazon |
| `FLIPKART_COLLECTOR_ID` | Phase 3 | Bright Data collector for Flipkart |

Secrets are resolved in this order: environment variable, Streamlit secrets,
Kaggle secrets. Environment variables come first so the library runs unchanged
in a container.

---

## Project layout

```
scrapeverse/
├── app.py                    Streamlit entry point
├── scrapeverse/
│   ├── config.py             constants, thresholds, whitelists
│   ├── credentials.py        secret resolution (env → Streamlit → Kaggle)
│   ├── normalise.py          platform key matching
│   ├── search_urls.py        LLM-generated marketplace URLs
│   ├── brightdata.py         Scraper Studio client (trigger + poll)
│   ├── fetch.py              HTTP / Playwright page fetching
│   ├── sanitizer.py          Phase 1a — HTML reduction
│   ├── schema.py             Phase 1b — JSON-LD poisoning detection
│   ├── healer.py             Phase 2 — AI self-healing extraction
│   ├── helpers.py            price parsing, record assembly
│   ├── pipeline.py           end-to-end search pipeline
│   └── ui.py                 Streamlit views
├── examples/
│   ├── check_page.py         offline demo, no keys required
│   ├── sample_product.html   honest page
│   └── sample_poisoned.html  same page, tampered JSON-LD
└── tests/
    ├── test_sanitizer.py
    └── test_prices.py
```

---

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

14 tests cover the sanitiser (noise removal, content retention, lazy-attribute
stripping, JSON-LD survival), the poisoning detector (trusted, suspicious,
poisoned, no-JSON-LD cases) and price parsing across rupee and dollar formats.

---

## Known limitations

Documented deliberately, because a scraper that hides its failure modes is worse
than one that lists them.

- **False positives on invisible fields.** `sku` and `availability` are often
  declared in JSON-LD but never rendered on the page. They count as mismatches
  and pull the score down, which is why the honest sample scores 50 rather than
  100. A weighted score that treats price-like fields as decisive and
  descriptive fields as advisory would remove this class of false positive.
- **Schema URLs never match visible text.** `availability` is usually a
  schema.org URL (`https://schema.org/InStock`), not the words "In Stock", so it
  can never be found in the DOM as written.
- **Phase 3 needs a paid Bright Data account.** Without a key the marketplace
  path is unavailable; the sanitise-and-score path still works on any HTML.
- **No JavaScript rendering by default.** Playwright is optional and only used
  when installed; client-rendered prices will otherwise come back empty.
- **English and Indian-market price formats.** `parse_price` handles `Rs.`,
  `INR`, `₹`, `$`, thousands separators and the `/‑` suffix. Other locales are
  untested.
- **The trust score is heuristic.** It measures agreement between two sources on
  the same page. It does not verify that either source is true.

---

## Licence

MIT. See [LICENSE](LICENSE).

Built by **Group of AI (GoA)**.
