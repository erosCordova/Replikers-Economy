from typing import Literal

from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


EnvironmentName = Literal[
    "development",
    "test",
    "production",
]


class Settings(BaseSettings):
    APP_NAME: str = (
        "Repliker Economy"
    )

    API_V1_PREFIX: str = (
        "/api/v1"
    )

    ENVIRONMENT: EnvironmentName = (
        "development"
    )

    # --------------------------------------------------------
    # Database
    # --------------------------------------------------------

    DATABASE_URL: str = (
        "sqlite:///./replikers.db"
    )

    DB_POOL_PRE_PING: bool = True

    DB_POOL_RECYCLE_SECONDS: int = (
        300
    )

    # --------------------------------------------------------
    # Security
    # --------------------------------------------------------

    SECRET_KEY: str

    ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = (
        1440
    )

    FRONTEND_URL: str = (
        "http://localhost:5173"
    )

    # --------------------------------------------------------
    # Inteligencia artificial
    # --------------------------------------------------------

    GEMINI_API_KEY: str = ""

    GEMINI_MODEL: str = (
        "gemini-3.8-flash"
    )

    # --------------------------------------------------------
    # Economia
    # --------------------------------------------------------
    # Replikers continua trabajando
    # EXCLUSIVAMENTE con dinero ficticio.
    # El paso a dinero real solo se activara
    # mediante una decision posterior explicita.
    # --------------------------------------------------------

    ECONOMY_MODE: str = (
        "simulation"
    )

    REAL_PAYMENTS_ENABLED: bool = (
        False
    )

    # 1000 basis points = 10 %
    # Politica temporal de simulacion.
    PLATFORM_COMMISSION_BPS: int = (
        1000
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
