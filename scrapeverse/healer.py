"""Phase 2 - AI self-healing extraction with selector validation."""

import json
import re
import time

import requests
from bs4 import BeautifulSoup

from .config import CONFIDENCE_THRESHOLD, HF_MODELS, HF_ROUTER_URL
from .credentials import get_llm_token

# ================================================================

def build_prompt(clean_html, target_schema, max_chars=3000,
                failed_selectors=None):
    """
    Build the AI extraction prompt. Includes instructions for
    generating self-healing CSS selectors for each field.
    """
    if len(clean_html) > max_chars:
        truncated = clean_html[:max_chars]
        last_close = truncated.rfind(">")
        if last_close > 0:
            truncated = truncated[:last_close + 1]
        clean_html = truncated

    prompt = (
        "You are an expert data engineer and web scraper. "
        "I will provide you with a sanitized HTML snippet "
        "and a Target Schema.\n\n"
        "Your mission is to extract the requested data points "
        "from the HTML.\n\n"
        "CRITICAL INSTRUCTION FOR SELF-HEALING:\n"
        "For every field you extract, you MUST also provide the "
        "EXACT structural CSS selector (using id, class, or "
        "data-* attributes) that can be used to find this element "
        "again in the DOM. Do not use fragile chained selectors "
        "like div > div > span; prefer robust attributes like "
        '[data-testid="price"] or .product-price.\n\n'
        f"Target Schema: {json.dumps(target_schema, indent=2)}\n\n"
        "Sanitized HTML:\n"
        f"```html\n{clean_html}\n```\n\n"
        "Return ONLY a valid JSON object matching this exact "
        "structure. No conversational text, no explanations, "
        "no markdown:\n"
        '{"extracted_data": {"field_name": "value"}, '
        '"self_healing_selectors": {"field_name": "css_selector_here"}}'
    )

    if failed_selectors:
        feedback = "\n\nIMPORTANT: SELF-HEALING RETRY\n"
        feedback += "Previous selectors FAILED:\n"
        for field, info in failed_selectors.items():
            feedback += (
                f"- {field}: '{info['selector']}' "
                f"-> {info['reason']}\n"
            )
        feedback += "\nGenerate NEW, DIFFERENT selectors."
        prompt += feedback

    return prompt


def extract_json_robust(text):
    """
    Robustly extract JSON from LLM text output.
    Tries markdown code blocks, bare JSON, and raw parsing.
    """
    match = re.search(r"```json\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    match = re.search(r"```\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        json_str = text[first_brace:last_brace + 1]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return None


def validate_selectors(result, clean_html):
    """
    Validate AI-generated CSS selectors against the HTML.
    Assigns confidence scores (high/medium/low) per field.
    """
    selectors = result.get("self_healing_selectors", {})
    if not selectors:
        result["selector_validation"] = {
            "validated": False,
            "reason": "No selectors provided",
        }
        result["confidence_score"] = 0
        return result

    soup = BeautifulSoup(clean_html, "html.parser")
    validation_report = {}

    for field, selector in selectors.items():
        if not selector:
            validation_report[field] = {
                "valid": False,
                "reason": "Empty selector",
                "confidence": "low",
            }
            continue
        try:
            elements = soup.select(selector)
            if elements:
                validation_report[field] = {
                    "valid": True,
                    "matches": len(elements),
                    "confidence": "high",
                }
            else:
                validation_report[field] = {
                    "valid": False,
                    "reason": "0 elements matched",
                    "confidence": "low",
                }
        except NotImplementedError:
            validation_report[field] = {
                "valid": None,
                "reason": "BS4 unsupported selector",
                "confidence": "medium",
            }
        except Exception as e:
            error_name = type(e).__name__
            validation_report[field] = {
                "valid": False,
                "reason": f"{error_name}: {e}",
                "confidence": "low",
            }

    result["selector_validation"] = validation_report

    total = len(validation_report)
    high_count = sum(
        1 for v in validation_report.values()
        if v.get("confidence") == "high"
    )
    medium_count = sum(
        1 for v in validation_report.values()
        if v.get("confidence") == "medium"
    )
    confidence_pct = (
        (high_count * 100 + medium_count * 50) / total
    ) if total > 0 else 0
    result["confidence_score"] = round(confidence_pct, 2)

    return result


def extract_data_with_ai(clean_html, target_schema, hf_token=None,
                        failed_selectors=None, is_retry=False):
    """
    Call HuggingFace Router API to extract structured data from HTML.
    Tries multiple models with retry logic.
    Returns validated result dict or None.
    """
    if hf_token is None:
        hf_token = get_llm_token()
        if not hf_token:
            return None

    headers = {
        "Authorization": f"Bearer {hf_token}",
        "Content-Type": "application/json",
    }

    user_prompt = build_prompt(
        clean_html, target_schema, failed_selectors=failed_selectors,
    )

    payload = {
        "model": None,
        "messages": [{"role": "user", "content": user_prompt}],
        "max_tokens": 1024,
        "temperature": 0.1 if not is_retry else 0.3,
        "stream": False,
    }

    for model_name in HF_MODELS:
        payload["model"] = model_name

        for attempt in range(3):
            try:
                response = requests.post(
                    HF_ROUTER_URL, headers=headers,
                    json=payload, timeout=60,
                )

                if response.status_code == 503:
                    wait_time = 20
                    try:
                        err = response.json()
                        wait_time = err.get("estimated_time", 20)
                    except Exception:
                        pass
                    time.sleep(wait_time)
                    continue

                if response.status_code == 429:
                    time.sleep(30)
                    continue

                if response.status_code == 400:
                    # Model not available, try next
                    break

                if response.status_code == 404:
                    break

                response.raise_for_status()

                ai_response = response.json()
                generated_text = ""

                if "choices" in ai_response and len(ai_response["choices"]) > 0:
                    message = ai_response["choices"][0].get("message", {})
                    generated_text = message.get("content", "").strip()
                elif isinstance(ai_response, list) and len(ai_response) > 0:
                    generated_text = (
                        ai_response[0].get("generated_text", "").strip()
                    )
                else:
                    generated_text = str(ai_response).strip()

                if not generated_text:
                    continue

                result = extract_json_robust(generated_text)

                if result is not None:
                    result = validate_selectors(result, clean_html)
                    return result

            except requests.exceptions.RequestException:
                time.sleep(5)

    return None


def self_healing_extract(clean_html, target_schema, hf_token=None,
                         max_retries=2):
    """
    Phase 2 core: Self-healing extraction with confidence-based retries.
    - First attempt: normal extraction
    - If confidence < threshold: retry with failed selector feedback
    - Up to max_retries retry attempts
    - Returns best result with full retry history.
    """
    retry_history = []
    best_result = None
    best_confidence = -1  # Start at -1 so confidence=0 is still captured

    for retry_num in range(max_retries + 1):
        is_retry = retry_num > 0
        failed_selectors = None

        if is_retry and best_result is not None:
            failed_selectors = {}
            for field, info in (
                best_result.get("selector_validation", {}).items()
            ):
                if info.get("confidence") == "low":
                    failed_selectors[field] = {
                        "selector": (
                            best_result.get(
                                "self_healing_selectors", {}
                            ).get(field, "unknown")
                        ),
                        "reason": info.get("reason", "unknown"),
                    }

        result = extract_data_with_ai(
            clean_html, target_schema, hf_token,
            failed_selectors=failed_selectors,
            is_retry=is_retry,
        )

        if result is None:
            retry_history.append({
                "attempt": retry_num + 1,
                "confidence": 0,
                "is_retry": is_retry,
                "failed_fields": (
                    list(failed_selectors.keys())
                    if failed_selectors else []
                ),
            })
            continue

        confidence = result.get("confidence_score", 0)

        retry_history.append({
            "attempt": retry_num + 1,
            "confidence": confidence,
            "is_retry": is_retry,
            "failed_fields": (
                list(failed_selectors.keys())
                if failed_selectors else []
            ),
        })

        if confidence >= best_confidence:
            best_result = result
            best_confidence = confidence

        if confidence >= CONFIDENCE_THRESHOLD:
            break

    if best_result is not None:
        best_result["retry_history"] = retry_history
        best_result["final_confidence"] = best_confidence

    return best_result


# ================================================================
