"""Application configuration loaded from environment variables."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://quickdrop:quickdrop@localhost:5432/disputes"
    database_url_sync: str = "postgresql://quickdrop:quickdrop@localhost:5432/disputes"

    # PaySwift
    payswift_base_url: str = "http://localhost:8081"
    payswift_timeout: float = 8.0

    # LLM provider: "groq" or "gemini"
    llm_provider: str = "groq"
    groq_api_key: str = ""
    groq_model: str = "qwen/qwen3.8-27b"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"

    # Application
    app_name: str = "Rider Payout Dispute Desk"
    debug: bool = False
    log_level: str = "INFO"

    # Policy
    auto_pay_limit_rupees: int = 200          # Max amount for automatic payout
    dispute_window_days: int = 7              # Only accept disputes within last 7 days
    daily_incentive_trips: int = 12           # Trips needed for daily incentive
    daily_incentive_amount: int = 150         # ₹150 daily incentive
    base_fare: int = 25                       # ₹25 base fare
    per_km_rate: int = 6                      # ₹6/km after first 2km
    cancellation_penalty: int = 10            # ₹10 penalty per rider cancellation


@lru_cache
def get_settings() -> Settings:
    return Settings()
