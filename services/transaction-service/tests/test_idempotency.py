import pytest
import asyncio
import httpx
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any

BASE_URL = "http://localhost:8001"

@pytest.mark.asyncio
async def test_idempotency_single_request():
    """Test that a single request works"""
    async with httpx.AsyncClient() as client:
        idempotency_key = f"test_key_{uuid4()}"
        payload = {
            "idempotency_key": idempotency_key,
            "user_id": "user_123",
            "amount": 1000,
            "currency": "NGN",
            "payment_method": "wallet",
            "metadata": {"test": True}
        }
        
        response = await client.post(
            f"{BASE_URL}/api/v1/payments/process",
            json=payload,
            headers={"Idempotency-Key": idempotency_key}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["idempotency_key"] == idempotency_key
        assert data["status"] == "success"

@pytest.mark.asyncio
async def test_idempotency_duplicate_requests():
    """Test that duplicate requests return cached response"""
    async with httpx.AsyncClient() as client:
        idempotency_key = f"test_dup_{uuid4()}"
        payload = {
            "idempotency_key": idempotency_key,
            "user_id": "user_456",
            "amount": 2000,
            "currency": "NGN",
            "payment_method": "wallet",
            "metadata": {"test": "duplicate"}
        }
        
        # First request
        response1 = await client.post(
            f"{BASE_URL}/api/v1/payments/process",
            json=payload,
            headers={"Idempotency-Key": idempotency_key}
        )
        
        # Second request (should be cached)
        response2 = await client.post(
            f"{BASE_URL}/api/v1/payments/process",
            json=payload,
            headers={"Idempotency-Key": idempotency_key}
        )
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        data1 = response1.json()
        data2 = response2.json()
        
        # Should have same transaction ID
        assert data1["transaction_id"] == data2["transaction_id"]
        assert data1["status"] == data2["status"]

@pytest.mark.asyncio
async def test_concurrent_identical_requests():
    """Test 100 concurrent requests with same idempotency key"""
    idempotency_key = f"concurrent_{uuid4()}"
    payload = {
        "idempotency_key": idempotency_key,
        "user_id": "user_concurrent",
        "amount": 5000,
        "currency": "NGN",
        "payment_method": "wallet",
        "metadata": {"test": "concurrent"}
    }
    
    async def make_request():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/api/v1/payments/process",
                json=payload,
                headers={"Idempotency-Key": idempotency_key}
            )
            return response
    
    # Make 100 concurrent requests
    tasks = [make_request() for _ in range(100)]
    responses = await asyncio.gather(*tasks)
    
    # All should succeed
    successful_responses = [r for r in responses if r.status_code == 200]
    assert len(successful_responses) == 100
    
    # Get unique transaction IDs
    transaction_ids = {r.json()["transaction_id"] for r in successful_responses}
    
    # Only ONE unique transaction should exist
    assert len(transaction_ids) == 1, f"Expected 1 transaction, got {len(transaction_ids)}"
    
    print(f"✓ Concurrent test passed: {len(successful_responses)} requests, {len(transaction_ids)} unique transaction")

@pytest.mark.asyncio
async def test_different_keys_different_transactions():
    """Test that different idempotency keys create different transactions"""
    async with httpx.AsyncClient() as client:
        key1 = f"key1_{uuid4()}"
        key2 = f"key2_{uuid4()}"
        
        payload1 = {
            "idempotency_key": key1,
            "user_id": "user_test",
            "amount": 100,
            "currency": "NGN",
            "payment_method": "wallet"
        }
        
        payload2 = {
            "idempotency_key": key2,
            "user_id": "user_test",
            "amount": 200,
            "currency": "NGN",
            "payment_method": "wallet"
        }
        
        response1 = await client.post(
            f"{BASE_URL}/api/v1/payments/process",
            json=payload1,
            headers={"Idempotency-Key": key1}
        )
        
        response2 = await client.post(
            f"{BASE_URL}/api/v1/payments/process",
            json=payload2,
            headers={"Idempotency-Key": key2}
        )
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        data1 = response1.json()
        data2 = response2.json()
        
        # Different transaction IDs
        assert data1["transaction_id"] != data2["transaction_id"]

def run_all_tests():
    """Run all tests synchronously"""
    asyncio.run(test_idempotency_single_request())
    asyncio.run(test_idempotency_duplicate_requests())
    asyncio.run(test_concurrent_identical_requests())
    asyncio.run(test_different_keys_different_transactions())
    print("\nAll idempotency tests passed!")

if __name__ == "__main__":
    run_all_tests()