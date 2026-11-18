from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LLM Service"
    environment: str = "development"
    database_url: str = "postgresql+asyncpg://llm:dev@localhost:5432/llm"
    llm_provider: str = "demo"  # "demo" | "anthropic" | "gateway"
    llm_api_key: str = ""  # secret — never commit, never log
    llm_base_url: str = ""  # set in .env for custom endpoints
    llm_model: str = "claude-opus-5"
    llm_timeout_seconds: float = 30.0
    llm_max_retries: int = 2

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
