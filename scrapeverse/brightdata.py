"""Bright Data Scraper Studio API client (trigger + poll)."""

import json
import time

import requests

from .config import (BRD_DATASET_URL, BRD_TRIGGER_URL, MAX_POLL_TIME,
                     MAX_RETRIES, POLL_INTERVAL, RETRY_DELAY)

# ================================================================

def trigger_collector(api_key, collector_id, target_url):
    """
    Trigger a Scraper Studio collector for a given URL.
    Returns a collection_id string, or None on failure.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = [{"url": target_url}]
    params = {
        "collector": collector_id,
        "queue_next": 1,
        "override_incompatible_schema": 1,
    }

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(
                BRD_TRIGGER_URL, headers=headers, params=params,
                json=payload, timeout=30,
            )
            sc = response.status_code
            if sc == 200:
                data = response.json()
                if isinstance(data, dict):
                    cid = data.get("collection_id")
                    if cid:
                        return cid
                elif isinstance(data, list) and len(data) > 0:
                    cid = data[0].get("collection_id")
                    if cid:
                        return cid
                return None
            elif sc == 401:
                return None
            elif sc == 429:
                time.sleep(RETRY_DELAY * (2 ** attempt))
                continue
            elif sc >= 500:
                time.sleep(RETRY_DELAY * (2 ** attempt))
                continue
            else:
                return None
        except Exception:
            time.sleep(RETRY_DELAY * (2 ** attempt))
    return None


def fetch_results(api_key, collection_id):
    """
    Poll the Bright Data dataset endpoint until results are ready.
    Returns a list of result records, or None on failure/timeout.
    """
    headers = {"Authorization": f"Bearer {api_key}"}
    params = {"id": collection_id}
    elapsed = 0

    while elapsed < MAX_POLL_TIME:
        try:
            response = requests.get(
                BRD_DATASET_URL, headers=headers,
                params=params, timeout=30,
            )
            if response.status_code == 202:
                elapsed += POLL_INTERVAL
                time.sleep(POLL_INTERVAL)
                continue
            if response.status_code == 200:
                try:
                    data = response.json()
                except json.JSONDecodeError:
                    return None
                if isinstance(data, list):
                    return data if len(data) > 0 else None
                elif isinstance(data, dict):
                    status = data.get("status", "")
                    if status in ("building", "running", "queued"):
                        elapsed += POLL_INTERVAL
                        time.sleep(POLL_INTERVAL)
                        continue
                    return [data]
                return None
            if response.status_code == 404:
                return None
            if response.status_code >= 500:
                elapsed += POLL_INTERVAL
                time.sleep(POLL_INTERVAL)
                continue
            return None
        except Exception:
            elapsed += POLL_INTERVAL
            time.sleep(POLL_INTERVAL)
    return None


# ================================================================
