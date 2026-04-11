"""
Firebase Firestore service for FoodFlow Support Bot.

Provides:
  - Safe Firestore initialisation (graceful fallback if credentials are absent)
  - Fetch, create, update orders
  - Create support tickets
  - Seed realistic demo data with refunds, address changes, etc.
"""

import os
import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

# ─── Firebase Admin bootstrap ─────────────────────────────────────────────────
_db = None          # Firestore client (None if unavailable)
_firebase_ok = False

def _init_firebase():
    """Initialise Firebase Admin SDK once. Skips gracefully if not configured."""
    global _db, _firebase_ok
    if _firebase_ok:
        return True

    cred_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "backend/firebase-service-account.json")

    if not os.path.exists(cred_path):
        print(f"[Firebase] No service account found at '{cred_path}'. "
              "Running without Firebase (order queries will fail gracefully).")
        return False

    try:
        import firebase_admin
        from firebase_admin import credentials, firestore

        if not firebase_admin._apps:
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)

        _db = firestore.client()
        _firebase_ok = True
        print("[Firebase] Firestore initialised successfully.")
        return True

    except Exception as exc:
        print(f"[Firebase] Initialisation error: {exc}")
        return False


def is_firebase_available() -> bool:
    """Returns True if Firestore is ready for use, attempting initialisation if needed."""
    return _init_firebase()


# ─── Order helpers ────────────────────────────────────────────────────────────

def _doc_to_dict(doc) -> Dict[str, Any]:
    """Convert a Firestore document snapshot to a plain dict."""
    data = doc.to_dict()
    for key, val in data.items():
        if hasattr(val, "isoformat"):
            data[key] = val.isoformat()
    return data


def get_active_order(user_id: str) -> Optional[Dict[str, Any]]:
    if not _init_firebase():
        return None
    try:
        from firebase_admin import firestore
        orders_ref = _db.collection("orders")
        query = orders_ref.where("user_id", "==", user_id).where("is_active", "==", True).limit(1)
        docs = query.get()
        for doc in docs:
            return _doc_to_dict(doc)
        return None
    except Exception as exc:
        print(f"[Firebase] get_active_order error: {exc}")
        return None


def get_latest_order(user_id: str) -> Optional[Dict[str, Any]]:
    if not _init_firebase():
        return None
    try:
        orders_ref = _db.collection("orders")
        # Fetch all orders for the user and sort locally to avoid composite index requirements
        docs = orders_ref.where("user_id", "==", user_id).get()
        
        if not docs:
            return None
            
        # Sort by created_at descending
        sorted_docs = sorted(docs, key=lambda x: x.to_dict().get("created_at", ""), reverse=True)
        return _doc_to_dict(sorted_docs[0])
    except Exception as exc:
        print(f"[Firebase] get_latest_order error: {exc}")
        return None


def get_order_history(user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    if not _init_firebase():
        return []
    try:
        orders_ref = _db.collection("orders")
        # Fetch all and sort locally to avoid composite index requirements
        docs = orders_ref.where("user_id", "==", user_id).get()
        
        # Sort by created_at descending
        sorted_orders = [_doc_to_dict(doc) for doc in docs]
        sorted_orders.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        return sorted_orders[:limit]
    except Exception as exc:
        print(f"[Firebase] get_order_history error: {exc}")
        return []


def get_all_orders(user_id: str) -> List[Dict[str, Any]]:
    return get_order_history(user_id, limit=20)


def create_order(order_data: Dict[str, Any]) -> Dict[str, Any]:
    if not _init_firebase():
        return {"success": False, "error": "Firebase not available"}
    try:
        order_id = order_data.get("order_id")
        if not order_id:
            order_id = f"ORD{int(datetime.now(timezone.utc).timestamp())}"
            order_data["order_id"] = order_id
        
        if "created_at" not in order_data:
            order_data["created_at"] = datetime.now(timezone.utc).isoformat()
            
        # Field completion for a "live" feel
        order_data["status"] = order_data.get("status", "Preparing")
        order_data["delivery_stage"] = order_data.get("delivery_stage", "Restaurant is preparing your order")
        order_data["estimated_arrival_minutes"] = order_data.get("estimated_arrival_minutes", 25)
        order_data["rider_name"] = order_data.get("rider_name", "Sameer")
        order_data["rider_phone"] = order_data.get("rider_phone", "+91-9888877777")
        order_data["is_active"] = order_data.get("is_active", True)
        
        # Ensure items have complete calculations
        total_amount = 0.0
        if "items" in order_data and isinstance(order_data["items"], list):
            for i, item in enumerate(order_data["items"]):
                if isinstance(item, dict):
                    qty = int(item.get("quantity", 1))
                    price = float(item.get("unit_price", 0.0))
                    item["total_price"] = round(qty * price, 2)
                    total_amount += item["total_price"]
                else:
                    # Upgrade legacy string items dynamically if passed
                    order_data["items"][i] = {
                        "name": str(item),
                        "quantity": 1,
                        "unit_price": 100.0,
                        "total_price": 100.0
                    }
                    total_amount += 100.0
                    
        if "total_amount" not in order_data or order_data.get("total_amount") == 0:
            order_data["total_amount"] = round(total_amount, 2)

        print(f"[Firebase] Saving Order {order_id} for user {order_data.get('user_id')}...")
        _db.collection("orders").document(order_id).set(order_data)
        return {"success": True, "order": order_data}
    except Exception as exc:
        print(f"[Firebase] create_order error: {exc}")
        return {"success": False, "error": str(exc)}


def get_order_by_id(order_id: str) -> Optional[Dict[str, Any]]:
    if not _init_firebase():
        return None
    try:
        doc = _db.collection("orders").document(order_id).get()
        if doc.exists:
            return _doc_to_dict(doc)
        return None
    except Exception as exc:
        print(f"[Firebase] get_order_by_id error: {exc}")
        return None


def update_order(order_id: str, updates: Dict[str, Any]) -> bool:
    if not _init_firebase():
        return False
    try:
        _db.collection("orders").document(order_id).update(updates)
        return True
    except Exception as exc:
        print(f"[Firebase] update_order error: {exc}")
        return False


def create_support_ticket(ticket_data: Dict[str, Any]) -> Dict[str, Any]:
    if not _init_firebase():
        return {"success": False, "error": "Firebase not available"}
    try:
        ticket_id = ticket_data.get("ticket_id")
        if not ticket_id:
            ticket_id = f"TKT{int(datetime.now(timezone.utc).timestamp())}"
            ticket_data["ticket_id"] = ticket_id
        
        if "created_at" not in ticket_data:
            ticket_data["created_at"] = datetime.now(timezone.utc).isoformat()
            
        _db.collection("support_tickets").document(ticket_id).set(ticket_data)
        return {"success": True, "ticket": ticket_data}
    except Exception as exc:
        print(f"[Firebase] create_support_ticket error: {exc}")
        return {"success": False, "error": str(exc)}


# ─── Seed data ────────────────────────────────────────────────────────────────

def seed_demo_data() -> Dict[str, Any]:
    if not _init_firebase():
        return {"success": False, "error": "Firebase not available"}

    try:
        now = datetime.now(timezone.utc)

        users = [
            {"user_id": "user_001", "name": "Aryan Sharma", "email": "aryan@example.com", "phone": "+91-9876541001"},
            {"user_id": "user_002", "name": "Priya Nair",   "email": "priya@example.com",  "phone": "+91-9876541002"},
            {"user_id": "user_003", "name": "Rohan Mehta",  "email": "rohan@example.com",  "phone": "+91-9876541003"},
        ]
        for user in users:
            _db.collection("users").document(user["user_id"]).set(user)

        def ts(delta_days=0, delta_hours=0):
            return (now - timedelta(days=delta_days, hours=delta_hours)).isoformat()

        orders = [
            {
                "order_id": "ORD1001",
                "user_id": "user_001",
                "restaurant_name": "Burger Hub",
                "items": [
                    {"name": "Veg Burger", "quantity": 2, "unit_price": 120.0, "total_price": 240.0},
                    {"name": "Masala Fries", "quantity": 1, "unit_price": 60.0, "total_price": 60.0},
                    {"name": "Coke", "quantity": 1, "unit_price": 49.0, "total_price": 49.0}
                ],
                "total_amount": 349,
                "payment_method": "UPI",
                "status": "Preparing",
                "delivery_stage": "Restaurant is preparing your food",
                "estimated_arrival_minutes": 25,
                "rider_name": "Arjun",
                "rider_phone": "+91-9876543210",
                "delivery_address": "123 Tech Park, Block C",
                "created_at": ts(delta_hours=0),
                "is_active": True,
            },
            {
                "order_id": "ORD1002",
                "user_id": "user_001",
                "restaurant_name": "Pizza Palace",
                "items": [
                    {"name": "Margherita Pizza (M)", "quantity": 1, "unit_price": 350.0, "total_price": 350.0},
                    {"name": "Garlic Bread", "quantity": 1, "unit_price": 120.0, "total_price": 120.0},
                    {"name": "Pepsi", "quantity": 1, "unit_price": 59.0, "total_price": 59.0}
                ],
                "total_amount": 529,
                "payment_method": "Credit Card",
                "status": "Delivered",
                "delivery_stage": "Delivered",
                "estimated_arrival_minutes": 0,
                "rider_name": "Karthik",
                "rider_phone": "+91-9876543211",
                "delivery_address": "123 Tech Park, Block C",
                "created_at": ts(delta_days=1),
                "is_active": False,
            },
            {
                "order_id": "ORD1004",
                "user_id": "user_001",
                "restaurant_name": "Sushi Sakura",
                "items": [
                    {"name": "California Roll", "quantity": 2, "unit_price": 250.0, "total_price": 500.0},
                    {"name": "Edamame", "quantity": 1, "unit_price": 150.0, "total_price": 150.0},
                    {"name": "Green Tea Ice Cream", "quantity": 1, "unit_price": 149.0, "total_price": 149.0}
                ],
                "total_amount": 799,
                "payment_method": "Credit Card",
                "status": "Cancelled",
                "delivery_stage": "Cancelled",
                "estimated_arrival_minutes": 0,
                "rider_name": None,
                "rider_phone": None,
                "delivery_address": "123 Tech Park, Block C",
                "refund_status": "Refunded",
                "refund_amount": 799.0,
                "refund_eta_days": 0,
                "created_at": ts(delta_days=5),
                "is_active": False,
            },
            {
                "order_id": "ORD2001",
                "user_id": "user_002",
                "restaurant_name": "Wok & Roll",
                "items": [
                    {"name": "Veg Hakka Noodles", "quantity": 1, "unit_price": 160.0, "total_price": 160.0},
                    {"name": "Manchurian Gravy", "quantity": 1, "unit_price": 190.0, "total_price": 190.0},
                    {"name": "Spring Rolls", "quantity": 3, "unit_price": 35.0, "total_price": 105.0}
                ],
                "total_amount": 455,
                "payment_method": "UPI",
                "status": "On the way",
                "delivery_stage": "Rider is nearby",
                "estimated_arrival_minutes": 8,
                "rider_name": "Rahul",
                "rider_phone": "+91-9876543212",
                "delivery_address": "Apt 4B, Sunrise Towers",
                "created_at": ts(delta_hours=0),
                "is_active": True,
            },
        ]
        for order in orders:
            _db.collection("orders").document(order["order_id"]).set(order)

        tickets = [
            {
                "ticket_id": "TKT1001",
                "user_id": "user_001",
                "order_id": "ORD1002",
                "issue_type": "missing_item",
                "description": "I did not receive the Pepsi.",
                "status": "Open",
                "created_at": ts(delta_days=1, delta_hours=2)
            },
            {
                "ticket_id": "TKT1002",
                "user_id": "user_002",
                "order_id": "ORD2001",
                "issue_type": "wrong_item",
                "description": "Got cold coffee instead of coke.",
                "status": "Resolved",
                "created_at": ts(delta_days=2)
            }
        ]
        for ticket in tickets:
            _db.collection("support_tickets").document(ticket["ticket_id"]).set(ticket)

        faq_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "faq_data.json")
        faqs_seeded = 0
        if os.path.exists(faq_path):
            with open(faq_path, "r", encoding="utf-8") as f:
                faqs = json.load(f)
            for faq in faqs:
                _db.collection("faqs").document(str(faq["id"])).set(faq)
            faqs_seeded = len(faqs)

        return {
            "success": True,
            "users_seeded": len(users),
            "orders_seeded": len(orders),
            "tickets_seeded": len(tickets),
            "faqs_seeded": faqs_seeded,
        }

    except Exception as exc:
        print(f"[Firebase] seed_demo_data error: {exc}")
        return {"success": False, "error": str(exc)}
