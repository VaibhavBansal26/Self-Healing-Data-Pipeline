from typing import Optional, Literal, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict
from src.config import DEFAULT_SCHEMA_VERSION


class OrderEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    customer_id: str
    amount: float = Field(gt=0)
    currency: str
    status: Literal["created", "paid", "cancelled", "refunded"]
    schema_version: int = DEFAULT_SCHEMA_VERSION


class SimilarIncident(BaseModel):
    incident_id: str
    action: str
    original_payload: Dict[str, Any]
    healed_payload: Optional[Dict[str, Any]] = None
    status: str
    score: Optional[float] = None


class HealingDecision(BaseModel):
    action: Literal[
        "cast_amount_to_float",
        "fill_default_currency",
        "normalize_status",
        "send_to_dlq",
        "manual_review",
    ]
    reason: str
    confidence: float = Field(ge=0, le=1)
    risk_level: Literal["low", "medium", "high"]
    requires_human_approval: bool


class HealingState(BaseModel):
    original_payload: Dict[str, Any]
    healed_payload: Optional[Dict[str, Any]] = None
    error_type: str
    error_message: str
    similar_incidents: List[SimilarIncident] = []
    decision: Optional[HealingDecision] = None
    human_feedback: Optional[Dict[str, Any]] = None
    verified: bool = False
    final_status: str = "pending"
