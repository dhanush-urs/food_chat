"""
FAQ Service for FoodFlow Support Bot.

Implements a multi-strategy FAQ matching engine:
  1. Exact question match
  2. Alias match
  3. Keyword overlap scoring
  4. Confidence threshold gating

All matching is case-insensitive with punctuation normalization.
"""

import json
import re
import os
from typing import Optional, Dict, Any

# ─── Load FAQ data once at module level ───────────────────────────────────────
_FAQ_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "faq_data.json")
_faq_data: list = []

def _load_faq() -> list:
    """Load FAQ data from JSON file."""
    global _faq_data
    if _faq_data:
        return _faq_data
    try:
        with open(_FAQ_PATH, "r", encoding="utf-8") as f:
            _faq_data = json.load(f)
        print(f"[FAQ] Loaded {len(_faq_data)} FAQ entries.")
    except FileNotFoundError:
        print(f"[FAQ] WARNING: FAQ file not found at {_FAQ_PATH}")
        _faq_data = []
    except json.JSONDecodeError as e:
        print(f"[FAQ] ERROR: Failed to parse FAQ JSON — {e}")
        _faq_data = []
    return _faq_data


# ─── Text normalisation helpers ───────────────────────────────────────────────

def _normalise(text: str) -> str:
    """Lowercase and strip punctuation for consistent matching."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)   # remove punctuation
    text = re.sub(r"\s+", " ", text)        # collapse whitespace
    return text


def _tokenise(text: str) -> set:
    """Return a set of tokens, filtering out very short words."""
    return {
        w for w in text.split()
        if len(w) > 2  # ignore stop words like 'a', 'is', 'my'
    }


# ─── Public API ───────────────────────────────────────────────────────────────

CONFIDENCE_THRESHOLD = 0.35   # minimum score to return a match

def match_faq(query: str) -> Optional[Dict[str, Any]]:
    """
    Try to match `query` against the loaded FAQ database.

    Returns a dict with:
      - faq:       the matched FAQ dict
      - score:     float confidence [0, 1]
      - reason:    string describing why it matched
    Or None if no match exceeds the threshold.
    """
    faqs = _load_faq()
    if not faqs:
        return None

    norm_query = _normalise(query)
    query_tokens = _tokenise(norm_query)

    best: Optional[Dict[str, Any]] = None
    best_score: float = 0.0

    for faq in faqs:
        score, reason = _score_faq(faq, norm_query, query_tokens)
        if score > best_score:
            best_score = score
            best = {"faq": faq, "score": score, "reason": reason}

    if best and best_score >= CONFIDENCE_THRESHOLD:
        return best

    return None


def debug_match(query: str) -> Dict[str, Any]:
    """
    Return full debug information for a query, regardless of threshold.
    Used by /api/debug/faq-match endpoint.
    """
    faqs = _load_faq()
    norm_query = _normalise(query)
    query_tokens = _tokenise(norm_query)

    results = []
    for faq in faqs:
        score, reason = _score_faq(faq, norm_query, query_tokens)
        if score > 0:
            results.append({
                "id": faq["id"],
                "question": faq["question"],
                "category": faq["category"],
                "score": round(score, 3),
                "reason": reason,
            })

    results.sort(key=lambda r: r["score"], reverse=True)
    top = results[0] if results else None

    return {
        "query": query,
        "normalised_query": norm_query,
        "matched": top is not None and top["score"] >= CONFIDENCE_THRESHOLD,
        "threshold": CONFIDENCE_THRESHOLD,
        "top_match": top,
        "all_candidates": results[:10],  # return top-10 for debugging
    }


# ─── Internal scoring ─────────────────────────────────────────────────────────

def _score_faq(faq: dict, norm_query: str, query_tokens: set) -> tuple:
    """
    Compute a confidence score [0.0, 1.0] for a single FAQ entry.
    Returns (score, reason_string).
    """
    # 1. Exact question match (perfect score)
    norm_question = _normalise(faq.get("question", ""))
    if norm_query == norm_question:
        return 1.0, "exact_question_match"

    # 2. Question contains query verbatim
    if norm_query in norm_question or norm_question in norm_query:
        return 0.9, "substring_question_match"

    # 3. Alias match
    for alias in faq.get("aliases", []):
        norm_alias = _normalise(alias)
        if norm_query == norm_alias:
            return 0.95, "exact_alias_match"
        if norm_query in norm_alias or norm_alias in norm_query:
            return 0.85, "substring_alias_match"

    # 4. Keyword overlap scoring
    faq_keywords = set(faq.get("keywords", []))
    # also include tokens from the question and all aliases
    faq_question_tokens = _tokenise(_normalise(faq.get("question", "")))
    for alias in faq.get("aliases", []):
        faq_question_tokens |= _tokenise(_normalise(alias))

    combined_faq_tokens = faq_keywords | faq_question_tokens

    if not combined_faq_tokens or not query_tokens:
        return 0.0, "no_tokens"

    overlap = query_tokens & combined_faq_tokens
    if not overlap:
        return 0.0, "no_overlap"

    # Jaccard-style score weighted toward query (we want recall)
    recall = len(overlap) / len(query_tokens)
    precision = len(overlap) / len(combined_faq_tokens)
    f1 = (2 * precision * recall) / (precision + recall + 1e-9)

    # Cap keyword-only matches at 0.8 so exact/alias always win
    score = min(f1 * 1.2, 0.80)
    return score, f"keyword_overlap({', '.join(overlap)})"
