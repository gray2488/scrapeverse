"""Phase 1a - HTML sanitisation for AI consumption."""

import json
import re

from bs4 import BeautifulSoup, Comment

from .config import BLOCKED_DATA_ATTRS, HIDDEN_CLASSES, KEEP_ATTRS, UNWRAP_TAGS

# ================================================================

def estimate_tokens(text):
    """Estimate token count from text length (rough: 4 chars per token)."""
    return len(text) // 4


def remove_empty_tags(soup):
    """Remove tags that have no text content and no children."""
    changed = True
    while changed:
        changed = False
        for tag in soup.find_all(True):
            if tag.name in ("img", "br", "hr", "input", "meta", "link"):
                continue
            text_content = tag.get_text(strip=True)
            has_children = tag.find(True) is not None
            if not text_content and not has_children:
                tag.decompose()
                changed = True
    return soup


def _has_structural_attrs(tag):
    """Check if a tag has attributes worth keeping."""
    for attr_name in tag.attrs:
        if attr_name in KEEP_ATTRS:
            return True
        if attr_name.startswith("data-") and attr_name not in BLOCKED_DATA_ATTRS:
            return True
    return False


def _has_hidden_class(tag):
    """Check if a tag has a hidden-related CSS class."""
    classes = tag.get("class", [])
    if not classes:
        return False
    for cls in classes:
        if cls.lower() in HIDDEN_CLASSES:
            return True
    return False


def extract_json_ld(soup):
    """
    Extract JSON-LD structured data from <script> tags.
    Returns a list of parsed JSON-LD objects.
    """
    json_ld_data = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            raw = script.string or script.get_text(strip=True)
            if raw:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    json_ld_data.extend(parsed)
                else:
                    json_ld_data.append(parsed)
        except (json.JSONDecodeError, TypeError):
            continue
    return json_ld_data


def sanitize_html_for_ai(html_content):
    """
    Phase 1 core: Sanitize raw HTML for AI consumption.
    Steps:
      0. Extract JSON-LD structured data
      1. Remove non-essential tags (scripts, styles, nav, etc.)
      2. Unwrap inline formatting tags (b, i, strong, etc.)
      3. Remove HTML comments
      4. Remove hidden elements (display:none, aria-hidden, etc.)
      5. Filter attributes (keep only structural ones)
      6. Remove empty tags
      7. Minify whitespace
    Returns: (cleaned_html_string, json_ld_data_list)
    """
    soup = BeautifulSoup(html_content, "html.parser")

    # Step 0: Extract JSON-LD before removing script tags
    json_ld_data = extract_json_ld(soup)

    # Step 1: Remove non-essential tags
    tags_to_remove = [
        "style", "noscript", "svg", "footer", "nav",
        "iframe", "head", "meta", "link", "aside",
        "header", "template", "form", "button", "canvas",
    ]
    for tag in soup(tags_to_remove):
        tag.decompose()

    # Remove script tags (but preserve JSON-LD content already extracted)
    for script in soup.find_all("script"):
        if script.get("type", "") != "application/ld+json":
            script.decompose()
        else:
            script.clear()

    # Step 2: Unwrap inline formatting tags without structural attrs
    for tag in soup.find_all(UNWRAP_TAGS):
        if not _has_structural_attrs(tag):
            tag.unwrap()

    # Step 3: Remove HTML comments
    for comment in soup.find_all(
        string=lambda t: isinstance(t, Comment)
    ):
        comment.extract()

    # Step 4: Remove hidden elements
    for hidden in soup.find_all(
        style=re.compile(
            r"display\s*:\s*none|visibility\s*:\s*hidden",
            re.IGNORECASE,
        )
    ):
        hidden.decompose()
    for hidden in soup.find_all(_has_hidden_class):
        hidden.decompose()
    for hidden in soup.find_all(attrs={"aria-hidden": "true"}):
        hidden.decompose()

    # Step 5: Filter attributes on all remaining tags
    for tag in soup.find_all(True):
        attrs_to_delete = []
        for attr_name in list(tag.attrs.keys()):
            if attr_name.startswith("data-"):
                if attr_name in BLOCKED_DATA_ATTRS:
                    attrs_to_delete.append(attr_name)
            elif attr_name not in KEEP_ATTRS:
                attrs_to_delete.append(attr_name)
        for attr in attrs_to_delete:
            del tag.attrs[attr]

    # Step 6: Remove empty tags (iterative)
    soup = remove_empty_tags(soup)

    # Step 7: Minify whitespace
    clean_html = str(soup)
    clean_html = re.sub(r"\n\s*\n", "\n", clean_html)
    clean_html = re.sub(r"[ \t]+", " ", clean_html)
    clean_html = clean_html.strip()

    return clean_html, json_ld_data
