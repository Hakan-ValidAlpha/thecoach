from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://thecoach:thecoach_dev@db:5432/thecoach"
    garmin_email: str = ""
    garmin_password: str = ""
    anthropic_api_key: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
