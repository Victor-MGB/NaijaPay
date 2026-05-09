from fastapi import APIRouter, HTTPException, Header
from typing import Optional
import structlog

from ..models.transaction import PaymentRequest, PaymentResponse, TransactionStatus
from ..repositories.transaction_repo import TransactionRepository
from ..repositories.idempotency_repo import IdempotencyRepository
from ..utils.queue import rabbitmq_client

router = APIRouter()
logger = structlog.get_logger()

transaction_repo = TransactionRepository()
idempotency_repo = IdempotencyRepository()


@router.post("/process", response_model=PaymentResponse)
async def process_payment(
    request: PaymentRequest,
    idempotency_key: Optional[str] = Header(None)
):
    """Clean & Robust Idempotency Handler"""
    key = idempotency_key or request.idempotency_key

    # Cache check
    cached = await idempotency_repo.get_cached_response(key)
    if cached and isinstance(cached, dict):
        logger.info("Cache hit", key=key)
        return PaymentResponse(**cached)

    try:
        # Check if already processed
        existing = await transaction_repo.get_transaction_by_idempotency_key(key)
        if existing:
            logger.info("Recovered existing transaction", key=key)
            return PaymentResponse(
                transaction_id=str(existing.id),
                idempotency_key=key,
                status=existing.status,
                amount=existing.amount,
                currency=existing.currency,
                message="Payment already processed",
                created_at=existing.created_at,
                metadata=existing.metadata or {}
            )

        # Store processing state
        await idempotency_repo.store_response(
            key, {"status": "processing"}, 202
        )

        # Create transaction
        transaction = await transaction_repo.create_transaction(
            idempotency_key=key,
            user_id=request.user_id,
            amount=request.amount,
            currency=request.currency,
            payment_method=request.payment_method,
            metadata=request.metadata or {}
        )

        # Process payment
        if request.amount <= 0:
            raise ValueError("Invalid amount")

        transaction = await transaction_repo.update_transaction_status(
            transaction.id,
            TransactionStatus.SUCCESS,
            {"processor_response": "simulated_success"}
        )

        await rabbitmq_client.publish_event(
            "payment.processed",
            {
                "transaction_id": str(transaction.id),
                "user_id": request.user_id,
                "amount": request.amount,
                "status": "success"
            }
        )

        # Final Response
        response = PaymentResponse(
            transaction_id=str(transaction.id),
            idempotency_key=key,
            status=TransactionStatus.SUCCESS,
            amount=transaction.amount,
            currency=transaction.currency,
            message="Payment processed successfully",
            created_at=transaction.created_at,
            metadata=transaction.metadata or {}
        )

        # Save to cache
        await idempotency_repo.store_response(
            key, 
            response.model_dump(mode='json'), 
            200
        )

        logger.info("Payment processed successfully", key=key, transaction_id=response.transaction_id)
        return response

    except Exception as e:
        logger.error("Payment failed", key=key, error=str(e), exc_info=True)

        if 'transaction' in locals() and transaction is not None:
            try:
                await transaction_repo.update_transaction_status(
                    transaction.id, TransactionStatus.FAILED, {"error": str(e)}
                )
            except:
                pass

        raise HTTPException(status_code=400, detail=f"Payment processing failed: {str(e)}")