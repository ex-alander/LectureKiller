"""Configuration management using environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, PositiveFloat, PositiveInt
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Configuration
    api_base_url: str = Field(..., alias="API_BASE_URL")
    api_key: str = Field(..., alias="API_KEY")
    model_name: str = Field("gpt-5.4", alias="MODEL_NAME")

    # API Parameters
    max_completion_tokens: PositiveInt = Field(16384, alias="MAX_COMPLETION_TOKENS")
    temperature: PositiveFloat = Field(0.2, alias="TEMPERATURE")
    max_retries: PositiveInt = Field(2, alias="MAX_RETRIES")
    retry_delay_seconds: PositiveFloat = Field(5.0, alias="RETRY_DELAY_SECONDS")
    request_delay_seconds: PositiveFloat = Field(2.0, alias="REQUEST_DELAY_SECONDS")

    # Image Processing
    pdf_dpi: PositiveInt = Field(200, alias="PDF_DPI")
    image_quality: PositiveInt = Field(85, alias="IMAGE_QUALITY")
    max_image_size: PositiveInt = Field(1024, alias="MAX_IMAGE_SIZE")

    # Paths
    input_dir: Path = Field(Path("./input_pdfs"), alias="INPUT_DIR")
    output_dir: Path = Field(Path("./output_markdown"), alias="OUTPUT_DIR")
    temp_images_dir: Path = Field(Path("./temp_images"), alias="TEMP_IMAGES_DIR")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
        "protected_namespaces": ("settings_",),
    }


@lru_cache
def get_settings() -> Settings:
    """Return cached settings singleton."""
    return Settings()