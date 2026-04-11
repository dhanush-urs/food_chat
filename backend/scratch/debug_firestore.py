import os
import sys
from typing import Any, Dict, List
import json
from datetime import datetime, timezone
from dotenv import load_dotenv

sys.path.append(os.getcwd())
load_dotenv(".env")
os.environ["FIREBASE_SERVICE_ACCOUNT_PATH"] = "firebase-service-account.json"

from services import firebase_service

def debug():
    print("Initializing Firebase...")
    firebase_service._init_firebase()
    
    if not firebase_service.is_firebase_available():
        print("Firebase is NOT available.")
        return

    user_id = "user_001"
    orders_ref = firebase_service._db.collection("orders")
    
    print(f"\n--- Fetching all orders for {user_id} (No order_by) ---")
    try:
        docs = orders_ref.where("user_id", "==", user_id).get()
        print(f"Count: {len(docs)}")
        for doc in docs:
            d = doc.to_dict()
            print(f" - {doc.id}: {d.get('restaurant_name')} | Created at: {d.get('created_at')}")
    except Exception as e:
        print(f"Error fetching: {e}")

    print(f"\n--- Fetching with order_by('created_at') ---")
    try:
        from firebase_admin import firestore
        docs = orders_ref.where("user_id", "==", user_id).order_by("created_at", direction=firestore.Query.DESCENDING).get()
        print(f"Count: {len(docs)}")
    except Exception as e:
        print(f"Error fetching with order_by: {e}")

if __name__ == "__main__":
    debug()
