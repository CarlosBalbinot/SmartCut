from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./smartcut.db"
    secret_key: str = "smartcut-default-secret-change-in-production"
    jwt_secret_key: str = "smartcut-dev-jwt-secret-CHANGE-ME"
    upload_dir: str = "./uploads"
    max_file_size_mb: int = 50
    nesting_timeout_sec: int = 120

    model_config = {"env_file": ".env"}


settings = Settings()
