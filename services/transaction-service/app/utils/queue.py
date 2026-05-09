import aio_pika
from typing import Optional, Any
import json
import structlog
from datetime import datetime   
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings

logger = structlog.get_logger(__name__)


class RabbitMQClient:
    _connection: Optional[aio_pika.Connection] = None
    _channel: Optional[aio_pika.Channel] = None
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def initialize(self):
        """Initialize RabbitMQ connection"""
        try:
            self._connection = await aio_pika.connect_robust(
                settings.RABBITMQ_URL, 
                heartbeat=60
            )
            self._channel = await self._connection.channel()
            
            # Declare exchanges and queues
            await self._channel.declare_exchange(
                "transactions", aio_pika.ExchangeType.TOPIC, durable=True
            )
            
            await self._channel.declare_queue(
                "transaction.events", durable=True
            )
            
            logger.info("RabbitMQ connection established")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise
    
    async def publish_event(self, event_type: str, data: dict):
        """Publish transaction event"""
        if not self._channel:
            await self.initialize()
        
        message = aio_pika.Message(
            body=json.dumps({
                "event_type": event_type,
                "data": data,
                "timestamp": datetime.utcnow().isoformat()
            }).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT
        )
        
        await self._channel.default_exchange.publish(
            message, 
            routing_key=f"transaction.{event_type}"
        )
        
        logger.info(f"Published event: {event_type}", event_type=event_type)
    
    async def close(self):
        """Close RabbitMQ connection"""
        if self._connection:
            await self._connection.close()
            logger.info("RabbitMQ connection closed")


rabbitmq_client = RabbitMQClient()