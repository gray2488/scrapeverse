"""Streamlit rendering for both steps."""

import difflib
from datetime import datetime

import pandas as pd
import streamlit as st

from .helpers import format_price, is_valid_price

# ================================================================

# ================================================================

# ================================================================

def render_search_results(products, query):
    """
    Step 1: Display top 5 search results with Select buttons.
    Uses native Streamlit components only — no HTML.
    """
    st.subheader(f"Search Results for: {query}")
    st.write(f"Found {len(products)} products. Select one to compare.")
    st.markdown("---")

    if not products:
        st.warning("No products found. Try a different search term.")
        return

    for i, product in enumerate(products):
        try:
            with st.container():
                col_img, col_info, col_btn = st.columns([1, 3, 1])

                with col_img:
                    try:
                        if product.get("image_url"):
                            st.image(product["image_url"], width=100)
                        else:
                            st.write("No Image")
                    except Exception:
                        st.write("No Image")

                with col_info:
                    title = product["title"]
                    if len(title) > 70:
                        title = title[:70] + "..."
                    st.write(f"**{title}**")
                    st.write(f"Platform: {product['platform']}")

                    if is_valid_price(product["price_num"]):
                        st.metric(
                            label="Price",
                            value=format_price(product["price_num"]),
                        )
                    else:
                        st.metric(label="Price", value="N/A")

                    avail = product.get("availability", "N/A")
                    st.write(f"Availability: {avail}")

                    # Show healing badge if data was self-healed
                    if product.get("healing_status") == "healed":
                        conf = product.get("healing_confidence", 0)
                        st.caption(
                            f"Self-Healed | Confidence: {conf}%"
                        )

                with col_btn:
                    if st.button(
                        "Select & Compare",
                        key=f"select_btn_{i}",
                        type="primary",
                    ):
                        st.session_state["selected_product"] = product
                        st.session_state["current_step"] = "comparison"
                        st.rerun()

                st.markdown("---")

        except Exception as e:
            st.warning(f"Error displaying product {i+1}: {e}")


# ================================================================
def render_comparison_dashboard(selected_product, all_search_products):
    """
    Step 2: Deep comparison for the selected product.
    Shows side-by-side comparison across platforms with
    savings calculation, comparison table, and CSV export.
    """
    selected_title = selected_product.get("title", "Unknown")
    selected_platform = selected_product.get("platform", "Unknown")

    st.subheader(f"Deep Comparison: {selected_title[:60]}")
    st.write(f"Selected from: {selected_platform}")
    st.markdown("---")

    # Find matching products from other platforms via fuzzy title match
    comparison_products = [selected_product]

    for p in all_search_products:
        if p["platform"] == selected_platform:
            continue
        title_ratio = difflib.SequenceMatcher(
            None,
            selected_title.lower(),
            p["title"].lower(),
        ).ratio()
        if title_ratio > 0.5:
            comparison_products.append(p)

    num = len(comparison_products)
    if num == 0:
        st.warning("No comparison data available.")
        return

    try:
        cols = st.columns(num)

        # Find lowest valid price
        valid_prices = [
            p for p in comparison_products
            if is_valid_price(p.get("price_num"))
        ]
        lowest_price = (
            min(p["price_num"] for p in valid_prices)
            if valid_prices else None
        )
        lowest_platform = None
        if valid_prices:
            cheapest = min(valid_prices, key=lambda x: x["price_num"])
            lowest_platform = cheapest["platform"]

        for i, product in enumerate(comparison_products):
            with cols[i]:
                with st.container():
                    try:
                        platform = product.get("platform", "Unknown")
                        price_num = product.get("price_num")
                        avail = product.get("availability", "N/A")
                        avail_lower = avail.lower()
                        img_url = product.get("image_url")

                        is_cheapest = (
                            platform == lowest_platform
                            and is_valid_price(price_num)
                        )

                        if is_cheapest:
                            st.success(f"{platform} - CHEAPEST")
                        else:
                            st.write(f"**{platform}**")

                        try:
                            if img_url:
                                st.image(img_url, width=120)
                            else:
                                st.write("No Image")
                        except Exception:
                            st.write("No Image")

                        if is_valid_price(price_num):
                            st.metric(
                                label="Price",
                                value=format_price(price_num),
                            )
                        else:
                            st.metric(label="Price", value="N/A")

                        if any(w in avail_lower for w in ("in stock", "available")):
                            st.write("In Stock")
                        elif any(w in avail_lower for w in ("out of stock", "unavailable", "sold out")):
                            st.write("Out of Stock")
                        elif any(w in avail_lower for w in ("access denied", "blocked")):
                            st.write("Blocked")
                        else:
                            st.write(f"Status: {avail}")

                        # Show healing info on comparison cards
                        if product.get("healing_status") == "healed":
                            conf = product.get("healing_confidence", 0)
                            st.caption(f"Healed ({conf}%)")

                    except Exception as card_err:
                        st.warning(f"Card error: {card_err}")

    except Exception as grid_err:
        st.warning(f"Comparison grid error: {grid_err}")

    st.markdown("---")

    # Savings calculation
    try:
        if len(valid_prices) >= 2:
            sorted_prices = sorted(
                valid_prices, key=lambda x: x["price_num"]
            )
            cheapest = sorted_prices[0]
            expensive = sorted_prices[-1]
            diff = expensive["price_num"] - cheapest["price_num"]
            if diff > 0:
                pct = (diff / expensive["price_num"]) * 100
                st.success(
                    f"{cheapest['platform']} is cheaper by "
                    f"{format_price(diff)} ({pct:.1f}% savings)!"
                )
            else:
                st.info("All platforms have the same price.")
        elif len(valid_prices) == 1:
            st.warning("Only one platform returned valid price data.")
        else:
            st.error("No valid price data from any platform.")
    except Exception:
        st.warning("Savings calculation skipped.")

    st.markdown("---")

    # Comparison table
    try:
        st.subheader("Full Comparison Table")
        table_data = []
        for p in comparison_products:
            title = p.get("title", "N/A")
            if len(title) > 50:
                title = title[:50] + "..."
            row = {
                "Platform": p.get("platform", "?"),
                "Price": format_price(p.get("price_num")),
                "Availability": p.get("availability", "N/A"),
                "Title": title,
            }
            if p.get("healing_status") == "healed":
                row["Healed"] = f"Yes ({p.get('healing_confidence', 0)}%)"
            else:
                row["Healed"] = "No"
            table_data.append(row)
        table_df = pd.DataFrame(table_data)
        st.dataframe(table_df, use_container_width=True, hide_index=True)
    except Exception as table_err:
        st.warning(f"Table error: {table_err}")

    # CSV download
    try:
        csv_data = pd.DataFrame(comparison_products).to_csv(index=False)
        st.download_button(
            label="Download as CSV",
            data=csv_data,
            file_name=(
                f"comparison_"
                f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            ),
            mime="text/csv",
        )
    except Exception:
        st.write("CSV download unavailable.")

    st.markdown("---")

    # Self-healing summary
    try:
        healed_count = sum(
            1 for p in comparison_products
            if p.get("healing_status") == "healed"
        )
        if healed_count > 0:
            st.info(
                f"{healed_count} product(s) were self-healed by the "
                "AI engine. Incomplete scraper data was automatically "
                "repaired using Phase 1 (HTML Sanitizer) and "
                "Phase 2 (AI Self-Healing)."
            )
    except Exception:
        pass

    # Back button
    if st.button("Back to Search Results"):
        st.session_state["current_step"] = "search"
        st.session_state.pop("selected_product", None)
        st.rerun()

    st.caption(
        "ScrapeVerse Hackathon | Bright Data Scraper Studio + "
        "HuggingFace AI Self-Healing Engine"
    )


# ================================================================
