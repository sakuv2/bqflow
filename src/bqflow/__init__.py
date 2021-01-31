__version__ = "0.1.1"

from pathlib import Path

from pydantic import BaseSettings


class Env(BaseSettings):
    GOOGLE_APPLICATION_CREDENTIALS: Path

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


env = Env()
