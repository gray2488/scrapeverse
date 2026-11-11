"""Credential loading.

Resolution order for every secret is: environment variable, then Streamlit
secrets, then Kaggle secrets. Environment variables come first so the library
runs unchanged outside Streamlit and inside a plain container.

Streamlit is an optional dependency here. It is imported defensively so that
the extraction core can be imported and tested without it installed.
"""

import os

from .config import COLLECTORS, COLLECTORS_LOWER

try:  # pragma: no cover - only importable when running under Streamlit
    import streamlit as st
except ImportError:  # pragma: no cover
    st = None


def _secret(name, default=""):
    """Resolve one secret by name, in priority order."""
    value = os.environ.get(name, "")
    if value:
        return value

    if st is not None:
        try:
            return st.secrets[name]
        except Exception:
            pass

    try:
        from kaggle_secrets import UserSecretsClient

        return UserSecretsClient().get_secret(name)
    except Exception:
        pass

    return default


def _load_collectors():
    """Populate the collector registry from configuration.

    The registries are mutated in place rather than rebound. Rebinding would
    leave every module that did ``from .config import COLLECTORS`` holding the
    original empty dict, so platform keys would never resolve.
    """
    collectors = {}
    for platform, env_key in (
        ("Amazon", "AMAZON_COLLECTOR_ID"),
        ("Flipkart", "FLIPKART_COLLECTOR_ID"),
    ):
        collector_id = _secret(env_key)
        if collector_id:
            collectors[platform] = collector_id

    COLLECTORS.clear()
    COLLECTORS.update(collectors)
    COLLECTORS_LOWER.clear()
    COLLECTORS_LOWER.update({name.lower(): name for name in collectors})
    return COLLECTORS


def get_llm_token():
    """HuggingFace token used by the self-healing engine."""
    return _secret("HF_TOKEN")


def get_brd_api_key():
    """Bright Data API key used by the Scraper Studio client."""
    return _secret("BRD_API_KEY")
