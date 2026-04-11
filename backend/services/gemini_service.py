"""
Gemini AI fallback service for FoodFlow Support Bot.

Uses the new google-genai SDK (google.genai).
Only called when:
  1. The query is NOT an order intent, AND
  2. FAQ matching confidence is below the threshold.
"""

import os
from typing import Optional

# ─── Lazy client initialisation ───────────────────────────────────────────────
_gemini_client = None
_model_name = "gemini-2.5-flash"

_SYSTEM_INSTRUCTION = (
    "You are a concise food delivery customer support assistant for FoodFlow. "
    "If the user asks for order-specific details that are unavailable or require real-time data, "
    "politely say that real-time order data is only available through linked order records. "
    "Keep all responses under 80 words. Be helpful, brief, and support-oriented. "
    "Do not make up order-specific information such as delivery times, rider names, or amounts."
)


def _get_client():
    """Lazily initialise the Gemini client using google-genai SDK."""
    global _gemini_client
    if _gemini_client is not None:
        return _gemini_client

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key or api_key == "your_gemini_api_key_here":
        print("[Gemini] No valid GEMINI_API_KEY found. AI fallback disabled.")
        return None

    try:
        from google import genai
        _gemini_client = genai.Client(api_key=api_key)
        print(f"[Gemini] Client ready using model '{_model_name}'.")
        return _gemini_client
    except Exception as exc:
        print(f"[Gemini] Initialisation error: {exc}")
        return None


def ask_gemini(user_message: str) -> Optional[str]:
    """
    Send a message to Gemini and return the response text.
    Returns None if Gemini is not configured or an error occurs.
    """
    client = _get_client()
    if client is None:
        return None

    try:
        from google.genai import types

        response = client.models.generate_content(
            model=_model_name,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_INSTRUCTION,
                max_output_tokens=200,
                temperature=0.4,
            ),
        )
        return response.text.strip() if response.text else None
    except Exception as exc:
        print(f"[Gemini] generate_content error: {exc}")
        return None


def is_gemini_available() -> bool:
    """Quick check: returns True if Gemini is configured and ready."""
    return _get_client() is not None
