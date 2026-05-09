from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class TransactionStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELED = "canceled"
    REFUNDED = "refunded"


class PaymentMethod(str, Enum):
    CARD = "card"
    BANK_TRANSFER = "bank_transfer"
    USSD = "ussd"
    WALLET = "wallet"


class PaymentRequest(BaseModel):
    idempotency_key: str = Field(
        ...,
        min_length=10,
        max_length=255,
    )
    user_id: str = Field(
        ..., 
        min_length=1,
        max_length=100
    )
    amount: float = Field(
        ...,
        gt=0,
        le=10000000
    )
    currency: str = Field(
        "NGN",
        pattern=r"^[A-Z]{3}$"         
    )
    payment_method: PaymentMethod
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v: float) -> float:
        if v < 1:
            raise ValueError("Amount must be at least 1 NGN")
        if v > 10_000_000:
            raise ValueError("Amount cannot exceed 10 million NGN")
        return round(v, 2)


class PaymentResponse(BaseModel):
    transaction_id: str
    idempotency_key: str
    status: TransactionStatus
    amount: float
    currency: str
    message: str
    created_at: datetime
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class Transaction(BaseModel):
    id: str
    idempotency_key: str
    user_id: str
    amount: float
    currency: str
    status: TransactionStatus
    payment_method: PaymentMethod
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime