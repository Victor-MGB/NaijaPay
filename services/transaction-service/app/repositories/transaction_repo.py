import json
from typing import Optional, Dict, Any
from datetime import datetime
import uuid
import structlog

from ..utils.database import db_pool
from ..models.transaction import Transaction, TransactionStatus, PaymentMethod

logger = structlog.get_logger(__name__)


class TransactionRepository:
    
    async def create_transaction(
        self,
        idempotency_key: str,
        user_id: str,
        amount: float,
        currency: str,
        payment_method: PaymentMethod,
        metadata: Dict[str, Any]
    ) -> Transaction:
        """Create a new transaction record - idempotent"""
        transaction_id = str(uuid.uuid4())
        now = datetime.utcnow()

        async with db_pool.connection() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO transactions (
                    id, idempotency_key, user_id, amount, currency, 
                    status, payment_method, metadata, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (idempotency_key) 
                DO UPDATE SET updated_at = NOW()
                RETURNING *
                """,
                transaction_id, 
                idempotency_key, 
                user_id, 
                amount, 
                currency, 
                TransactionStatus.PENDING.value, 
                payment_method.value,
                json.dumps(metadata or {}), 
                now, 
                now
            )

            logger.info("Transaction created/retrieved", 
                    transaction_id=str(row["id"]), 
                    user_id=user_id)
        return self._row_to_transaction(row)

    async def update_transaction_status(
        self,
        transaction_id: str,
        status: TransactionStatus,
        metadata_updates: Optional[Dict[str, Any]] = None
    ) -> Optional[Transaction]:
        """Update transaction status"""
        async with db_pool.connection() as conn:
            if metadata_updates:
                await conn.execute(
                    """
                    UPDATE transactions 
                    SET status = $1, 
                        metadata = metadata || $2::jsonb,
                        updated_at = NOW()
                    WHERE id = $3
                    """,
                    status.value, json.dumps(metadata_updates), transaction_id
                )
            else:
                await conn.execute(
                    """
                    UPDATE transactions 
                    SET status = $1, updated_at = NOW()
                    WHERE id = $2
                    """,
                    status.value, transaction_id
                )

            row = await conn.fetchrow(
                "SELECT * FROM transactions WHERE id = $1", transaction_id
            )
            return self._row_to_transaction(row) if row else None

    async def get_transaction_by_id(self, transaction_id: str) -> Optional[Transaction]:
        async with db_pool.connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM transactions WHERE id = $1", transaction_id
            )
            return self._row_to_transaction(row) if row else None

    async def get_transaction_by_idempotency_key(self, key: str) -> Optional[Transaction]:
        async with db_pool.connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM transactions WHERE idempotency_key = $1", key
            )
            return self._row_to_transaction(row) if row else None

    def _row_to_transaction(self, row) -> Optional[Transaction]:
        if not row:
            return None

        # Safe metadata conversion
        metadata_raw = row.get("metadata")
        if isinstance(metadata_raw, (str, bytes, bytearray)):
            try:
                metadata = json.loads(metadata_raw)
            except:
                metadata = {}
        elif isinstance(metadata_raw, dict):
            metadata = metadata_raw
        else:
            metadata = dict(metadata_raw) if metadata_raw else {}

        return Transaction(
            id=str(row["id"]), 
            idempotency_key=row["idempotency_key"],
            user_id=row["user_id"],
            amount=float(row["amount"]),
            currency=row["currency"],
            status=TransactionStatus(row["status"]),
            payment_method=PaymentMethod(row["payment_method"]),
            metadata=metadata,
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )