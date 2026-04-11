"""
Firebase Firestore service for FoodFlow Support Bot.

Provides:
  - Safe Firestore initialisation (graceful fallback if credentials are absent)
  - Fetch active order for a user
  - Fetch order history for a user
  - Seed realistic demo data
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
    """Returns True if Firestore is ready for use."""
    return _firebase_ok


# ─── Order helpers ────────────────────────────────────────────────────────────

def _doc_to_dict(doc) -> Dict[str, Any]:
    """Convert a Firestore document snapshot to a plain dict."""
    data = doc.to_dict()
    # Firestore timestamps → ISO string
    for key, val in data.items():
        if hasattr(val, "isoformat"):
            data[key] = val.isoformat()
    return data


def get_active_order(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch the currently active order for a user.
    Returns the order dict or None.
    """
    if not _init_firebase():
        return None
    try:
        from firebase_admin import firestore
        orders_ref = _db.collection("orders")
        query = (
            orders_ref
            .where("user_id", "==", user_id)
            .where("is_active", "==", True)
            .limit(1)
        )
        docs = query.get()
        for doc in docs:
            return _doc_to_dict(doc)
        return None
    except Exception as exc:
        print(f"[Firebase] get_active_order error: {exc}")
        return None


def get_latest_order(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch the most recent order (active or not) for a user.
    Uses ordering by created_at descending.
    """
    if not _init_firebase():
        return None
    try:
        from firebase_admin import firestore
        orders_ref = _db.collection("orders")
        query = (
            orders_ref
            .where("user_id", "==", user_id)
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(1)
        )
        docs = query.get()
        for doc in docs:
            return _doc_to_dict(doc)
        return None
    except Exception as exc:
        print(f"[Firebase] get_latest_order error: {exc}")
        return None


def get_order_history(user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Fetch the N most recent orders for a user (sorted newest first).
    """
    if not _init_firebase():
        return []
    try:
        from firebase_admin import firestore
        orders_ref = _db.collection("orders")
        query = (
            orders_ref
            .where("user_id", "==", user_id)
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        docs = query.get()
        return [_doc_to_dict(doc) for doc in docs]
    except Exception as exc:
        print(f"[Firebase] get_order_history error: {exc}")
        return []


def get_all_orders(user_id: str) -> List[Dict[str, Any]]:
    """Alias for get_order_history with higher limit, for the /api/orders endpoint."""
    return get_order_history(user_id, limit=20)


# ─── Seed data ────────────────────────────────────────────────────────────────

def seed_demo_data() -> Dict[str, Any]:
    """
    Create realistic demo users and orders in Firestore.
    Safe to call multiple times — uses set() with merge=False per doc ID.
    """
    if not _init_firebase():
        return {"success": False, "error": "Firebase not available"}

    try:
        now = datetime.now(timezone.utc)

        # ── Sample users ──────────────────────────────────────────────────────
        users = [
            {"user_id": "user_001", "name": "Aryan Sharma", "email": "aryan@example.com", "phone": "+91-9876541001"},
            {"user_id": "user_002", "name": "Priya Nair",   "email": "priya@example.com",  "phone": "+91-9876541002"},
            {"user_id": "user_003", "name": "Rohan Mehta",  "email": "rohan@example.com",  "phone": "+91-9876541003"},
        ]
        for user in users:
            _db.collection("users").document(user["user_id"]).set(user)

        # ── Helper: quick timestamp ───────────────────────────────────────────
        def ts(delta_days=0, delta_hours=0):
            return (now - timedelta(days=delta_days, hours=delta_hours)).isoformat()

        # ── Sample orders ─────────────────────────────────────────────────────
        orders = [
            # user_001 → 1 ACTIVE order
            {
                "order_id": "ORD1001",
                "user_id": "user_001",
                "restaurant_name": "Burger Hub",
                "items": ["Veg Burger", "Masala Fries", "Coke"],
                "total_amount": 349,
                "payment_method": "UPI",
                "status": "On the way",
                "delivery_stage": "Picked up by rider",
                "estimated_arrival_minutes": 12,
                "rider_name": "Arjun",
                "rider_phone": "+91-9876543210",
                "created_at": ts(delta_hours=0),
                "is_active": True,
            },
            # user_001 → past orders
            {
                "order_id": "ORD1002",
                "user_id": "user_001",
                "restaurant_name": "Pizza Palace",
                "items": ["Margherita Pizza (M)", "Garlic Bread", "Pepsi"],
                "total_amount": 529,
                "payment_method": "Credit Card",
                "status": "Delivered",
                "delivery_stage": "Delivered",
                "estimated_arrival_minutes": 0,
                "rider_name": "Karthik",
                "rider_phone": "+91-9876543211",
                "created_at": ts(delta_days=1),
                "is_active": False,
            },
            {
                "order_id": "ORD1003",
                "user_id": "user_001",
                "restaurant_name": "Biryani Delight",
                "items": ["Chicken Biryani (Full)", "Raita", "Mirchi Ka Salan"],
                "total_amount": 420,
                "payment_method": "Wallet",
                "status": "Delivered",
                "delivery_stage": "Delivered",
                "estimated_arrival_minutes": 0,
                "rider_name": "Vikram",
                "rider_phone": "+91-9876543212",
                "created_at": ts(delta_days=3),
                "is_active": False,
            },
            {
                "order_id": "ORD1004",
                "user_id": "user_001",
                "restaurant_name": "Sushi Sakura",
                "items": ["California Roll x2", "Edamame", "Green Tea Ice Cream"],
                "total_amount": 799,
                "payment_method": "Credit Card",
                "status": "Cancelled",
                "delivery_stage": "Cancelled",
                "estimated_arrival_minutes": 0,
                "rider_name": None,
                "rider_phone": None,
                "created_at": ts(delta_days=5),
                "is_active": False,
            },
            {
                "order_id": "ORD1005",
                "user_id": "user_001",
                "restaurant_name": "Dosa Delight",
                "items": ["Masala Dosa", "Sambar Vada x2", "Filter Coffee"],
                "total_amount": 235,
                "payment_method": "COD",
                "status": "Delivered",
                "delivery_stage": "Delivered",
                "estimated_arrival_minutes": 0,
                "rider_name": "Suresh",
                "rider_phone": "+91-9876543213",
                "created_at": ts(delta_days=7),
                "is_active": False,
            },
            # user_002 orders
            {
                "order_id": "ORD2001",
                "user_id": "user_002",
                "restaurant_name": "Wok & Roll",
                "items": ["Veg Hakka Noodles", "Manchurian Gravy", "Spring Rolls x3"],
                "total_amount": 455,
                "payment_method": "UPI",
                "status": "Preparing",
                "delivery_stage": "Restaurant is preparing your food",
                "estimated_arrival_minutes": 30,
                "rider_name": None,
                "rider_phone": None,
                "created_at": ts(delta_hours=0),
                "is_active": True,
            },
            {
                "order_id": "ORD2002",
                "user_id": "user_002",
                "restaurant_name": "Taco Fiesta",
                "items": ["Veg Tacos x3", "Nachos with Cheese", "Horchata"],
                "total_amount": 390,
                "payment_method": "Debit Card",
                "status": "Delivered",
                "delivery_stage": "Delivered",
                "estimated_arrival_minutes": 0,
                "rider_name": "Ravi",
                "rider_phone": "+91-9876543214",
                "created_at": ts(delta_days=2),
                "is_active": False,
            },
            {
                "order_id": "ORD2003",
                "user_id": "user_002",
                "restaurant_name": "The Healthy Bowl",
                "items": ["Quinoa Salad", "Avocado Toast", "Cold Brew Coffee"],
                "total_amount": 580,
                "payment_method": "Wallet",
                "status": "Refunded",
                "delivery_stage": "Refunded",
                "estimated_arrival_minutes": 0,
                "rider_name": None,
                "rider_phone": None,
                "created_at": ts(delta_days=4),
                "is_active": False,
            },
            # user_003 orders
            {
                "order_id": "ORD3001",
                "user_id": "user_003",
                "restaurant_name": "Kebab King",
                "items": ["Seekh Kebab x6", "Rumali Roti x4", "Mint Chutney"],
                "total_amount": 610,
                "payment_method": "UPI",
                "status": "On the way",
                "delivery_stage": "Rider is nearby",
                "estimated_arrival_minutes": 5,
                "rider_name": "Mohammed Ali",
                "rider_phone": "+91-9876543215",
                "created_at": ts(delta_hours=0),
                "is_active": True,
            },
            {
                "order_id": "ORD3002",
                "user_id": "user_003",
                "restaurant_name": "Pancake House",
                "items": ["Blueberry Pancakes", "Classic Waffle", "Orange Juice"],
                "total_amount": 470,
                "payment_method": "Credit Card",
                "status": "Delivered",
                "delivery_stage": "Delivered",
                "estimated_arrival_minutes": 0,
                "rider_name": "Deepak",
                "rider_phone": "+91-9876543216",
                "created_at": ts(delta_days=2),
                "is_active": False,
            },
            {
                "order_id": "ORD3003",
                "user_id": "user_003",
                "restaurant_name": "Thali Express",
                "items": ["Rajasthani Thali (Full)", "Buttermilk", "Gulab Jamun x2"],
                "total_amount": 299,
                "payment_method": "COD",
                "status": "Delivered",
                "delivery_stage": "Delivered",
                "estimated_arrival_minutes": 0,
                "rider_name": "Ganesh",
                "rider_phone": "+91-9876543217",
                "created_at": ts(delta_days=6),
                "is_active": False,
            },
            {
                "order_id": "ORD3004",
                "user_id": "user_003",
                "restaurant_name": "Rolls Mania",
                "items": ["Paneer Tikka Roll x2", "Chicken Kathi Roll", "Lime Soda"],
                "total_amount": 320,
                "payment_method": "UPI",
                "status": "Cancelled",
                "delivery_stage": "Cancelled",
                "estimated_arrival_minutes": 0,
                "rider_name": None,
                "rider_phone": None,
                "created_at": ts(delta_days=8),
                "is_active": False,
            },
        ]

        for order in orders:
            _db.collection("orders").document(order["order_id"]).set(order)

        return {
            "success": True,
            "users_seeded": len(users),
            "orders_seeded": len(orders),
        }

    except Exception as exc:
        print(f"[Firebase] seed_demo_data error: {exc}")
        return {"success": False, "error": str(exc)}
