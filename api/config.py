from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATA_DIR: str = "data"
    DUCKDB_PATH: str = "data/commodex.duckdb"
    SQLITE_PATH: str = "data/commodex.sqlite"
    JWT_SECRET: str = "secret"
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    INGEST_SOURCE: str = "local" # or "mcx"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
