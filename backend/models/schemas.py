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
    language: Optional[str] = "english"


class ChatResponse(BaseModel):
    """Structured response returned by POST /api/chat."""
    type: str          # order_status | order_history | faq | gemini | error
    source: str        # firebase | faq | gemini | error
    message: str       # Human-readable reply text
    data: Dict[str, Any] = {}  # Additional structured data


class OrderItemDetail(BaseModel):
    name: str
    quantity: int
    unit_price: float
    total_price: Optional[float] = None

class OrderItemCreate(BaseModel):
    name: str
    quantity: int
    unit_price: float

class CreateOrderRequest(BaseModel):
    user_id: str
    restaurant_name: str
    items: List[OrderItemCreate]
    payment_method: str
    delivery_address: str

class OrderItem(BaseModel):
    """Represents a single order document."""
    order_id: str
    user_id: str
    restaurant_name: str
    items: List[Dict[str, Any]]
    total_amount: float
    payment_method: str
    status: str
    delivery_stage: str
    estimated_arrival_minutes: Optional[int] = None
    rider_name: Optional[str] = None
    rider_phone: Optional[str] = None
    delivery_address: Optional[str] = None
    refund_status: Optional[str] = None
    refund_amount: Optional[float] = None
    refund_eta_days: Optional[int] = None
    created_at: str
    is_active: bool
class SupportTicket(BaseModel):
    """Support ticket for issues like missing item, wrong item, damaged food."""
    ticket_id: str
    user_id: str
    order_id: str
    issue_type: str
    description: str
    status: str
    created_at: str


class FAQDebugResponse(BaseModel):
    """Debug response for /api/debug/faq-match endpoint."""
    query: str
    matched: bool
    confidence: float
    reason: str
    matched_question: Optional[str] = None
    matched_answer: Optional[str] = None
    category: Optional[str] = None
