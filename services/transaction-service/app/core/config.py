from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str
    RABBITMQ_URL: str

    TRANSACTION_SERVICE_URL: str
    WALLET_SERVICE_URL: str
    FRAUD_SERVICE_URL: str

    JWT_SECRET_KEY: str

    IDEMPOTENCY_TTL: int = 3600

    REDIS_MAX_CONNECTIONS: int = 50
    REDIS_SOCKET_TIMEOUT: int = 5

    RATE_LIMIT_REQUESTS: int = 1000
    RATE_LIMIT_PERIOD: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()