from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://thecoach:thecoach_dev@db:5432/thecoach"
    garmin_email: str = ""
    garmin_password: str = ""
    anthropic_api_key: str = ""
    withings_client_id: str = ""
    withings_client_secret: str = ""
    withings_redirect_uri: str = "http://localhost:8002/api/withings/callback"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
