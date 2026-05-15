from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):

    APP_NAME: str
    APP_ENVIRONMENT: str
    DEBUG: bool


    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int


    DATABASE_URL: str

    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str

    EMAIL_HOST: str
    EMAIL_PORT: int
    EMAIL_USE_TLS: bool
    EMAIL_HOST_USER: str
    EMAIL_HOST_PASSWORD: str

    # Comma-separated list of allowed CORS origins. Use a real allowlist in
    # any non-dev environment. "*" is accepted but will force
    # allow_credentials=False in main.py (browsers reject "*" + credentials).
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173"

    # Logging. LOG_FORMAT="json" switches to one-JSON-line-per-record output,
    # which is what aggregators (Datadog, CloudWatch, Loki, etc.) want.
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "text"  # "text" | "json"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()