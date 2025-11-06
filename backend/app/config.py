from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, AnyUrl

class Settings(BaseSettings):

    openai_api_key: str | None = Field(None, validation_alias="OPENAI_API_KEY")
    agno_api_key: str = Field("", validation_alias="AGNO_API_KEY")
    agno_api_url: AnyUrl = Field("https://api.agnocloud.ai", validation_alias="AGNO_API_URL")

    max_pdf_bytes: int = Field(20 * 1024 * 1024, validation_alias="MAX_PDF_BYTES")
    storage_dir: str = "pdf_text"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

