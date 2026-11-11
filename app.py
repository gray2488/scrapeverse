"""ScrapeVerse Streamlit entry point."""

import streamlit as st

from scrapeverse.config import COLLECTORS
from scrapeverse.credentials import (_load_collectors, get_brd_api_key,
                                     get_llm_token)
from scrapeverse.pipeline import run_search_pipeline
from scrapeverse.ui import render_comparison_dashboard, render_search_results


def main():
    """
    Main entry point. Manages the 2-step flow via st.session_state.
    Step 1: Search phase — user enters query, sees top 5 products.
    Step 2: Comparison phase — user selects a product, sees
            side-by-side price comparison with self-healing info.
    """
    st.set_page_config(
        page_title="ScrapeVerse Price Engine",
        page_icon="*",
        layout="wide",
    )

    # Load collector IDs from secrets/environment
    _load_collectors()

    st.title("ScrapeVerse Self-Healing Price Engine")
    st.write(
        "AI-powered multi-site price comparison with "
        "self-healing scrapers | Bright Data Scraper Studio"
    )
    st.markdown("---")

    # Initialize session state
    if "current_step" not in st.session_state:
        st.session_state["current_step"] = "search"
    if "search_products" not in st.session_state:
        st.session_state["search_products"] = []
    if "search_query" not in st.session_state:
        st.session_state["search_query"] = ""
    if "selected_product" not in st.session_state:
        st.session_state["selected_product"] = None

    # ============================================================
    #  STEP 1: SEARCH PHASE
    # ============================================================
    if st.session_state["current_step"] == "search":
        st.subheader("Search Any Product")
        user_query = st.text_input(
            "Enter product name:",
            placeholder=(
                "e.g., Sony WH-1000XM5, iPhone 13, "
                "Samsung Galaxy S24..."
            ),
        )

        if st.button("Search", type="primary"):
            if not user_query.strip():
                st.warning("Please enter a product name.")
            else:
                api_key = get_brd_api_key()
                hf_token = get_llm_token()

                if not api_key:
                    st.error("BRD_API_KEY not found in secrets.")
                elif not hf_token:
                    st.error("HF_TOKEN not found in secrets.")
                elif not COLLECTORS:
                    st.error(
                        "No collector IDs found. Set "
                        "AMAZON_COLLECTOR_ID and "
                        "FLIPKART_COLLECTOR_ID in secrets."
                    )
                else:
                    try:
                        progress_bar = st.progress(
                            0, text="Starting search..."
                        )

                        products = run_search_pipeline(
                            user_query.strip(), api_key,
                            hf_token, progress_bar,
                        )

                        st.session_state["search_products"] = products
                        st.session_state["search_query"] = user_query.strip()

                        if products:
                            st.success(f"Found {len(products)} products!")
                        else:
                            st.warning(
                                "No products found. "
                                "Try a different search term."
                            )

                    except Exception as e:
                        st.error(f"Search error: {e}")

        # Display search results if available
        if st.session_state["search_products"]:
            render_search_results(
                st.session_state["search_products"],
                st.session_state["search_query"],
            )

    # ============================================================
    #  STEP 2: COMPARISON PHASE
    # ============================================================
    elif st.session_state["current_step"] == "comparison":
        if st.session_state.get("selected_product"):
            render_comparison_dashboard(
                st.session_state["selected_product"],
                st.session_state.get("search_products", []),
            )
        else:
            st.session_state["current_step"] = "search"
            st.rerun()

    # Sidebar with info
    with st.sidebar:
        st.header("About")
        st.write("ScrapeVerse Self-Healing Price Engine")
        st.write("")
        st.write("**How it works:**")
        st.write("1. Enter product name")
        st.write("2. AI generates search URLs")
        st.write("3. Bright Data scrapes results")
        st.write("4. Self-healing fills missing data")
        st.write("5. Select a product")
        st.write("6. See price comparison")
        st.write("")
        st.write("**Configured Collectors:**")
        if COLLECTORS:
            for p, cid in COLLECTORS.items():
                st.write(f"- {p}")
        else:
            st.write("No collectors configured.")
        st.write("")
        st.write("**Secrets needed:**")
        st.write("- HF_TOKEN")
        st.write("- BRD_API_KEY")
        st.write("- AMAZON_COLLECTOR_ID")
        st.write("- FLIPKART_COLLECTOR_ID")


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()
