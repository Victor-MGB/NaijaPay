import asyncio
import aiohttp
from uuid import uuid4
import time
from typing import List, Dict
import statistics

async def load_test_concurrent_requests(num_requests: int = 1000, num_unique_keys: int = 100):
    """
    Load test with 1000 requests, some sharing idempotency keys
    """
    # Generate idempotency keys (some duplicate, some unique)
    keys = [f"load_key_{uuid4()}" for _ in range(num_unique_keys)]
    
    # Create requests: 80% unique keys, 20% duplicates
    requests_data = []
    for i in range(num_requests):
        if i % 5 == 0 and i > 0:  # Every 5th request is duplicate of previous
            key = requests_data[-1]["key"]
        else:
            key = keys[i % len(keys)]
        
        requests_data.append({
            "key": key,
            "payload": {
                "idempotency_key": key,
                "user_id": f"user_{key[:8]}",
                "amount": 100 + (i % 5000),
                "currency": "NGN",
                "payment_method": "wallet",
                "metadata": {"load_test": True, "request_id": i}
            }
        })
    
    async def make_request(session, data):
        start = time.time()
        async with session.post(
            "http://localhost:8001/api/v1/payments/process",
            json=data["payload"],
            headers={"Idempotency-Key": data["key"]}
        ) as response:
            latency = time.time() - start
            return {
                "status": response.status,
                "latency": latency,
                "key": data["key"]
            }
    
    async with aiohttp.ClientSession() as session:
        tasks = [make_request(session, data) for data in requests_data]
        results = await asyncio.gather(*tasks)
    
    # Analyze results
    successful = [r for r in results if r["status"] == 200]
    latencies = [r["latency"] for r in successful]
    
    print(f"\n📊 Load Test Results:")
    print(f"   Total requests: {num_requests}")
    print(f"   Successful: {len(successful)}")
    print(f"   Failed: {num_requests - len(successful)}")
    print(f"   Success rate: {(len(successful)/num_requests)*100:.2f}%")
    print(f"   Avg latency: {statistics.mean(latencies)*1000:.2f}ms")
    print(f"   Median latency: {statistics.median(latencies)*1000:.2f}ms")
    print(f"   P95 latency: {statistics.quantiles(latencies, n=20)[18]*1000:.2f}ms" if len(latencies) > 20 else "   Not enough data for P95")
    
    # Check for duplicate processing
    processed_transactions = {}
    async with aiohttp.ClientSession() as session:
        # This would need an API endpoint to check, but we'll simulate
        print(f"   Unique keys: {len(set(data['key'] for data in requests_data))}")
    
    return results

if __name__ == "__main__":
    asyncio.run(load_test_concurrent_requests(1000, 100))