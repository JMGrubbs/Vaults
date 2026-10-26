from pydantic import PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    redis_url: str
    algorithm: str = "HS256"
    access_token_expire_minutes: PositiveInt = 60
    authorization_code_expire_seconds: PositiveInt = 120
    oauth_login_rate_window_seconds: PositiveInt = 300
    oauth_login_email_limit: PositiveInt = 5
    oauth_login_ip_limit: PositiveInt = 300
    cors_origins: str = (
        "http://localhost:5173,http://localhost:5175,"
        "https://dvaults.johnmgrubbs.io"
    )
    cookie_key: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
