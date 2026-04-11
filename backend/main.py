"""
FoodFlow Support Bot — FastAPI Backend
======================================
Entry point for the backend.  Run with:
    uvicorn main:app --reload --port 8000

Routing priority for POST /api/chat:
  1. Order intent  → Firebase Firestore
  2. FAQ match     → faq_service
  3. AI fallback   → Gemini
"""

import os
import re
from typing import Any, Dict, List

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Load .env from the backend directory — works in any cwd or subprocess
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path=_env_path, override=True)
# Also try current directory as fallback
load_dotenv(override=False)

from models.schemas import ChatRequest, ChatResponse, FAQDebugResponse
from services import faq_service, firebase_service, gemini_service

# ─── App setup ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="FoodFlow Support Bot",
    description="AI-powered food delivery support chatbot API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Eagerly initialise Gemini and Firebase at startup."""
    key = os.getenv("GEMINI_API_KEY", "")
    print(f"[Startup] GEMINI_API_KEY present: {bool(key and key != 'your_gemini_api_key_here')}")
    # Trigger lazy init now so health check is accurate
    gemini_service.is_gemini_available()
    firebase_service.is_firebase_available()

# ─── Order intent keywords ────────────────────────────────────────────────────

_ACTIVE_ORDER_PATTERNS = [
    r"\btrack(ing)?\b",
    r"\bwhere.{0,10}(is|my) (my )?order\b",
    r"\border status\b",
    r"\bcurrent order\b",
    r"\bactive order\b",
    r"\blatest order\b",
    r"\bwhen.{0,15}(arrive|deliver|coming|reach)\b",
    r"\beta\b",
    r"\brider\b",
    r"\bdelivery (status|update|time)\b",
    r"\btransit\b",
    r"\bwho.{0,10}(rider|deliver|bring)\b",
    r"\bhow long.{0,10}(order|deliver|food)\b",
    r"\bmy order.{0,20}(late|slow|delay)\b",
]

_HISTORY_PATTERNS = [
    r"\bprevious order\b",
    r"\border history\b",
    r"\brecent order\b",
    r"\blast order\b",
    r"\bpast order\b",
    r"\bwhat did i order\b",
    r"\bmy orders\b",
    r"\border list\b",
    r"\bold order\b",
]


def _detect_order_intent(message: str) -> str:
    """
    Detect whether the user is asking about:
      - 'active'  → active / latest order status
      - 'history' → order history
      - None      → not an order query
    """
    msg_lower = message.lower().strip()
    for pattern in _ACTIVE_ORDER_PATTERNS:
        if re.search(pattern, msg_lower):
            return "active"
    for pattern in _HISTORY_PATTERNS:
        if re.search(pattern, msg_lower):
            return "history"
    return "none"


# ─── Helper: build structured responses ──────────────────────────────────────

def _order_status_response(order: Dict[str, Any]) -> ChatResponse:
    eta = order.get("estimated_arrival_minutes")
    eta_text = f"in approximately {eta} minutes" if eta else "soon"
    status = order.get("status", "Unknown")
    rider = order.get("rider_name")
    rider_text = f" Your rider is {rider}." if rider else ""
    message = (
        f"Your order from {order.get('restaurant_name', 'the restaurant')} "
        f"is currently **{status}**.{rider_text} "
        f"Expected arrival: {eta_text}."
    )
    return ChatResponse(
        type="order_status",
        source="firebase",
        message=message,
        data={
            "order_id": order.get("order_id"),
            "restaurant_name": order.get("restaurant_name"),
            "items": order.get("items", []),
            "status": status,
            "delivery_stage": order.get("delivery_stage"),
            "eta": eta,
            "rider_name": rider,
            "rider_phone": order.get("rider_phone"),
            "total_amount": order.get("total_amount"),
            "payment_method": order.get("payment_method"),
        },
    )


def _order_history_response(orders: List[Dict[str, Any]]) -> ChatResponse:
    return ChatResponse(
        type="order_history",
        source="firebase",
        message=f"Here are your {len(orders)} most recent orders.",
        data={"orders": orders},
    )


def _no_active_order_response() -> ChatResponse:
    return ChatResponse(
        type="order_status",
        source="firebase",
        message=(
            "You don't have any active orders right now. "
            "Your latest delivered order information is shown below, or try placing a new order!"
        ),
        data={"active": False},
    )


def _faq_response(match: Dict[str, Any]) -> ChatResponse:
    faq = match["faq"]
    return ChatResponse(
        type="faq",
        source="faq",
        message=faq["answer"],
        data={
            "matched_question": faq["question"],
            "category": faq.get("category"),
            "confidence": round(match["score"], 3),
        },
    )


def _gemini_response(text: str) -> ChatResponse:
    return ChatResponse(
        type="gemini",
        source="gemini",
        message=text,
        data={"fallback": True, "ai_assisted": True},
    )


def _error_response(msg: str) -> ChatResponse:
    return ChatResponse(
        type="error",
        source="error",
        message=msg,
        data={},
    )


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health_check():
    """Health check — returns service status."""
    return {
        "status": "ok",
        "service": "FoodFlow Support Bot",
        "firebase_available": firebase_service.is_firebase_available(),
        "gemini_available": gemini_service.is_gemini_available(),
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    Main chat endpoint.

    Routing order:
      1. Detect order intent → query Firebase
      2. FAQ matching
      3. Gemini fallback
    """
    message = req.message.strip()
    user_id = req.user_id.strip()

    if not message:
        return _error_response("Message cannot be empty.")

    # ── Step 1: Order intent detection ────────────────────────────────────────
    intent = _detect_order_intent(message)

    if intent == "active":
        order = firebase_service.get_active_order(user_id)
        if order:
            return _order_status_response(order)
        # Try latest order as fallback
        latest = firebase_service.get_latest_order(user_id)
        if latest:
            return _order_status_response(latest)
        # Firebase not configured or no orders found
        if firebase_service.is_firebase_available():
            return _no_active_order_response()
        # Firebase unavailable — fall through to FAQ/Gemini
        pass

    if intent == "history":
        orders = firebase_service.get_order_history(user_id)
        if orders:
            return _order_history_response(orders)
        if firebase_service.is_firebase_available():
            return ChatResponse(
                type="order_history",
                source="firebase",
                message="You don't have any past orders yet. Start ordering now!",
                data={"orders": []},
            )
        # Firebase unavailable — fall through

    # ── Step 2: FAQ matching ──────────────────────────────────────────────────
    faq_match = faq_service.match_faq(message)
    if faq_match:
        return _faq_response(faq_match)

    # ── Step 3: Gemini fallback ───────────────────────────────────────────────
    gemini_reply = gemini_service.ask_gemini(message)
    if gemini_reply:
        return _gemini_response(gemini_reply)

    # ── All paths exhausted ───────────────────────────────────────────────────
    return _error_response(
        "I'm sorry, I couldn't find an answer to your question. "
        "Please contact our support team directly for further assistance."
    )


@app.post("/api/seed-data")
async def seed_data():
    """Seed Firestore with realistic demo users and orders."""
    result = firebase_service.seed_demo_data()
    if not result.get("success"):
        raise HTTPException(status_code=503, detail=result.get("error", "Seed failed"))
    return result


@app.get("/api/orders/{user_id}")
async def get_orders(user_id: str):
    """Fetch all orders for a user."""
    orders = firebase_service.get_all_orders(user_id)
    return {"user_id": user_id, "orders": orders, "count": len(orders)}


@app.get("/api/orders/{user_id}/active")
async def get_active_order(user_id: str):
    """Fetch the active order for a user."""
    order = firebase_service.get_active_order(user_id)
    if not order:
        return {"user_id": user_id, "active_order": None, "message": "No active order found."}
    return {"user_id": user_id, "active_order": order}


@app.get("/api/debug/faq-match")
async def debug_faq_match(query: str):
    """Debug endpoint — shows matching scores for a query across all FAQs."""
    if not query:
        raise HTTPException(status_code=400, detail="'query' parameter is required.")
    return faq_service.debug_match(query)


# ─── Dev entrypoint ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
