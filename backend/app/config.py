from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    max_pdf_bytes: int = Field(20 * 1024 * 1024, validation_alias="MAX_PDF_BYTES")
    storage_dir: str = "pdf_text"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
