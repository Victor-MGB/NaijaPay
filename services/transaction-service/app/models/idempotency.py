from pydantic import BaseModel, ConfigDict
from typing import Dict, Any
from datetime import datetime

class IdempotencyRequest(BaseModel):
    idempotency_key: str
    response_data: Dict[str, Any]
    status_code: int
    created_at: datetime
    expires_at: datetime

    model_config = ConfigDict(
        from_attributes=True,   
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    )