from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    upload_dir: str = "./uploads"
    max_file_size_mb: int = 50
    nesting_timeout_sec: int = 120

    model_config = {"env_file": ".env"}


settings = Settings()
