import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    MAX_CONCURRENT_JOBS: int = 2
    MAX_FILE_SIZE_MB: int = 50
    JOB_TIMEOUT_SECONDS: int = 300
    QUEUE_WAIT_SECONDS: int = 30
    OCR_LANGUAGES: str = "eng"
    OCRMYPDF_JOBS: int = os.cpu_count() or 1
    LOG_LEVEL: str = "INFO"
    TEMP_DIR: str = "/tmp"


def get_settings() -> Settings:
    return Settings()
