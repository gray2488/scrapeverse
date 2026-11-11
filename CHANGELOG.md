# Changelog

## 1.0.0 — 2026-11-12

First public release. The hackathon submission was a single 1,754-line
`app.py`; this release splits it into a package, adds tests, and fixes two
defects found while doing so.

### Added
- `scrapeverse/` package: config, credentials, normalise, search_urls,
  brightdata, fetch, sanitizer, schema, healer, helpers, pipeline, ui.
- `tests/` — 14 tests covering the sanitiser, the poisoning detector and price
  parsing.
- `examples/check_page.py` — offline demo that runs with no API keys, plus two
  sample pages (honest and tampered).
- `LICENSE` (MIT), `requirements.txt`, `requirements-dev.txt`, `.env.example`,
  `.gitignore`.

### Fixed
- **Price parsing returned a fraction of the real price.** `parse_price()` used
  `re.sub(r"[^\d.]", "", s)`, which keeps the dot from the "Rs." prefix, so
  `"Rs. 1,299"` became `".1299"` and parsed as **0.1299** instead of 1299.0.
  Every rupee-formatted price in the app was wrong by a factor of 10,000. The
  function now strips currency words first and parses the last numeric group.
- **Collector IDs never resolved.** `_load_collectors()` rebound the
  `COLLECTORS` name inside `credentials`, while `normalise` and `pipeline` held
  the original empty dict imported from `config`. Platform keys could therefore
  never be matched. The registry is now mutated in place, so every importer sees
  the same object.

### Changed
- Streamlit is imported defensively in `credentials`, so the extraction core can
  be imported and tested without the UI dependency installed.
- Secrets are resolved environment-first, then Streamlit, then Kaggle, so the
  library behaves the same inside and outside a notebook.
