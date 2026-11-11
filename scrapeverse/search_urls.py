"""LLM-generated marketplace search URLs."""

import json

import requests
import streamlit as st

from .config import HF_MODELS, HF_ROUTER_URL
from .credentials import get_llm_token
from .normalise import normalize_search_urls

# ================================================================

def llm_generate_search_urls(user_query):
    """
    Use HuggingFace LLM to convert a user query into platform
    search URLs. Returns a dict mapping platform names to URLs.
    """
    hf_token = get_llm_token()
    if not hf_token:
        st.error("HF_TOKEN not found. Add it to Kaggle Secrets.")
        return None

    prompt = (
        'You are a URL generator. Given a product search query, '
        "generate search URLs for Indian e-commerce sites.\n\n"
        "Rules:\n"
        "1. Amazon India: https://www.amazon.in/s?k=<query with + for spaces>\n"
        "2. Flipkart: https://www.flipkart.com/search?q=<query with + for spaces>\n\n"
        f'User query: "{user_query}"\n\n'
        'Return ONLY a JSON object with keys "amazon", "flipkart" '
        "and URL values. No extra text.\n\n"
        'Example:\n'
        'Input: "iPhone 13"\n'
        'Output: {"amazon": "https://www.amazon.in/s?k=iPhone+13", '
        '"flipkart": "https://www.flipkart.com/search?q=iPhone+13"}'
    )

    headers = {
        "Authorization": f"Bearer {hf_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": HF_MODELS[1],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 300,
    }

    try:
        response = requests.post(
            HF_ROUTER_URL, headers=headers, json=payload, timeout=30,
        )
        response.raise_for_status()
        ai_text = response.json()["choices"][0]["message"]["content"].strip()
        ai_text = ai_text.replace("```json", "").replace("```", "").strip()

        start = ai_text.find("{")
        end = ai_text.rfind("}") + 1

        if start >= 0 and end > start:
            raw_urls = json.loads(ai_text[start:end])
            normalized = normalize_search_urls(raw_urls)
            if normalized:
                return normalized
            st.error("No platforms matched configured collectors.")
            return None
        else:
            st.error("LLM did not return valid JSON.")
            return None
    except Exception as e:
        st.error(f"LLM API error: {e}")
        return None


# ================================================================
