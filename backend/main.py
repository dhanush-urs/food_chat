"""
FoodFlow Support Bot — FastAPI Backend
======================================
"""

import os
import re
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path=_env_path, override=True)
load_dotenv(override=False)

from models.schemas import ChatRequest, ChatResponse, CreateOrderRequest, FAQDebugResponse
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

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    details = ", ".join([f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in errors])
    resp = _build_response("error", "backend", "Unable to create order. Please check the order details and try again.", {
        "error_code": "ORDER_CREATE_FAILED",
        "details": details
    })
    return JSONResponse(status_code=400, content=resp.dict())

@app.on_event("startup")
async def startup_event():
    key = os.getenv("GEMINI_API_KEY", "")
    print(f"[Startup] GEMINI_API_KEY present: {bool(key and key != 'your_gemini_api_key_here')}")
    gemini_service.is_gemini_available()
    firebase_service.is_firebase_available()


# ─── Intent patterns ──────────────────────────────────────────────────────────

_ACTIVE_ORDER_PATTERNS = [
    r"\btrack(ing)?\b", r"\bwhere.{0,10}(is|my) (my )?order\b", r"\border status\b",
    r"\bcurrent order\b", r"\bactive order\b", r"\blatest order\b",
    r"\bwhen.{0,15}(arrive|deliver|coming|reach)\b", r"\beta\b", r"\bdelivery (status|update|time)\b",
    r"\btransit\b", r"\bhow long.{0,10}(order|deliver|food)\b", r"\bmy order.{0,20}(late|slow|delay)\b",
]

_HISTORY_PATTERNS = [
    r"\bprevious order(s)?\b", r"\border history\b", r"\brecent order(s)?\b", r"\blast order(s)?\b", 
    r"\bpast order(s)?\b", r"\bmy order(s)?\b", r"\border list\b", r"\bold order(s)?\b",
    r"\blast \d+ order(s)?\b", r"\bwhat did i order\b", r"\bwhat are my\b.*\border(s)?\b"
]

_ORDER_ITEMS_PATTERNS = [
    r"\bwhat item(s)? did i order\b", r"\bshow item(s)? from (my )?(last|previous) order\b",
    r"\bwhat food did i order\b", r"\bshow ordered item(s)?\b",
    r"\bwhat was in my (last|previous) order\b", r"\brecently ordered item(s)?\b"
]

_OPERATIONAL_PATTERNS = {
    "create_order": [r"\b(place|create|add|new) order\b", r"\border food\b", r"\bplace an order\b"],
    "cancel_order": [r"\bcancel( my)? order\b", r"\bcancel it\b"],
    "refund_request": [r"\b(request|want).{0,10}refund\b", r"\brefund my\b", r"\bget a refund\b"],
    "refund_status": [r"\brefund status\b", r"\bwhere is my refund\b"],
    "address_change": [r"\b(change|update).{0,10}address\b"],
    "rider_info": [r"\bwho.{0,10}(rider|deliver|bring)\b", r"\brider details\b", r"\bcall( my)? rider\b", r"\bcontact rider\b"],
    "reorder_last": [r"\breorder\b", r"\border same\b", r"\brepeat.+order\b"],
    "support_ticket_missing": [r"\bmissing\b(?!.+refund)"],
    "support_ticket_wrong": [r"\bwrong\b"],
    "support_ticket_damaged": [r"\bdamaged\b", r"\bspill\b", r"\bbroken\b"],
    "coupon": [r"\bcoupon\b", r"\bpromo\b", r"\bdiscount code\b"],
    "delivery_estimate": [r"\bdelivery (charge|fee|cost|estimate)\b", r"\bhow much is delivery\b"]
}

_FRUSTRATION_PATTERNS = [
    r"\b(angry|furious|mad)\b", r"\b(terrible|worst|awful|horrible|sucks)\b",
    r"\b(hate|disgusting|pathetic)\b", r"\b(wtf|bs|bullshit|trash|garbage)\b",
    r"\b(stupid|idiot|dumb|useless)\b",
]

def _normalize_message(text: str) -> str:
    """Strip punctuation and extra spaces for more robust intent matching."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def _detect_frustration(message: str) -> bool:
    msg = _normalize_message(message)
    return any(re.search(p, msg) for p in _FRUSTRATION_PATTERNS)

def _detect_operational_intent(message: str) -> str:
    msg = _normalize_message(message)
    for intent, patterns in _OPERATIONAL_PATTERNS.items():
        if any(re.search(p, msg) for p in patterns):
            return intent
    return "none"

def _is_order_history_intent(message: str) -> bool:
    """Strong detection for general order history queries."""
    msg = _normalize_message(message)
    # Check regex patterns
    if any(re.search(p, msg) for p in _HISTORY_PATTERNS):
        return True
    
    # Keyword-based strong signals
    tokens = set(msg.split())
    if "orders" in tokens or "order" in tokens:
        if any(w in tokens for w in ["previous", "past", "history", "recent", "last", "before"]):
            return True
            
    return False

def _is_ordered_items_history_intent(message: str) -> bool:
    """Strong detection for item-specific history queries."""
    msg = _normalize_message(message)
    if any(re.search(p, msg) for p in _ORDER_ITEMS_PATTERNS):
        return True
    
    # Keyword-based strong signals
    tokens = set(msg.split())
    if ("items" in tokens or "food" in tokens or "item" in tokens) and ("order" in tokens or "ordered" in tokens):
        if any(w in tokens for w in ["last", "previous", "recent", "recently", "what"]):
            return True
            
    return False

def _detect_order_intent(message: str) -> str:
    msg = _normalize_message(message)
    
    # 1. Active orders priority
    for pattern in _ACTIVE_ORDER_PATTERNS:
        if re.search(pattern, msg): return "active"
        
    # 2. History priority (items vs general)
    if _is_ordered_items_history_intent(message):
        return "items_history"
        
    if _is_order_history_intent(message):
        return "history"

    return "none"


# ─── Data Helpers ─────────────────────────────────────────────────────────────

_COUPONS = {
    "SAVE50": {"type": "flat", "discount": 50, "min_order": 200},
    "FREESHIP": {"type": "free_delivery", "discount": 0, "min_order": 150},
    "WELCOME": {"type": "percentage", "discount": 20, "max_discount": 100, "min_order": 100}
}


# ─── Response Builders ────────────────────────────────────────────────────────

def _build_response(resp_type: str, source: str, message: str, data: Dict[str, Any] = None) -> ChatResponse:
    return ChatResponse(type=resp_type, source=source, message=message, data=data or {})

# ─── Operational Handlers ─────────────────────────────────────────────────────

def handle_operational(intent: str, user_id: str, message: str) -> Optional[ChatResponse]:
    if not firebase_service.is_firebase_available():
        return None

    if intent == "create_order":
        active = firebase_service.get_active_order(user_id)
        if active:
            return _build_response("error", "firebase", "You already have an active order. Please wait for it to be delivered or cancel it first.")
        new_order = {
            "user_id": user_id,
            "restaurant_name": "Pizza Point (Demo)",
            "items": [
                {"name": "Margherita Pizza", "quantity": 1, "unit_price": 299.0},
                {"name": "Garlic Bread", "quantity": 2, "unit_price": 99.0}
            ],
            "payment_method": "UPI",
            "status": "Preparing",
            "delivery_stage": "Restaurant is preparing your order",
            "estimated_arrival_minutes": 30,
            "delivery_address": "Default Saved Address",
            "is_active": True
        }
        res = firebase_service.create_order(new_order)
        if res["success"]:
            return _build_response("order_created", "firebase", "Your order has been placed successfully!", res["order"])
        return None

    elif intent == "cancel_order":
        order = firebase_service.get_active_order(user_id)
        if not order:
            return _build_response("error", "firebase", "You have no active orders to cancel.")
        if order.get("status") in ["Picked up", "On the way", "Delivered"]:
            return _build_response("error", "firebase", f"Your order cannot be cancelled as it's already {order.get('status').lower()}.")
        firebase_service.update_order(order["order_id"], {
            "status": "Cancelled",
            "delivery_stage": "Order cancelled",
            "is_active": False
        })
        order["status"] = "Cancelled"
        order["delivery_stage"] = "Order cancelled"
        order["is_active"] = False
        return _build_response("order_cancelled", "firebase", "Your order has been cancelled successfully.", order)

    elif intent == "refund_request":
        last = firebase_service.get_latest_order(user_id)
        if not last:
            return _build_response("error", "firebase", "No recent orders found for a refund.")
        if last.get("status") not in ["Cancelled"]:
            return _build_response("error", "firebase", "Refunds are only automatically triggered for Cancelled orders. Please open a support ticket for other issues.")
        if last.get("refund_status"):
            return _build_response("error", "firebase", "A refund request already exists for this order.")
        
        firebase_service.update_order(last["order_id"], {"refund_status": "Requested", "refund_amount": last["total_amount"], "refund_eta_days": 3})
        last["refund_status"] = "Requested"
        last["refund_amount"] = last["total_amount"]
        return _build_response("refund_requested", "firebase", "Refund has been requested successfully.", last)

    elif intent == "refund_status":
        last = firebase_service.get_latest_order(user_id)
        if not last or not last.get("refund_status"):
            return _build_response("error", "firebase", "You don't have any recent refund requests.")
        return _build_response("refund_status", "firebase", f"Your refund is currently: {last.get('refund_status')}.", last)

    elif intent == "address_change":
        order = firebase_service.get_active_order(user_id)
        if not order:
            return _build_response("error", "firebase", "No active order to change address for.")
        if order.get("status") in ["Picked up", "On the way"]:
            return _build_response("error", "firebase", "Too late to change address. The rider is already on the way.")
        new_address = "Updated Location (Demo)"
        firebase_service.update_order(order["order_id"], {"delivery_address": new_address})
        order["delivery_address"] = new_address
        return _build_response("address_updated", "firebase", f"Your delivery address has been updated to {new_address}.", order)

    elif intent == "rider_info":
        order = firebase_service.get_active_order(user_id)
        if not order or not order.get("rider_name"):
            return _build_response("error", "firebase", "No rider has been assigned to your order yet.")
        return _build_response("rider_info", "firebase", f"Your rider is {order['rider_name']}.", order)

    elif intent == "reorder_last":
        history = firebase_service.get_order_history(user_id, limit=5)
        delivered = [o for o in history if o.get("status") == "Delivered"]
        if not delivered:
            return _build_response("error", "firebase", "You have no past delivered orders to reorder.")
        active = firebase_service.get_active_order(user_id)
        if active:
            return _build_response("error", "firebase", "You already have an active order.")
        last = delivered[0]
        
        cloned_items = []
        for i in last.get("items", []):
            if isinstance(i, dict):
                cloned_items.append({
                    "name": i.get("name"),
                    "quantity": i.get("quantity"),
                    "unit_price": i.get("unit_price")
                })
                
        new_order = {
            "user_id": user_id,
            "restaurant_name": last["restaurant_name"],
            "items": cloned_items,
            "payment_method": last.get("payment_method", "UPI"),
            "status": "Preparing",
            "delivery_stage": "Restaurant is preparing your order",
            "estimated_arrival_minutes": 35,
            "delivery_address": last.get("delivery_address", "Default Saved Address"),
            "is_active": True
        }
        res = firebase_service.create_order(new_order)
        if res["success"]:
            return _build_response("reorder_created", "firebase", "We've reordered your last meal!", res["order"])
        return None

    elif intent.startswith("support_ticket_"):
        issue = intent.split("_")[2]
        last = firebase_service.get_latest_order(user_id)
        if not last:
            return _build_response("error", "firebase", "No recent orders to create a ticket for.")
        ticket = {
            "user_id": user_id,
            "order_id": last["order_id"],
            "issue_type": f"{issue}_item" if issue in ["missing", "wrong"] else "damaged_food",
            "description": message,
            "status": "Open"
        }
        res = firebase_service.create_support_ticket(ticket)
        if res["success"]:
            return _build_response("support_ticket_created", "firebase", "Support ticket created. Our team will review this shortly.", res["ticket"])
        return None

    elif intent == "coupon":
        # simple demo: just validate first uppercase word
        words = message.upper().split()
        for w in words:
            if w in _COUPONS:
                return _build_response("coupon_result", "firebase", f"Coupon {w} is valid!", {"coupon": w, "details": _COUPONS[w]})
        return _build_response("error", "firebase", "This coupon is either invalid or expired.")
        
    elif intent == "delivery_estimate":
        return _build_response("delivery_estimate", "faq", "Delivery fees start at Rs.20 for up to 2km.", {"base_fee": 20, "per_km": 10})

    return None

# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "service": "FoodFlow Support Bot",
        "firebase_available": firebase_service.is_firebase_available(),
        "gemini_available": gemini_service.is_gemini_available(),
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    raw_message = req.message.strip()
    user_id = req.user_id.strip()
    norm_msg = _normalize_message(raw_message)
    
    print(f"[Chat] User: {user_id} | Msg: '{raw_message}' | Normalized: '{norm_msg}'")

    def _translate(resp: ChatResponse) -> ChatResponse:
        lang = getattr(req, "language", "english")
        if lang and lang.lower() not in ("english", "en", ""):
            resp.message = gemini_service.translate_content(resp.message, lang)
            if resp.data and "matched_question" in resp.data:
                resp.data["matched_question"] = gemini_service.translate_content(resp.data["matched_question"], lang)
        return resp

    if not raw_message:
        return _translate(_build_response("error", "error", "Message cannot be empty."))

    if _detect_frustration(raw_message):
        print("[Chat] Frustration detected. Escalating.")
        return _translate(_build_response("escalation", "escalation", "I am incredibly sorry. Escalating to human agent.", {"escalating": True}))

    # 1. Operational Intents
    op_intent = _detect_operational_intent(raw_message)
    if op_intent != "none":
        print(f"[Chat] Operational intent matched: {op_intent}")
        op_resp = handle_operational(op_intent, user_id, raw_message)
        if op_resp:
            return _translate(op_resp)

    # 2 & 3 & 4. Tracking / History
    track_intent = _detect_order_intent(raw_message)
    if track_intent != "none":
        print(f"[Chat] Order-related intent matched: {track_intent}")
        
        if track_intent == "active":
            order = firebase_service.get_active_order(user_id)
            if order:
                eta = order.get("estimated_arrival_minutes")
                eta_txt = f"in {eta} min" if eta else "soon"
                rider = order.get("rider_name")
                rider_txt = f" Rider: {rider}." if rider else ""
                msg = f"Your order is **{order.get('status')}**.{rider_txt} ETA: {eta_txt}."
                return _translate(_build_response("order_status", "firebase", msg, order))
            else:
                return _translate(_build_response("order_status", "firebase", "No active orders right now.", {"active": False}))

        elif track_intent == "items_history":
            last = firebase_service.get_latest_order(user_id)
            if last:
                return _translate(_build_response("ordered_items_history", "firebase", "Here are the items from your latest order.", last))
            else:
                return _translate(_build_response("error", "firebase", "No recent orders found to fetch items for."))

        elif track_intent == "history":
            orders = firebase_service.get_order_history(user_id)
            print(f"[Chat] Fetched {len(orders)} orders for history.")
            if orders:
                return _translate(_build_response("order_history", "firebase", f"Here are your {len(orders)} past orders.", {"orders": orders}))
            else:
                return _translate(_build_response("order_history", "firebase", "You don't have past orders.", {"orders": []}))

    # 5. FAQ Matching (Skipped if order intent was found)
    print("[Chat] No order intent matched. Checking FAQ...")
    faq_match = faq_service.match_faq(raw_message)
    if faq_match:
        faq = faq_match["faq"]
        print(f"[Chat] FAQ matched: '{faq['question']}' (score: {faq_match['score']})")
        return _translate(_build_response("faq", "faq", faq["answer"], {
            "matched_question": faq["question"],
            "category": faq.get("category"),
            "confidence": round(faq_match["score"], 3),
        }))

    # 6. Gemini Fallback
    print("[Chat] No FAQ match. Falling back to Gemini.")
    gemini_reply = gemini_service.ask_gemini(raw_message)
    if gemini_reply:
        return _translate(_build_response("gemini", "gemini", gemini_reply, {"fallback": True}))

    return _translate(_build_response("error", "error", "I'm sorry, I couldn't assist with that."))


@app.post("/api/seed-data")
async def seed_data():
    result = firebase_service.seed_demo_data()
    if not result.get("success"):
        raise HTTPException(status_code=503, detail=result.get("error", "Seed failed"))
    return result

# Expose Explicit Endpoints for REST usage
@app.post("/api/orders/create", response_model=ChatResponse)
async def create_new_order(req: CreateOrderRequest):
    print(f"[API] Received order create request for user: {req.user_id}")
    print(f"[API] Payload: {req.dict()}")
    
    new_order = {
        "user_id": req.user_id,
        "restaurant_name": req.restaurant_name,
        "items": [i.dict() for i in req.items],
        "payment_method": req.payment_method,
        "delivery_address": req.delivery_address,
        "status": "Preparing",
        "delivery_stage": "Restaurant is preparing your order",
        "estimated_arrival_minutes": 25,
        "is_active": True
    }
    
    res = firebase_service.create_order(new_order)
    
    if res["success"]:
        print(f"[API] Order created successfully: {res['order'].get('order_id')}")
        return _build_response(
            "order_created", 
            "firebase", 
            "Your order has been placed successfully.", 
            res["order"]
        )
    
    print(f"[API] Order creation failed: {res.get('error')}")
    return _build_response(
        "error", 
        "backend", 
        "Unable to create order. Please check the order details and try again.", 
        {
            "error_code": "ORDER_CREATE_FAILED",
            "details": res.get("error", "Unknown error occurred during Firestore save.")
        }
    )

@app.post("/api/orders/cancel")
async def cancel_order(req: Dict[str, Any]):
    return handle_operational("cancel_order", req.get("user_id"), "") or {"error": "Failed"}

@app.post("/api/orders/refund")
async def req_refund(req: Dict[str, Any]):
    return handle_operational("refund_request", req.get("user_id"), "") or {"error": "Failed"}

@app.get("/api/orders/{user_id}")
async def get_user_history(user_id: str, limit: int = 10):
    orders = firebase_service.get_order_history(user_id, limit=limit)
    return _build_response("order_history", "firebase", "Order history fetched successfully.", {"orders": orders})

@app.get("/api/orders/{user_id}/refund-status")
async def check_refund(user_id: str):
    return handle_operational("refund_status", user_id, "") or {"error": "Failed"}

@app.post("/api/orders/update-address")
async def update_addr(req: Dict[str, Any]):
    return handle_operational("address_change", req.get("user_id"), "") or {"error": "Failed"}

@app.post("/api/orders/reorder-last")
async def reorder(req: Dict[str, Any]):
    return handle_operational("reorder_last", req.get("user_id"), "") or {"error": "Failed"}

@app.post("/api/support/ticket")
async def create_ticket(req: Dict[str, Any]):
    return handle_operational("support_ticket_missing", req.get("user_id"), req.get("description", "Issue reported")) or {"error": "Failed"}

@app.post("/api/coupons/validate")
async def validate_coupon_endpoint(req: Dict[str, Any]):
    return handle_operational("coupon", "N/A", req.get("coupon_code", "")) or {"error": "Failed"}

@app.get("/api/delivery/estimate")
async def get_estimate(distance_km: float = 5):
    return handle_operational("delivery_estimate", "N/A", "") or {"error": "Failed"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
