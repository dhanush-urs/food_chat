"""
Pydantic schemas for FoodFlow Support Bot API.
Defines request and response models for all endpoints.
"""

from pydantic import BaseModel
from typing import Any, Dict, List, Optional


class ChatRequest(BaseModel):
    """Incoming chat message from the frontend."""
    user_id: str
    message: str


class ChatResponse(BaseModel):
    """Structured response returned by POST /api/chat."""
    type: str          # order_status | order_history | faq | gemini | error
    source: str        # firebase | faq | gemini | error
    message: str       # Human-readable reply text
    data: Dict[str, Any] = {}  # Additional structured data


class OrderItem(BaseModel):
    """Represents a single order document."""
    order_id: str
    user_id: str
    restaurant_name: str
    items: List[str]
    total_amount: float
    payment_method: str
    status: str
    delivery_stage: str
    estimated_arrival_minutes: Optional[int] = None
    rider_name: Optional[str] = None
    rider_phone: Optional[str] = None
    created_at: str
    is_active: bool


class FAQDebugResponse(BaseModel):
    """Debug response for /api/debug/faq-match endpoint."""
    query: str
    matched: bool
    confidence: float
    reason: str
    matched_question: Optional[str] = None
    matched_answer: Optional[str] = None
    category: Optional[str] = None
