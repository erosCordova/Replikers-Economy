from typing import Literal
from urllib.parse import urlparse

from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


EnvironmentName = Literal[
    "development",
    "test",
    "production",
]

CookieSameSite = Literal[
    "lax",
    "strict",
    "none",
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
    # Security / JWT
    # --------------------------------------------------------

    SECRET_KEY: str

    ALGORITHM: Literal[
        "HS256"
    ] = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = (
        15
    )

    JWT_ISSUER: str = (
        "repliker-economy"
    )

    JWT_AUDIENCE: str = (
        "repliker-economy-api"
    )

    JWT_LEEWAY_SECONDS: int = (
        5
    )

    # --------------------------------------------------------
    # Refresh sessions
    # --------------------------------------------------------

    REFRESH_TOKEN_EXPIRE_DAYS: int = (
        14
    )

    REFRESH_COOKIE_NAME: str = (
        "repliker_refresh"
    )

    REFRESH_COOKIE_PATH: str = (
        "/api/v1/auth"
    )

    REFRESH_COOKIE_DOMAIN: str = ""

    REFRESH_COOKIE_SAMESITE: CookieSameSite = (
        "lax"
    )

    REFRESH_COOKIE_SECURE: bool = (
        False
    )

    MAX_ACTIVE_SESSIONS_PER_USER: int = (
        5
    )

    AUTH_SESSION_HISTORY_DAYS: int = (
        30
    )

    AUTH_LOGIN_IP_MAX_REQUESTS: int = (
        30
    )

    AUTH_LOGIN_IDENTITY_MAX_REQUESTS: int = (
        10
    )

    AUTH_LOGIN_WINDOW_SECONDS: int = (
        300
    )

    AUTH_LOGIN_BLOCK_SECONDS: int = (
        900
    )

    AUTH_REGISTER_MAX_REQUESTS: int = (
        5
    )

    AUTH_REGISTER_WINDOW_SECONDS: int = (
        600
    )

    AUTH_REGISTER_BLOCK_SECONDS: int = (
        1800
    )

    AUTH_REFRESH_MAX_REQUESTS: int = (
        60
    )

    AUTH_REFRESH_WINDOW_SECONDS: int = (
        60
    )

    AUTH_REFRESH_BLOCK_SECONDS: int = (
        300
    )

    # --------------------------------------------------------
    # Web / CORS
    # --------------------------------------------------------

    FRONTEND_URL: str = (
        "http://localhost:5173"
    )

    CORS_ALLOWED_ORIGINS: str = ""

    ALLOW_INSECURE_LOCAL_ORIGINS: bool = (
        False
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

    ECONOMY_MODE: str = (
        "simulation"
    )

    REAL_PAYMENTS_ENABLED: bool = (
        False
    )

    PLATFORM_COMMISSION_BPS: int = (
        1000
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def refresh_cookie_secure(
        self,
    ) -> bool:
        return (
            self.REFRESH_COOKIE_SECURE
            or self.ENVIRONMENT
            == "production"
        )

    @property
    def cors_origins(
        self,
    ) -> list[str]:
        candidates: list[str] = []

        if self.FRONTEND_URL.strip():
            candidates.append(
                self.FRONTEND_URL
                .strip()
                .rstrip("/")
            )

        if (
            self.CORS_ALLOWED_ORIGINS
            .strip()
        ):
            candidates.extend(
                origin.strip().rstrip("/")
                for origin
                in self
                .CORS_ALLOWED_ORIGINS
                .split(",")
                if origin.strip()
            )

        if (
            self.ENVIRONMENT
            != "production"
        ):
            candidates.extend(
                [
                    "http://localhost:5173",
                    "http://127.0.0.1:5173",
                ]
            )

        result: list[str] = []

        for origin in candidates:
            if (
                origin
                and origin not in result
            ):
                result.append(
                    origin
                )

        return result

    def production_security_issues(
        self,
    ) -> list[str]:
        if (
            self.ENVIRONMENT
            != "production"
        ):
            return []

        issues: list[str] = []

        if len(
            self.SECRET_KEY
        ) < 48:
            issues.append(
                "SECRET_KEY debe tener "
                "al menos 48 caracteres."
            )

        if not (
            5
            <= self.ACCESS_TOKEN_EXPIRE_MINUTES
            <= 60
        ):
            issues.append(
                "ACCESS_TOKEN_EXPIRE_MINUTES "
                "debe estar entre 5 y 60."
            )

        if not (
            1
            <= self.REFRESH_TOKEN_EXPIRE_DAYS
            <= 30
        ):
            issues.append(
                "REFRESH_TOKEN_EXPIRE_DAYS "
                "debe estar entre 1 y 30."
            )

        if not (
            self.DATABASE_URL
            .lower()
            .startswith(
                (
                    "postgres://",
                    "postgresql://",
                    "postgresql+psycopg://",
                )
            )
        ):
            issues.append(
                "Produccion requiere PostgreSQL."
            )

        if not self.cors_origins:
            issues.append(
                "Debe existir al menos un "
                "origen CORS permitido."
            )

        if "*" in self.cors_origins:
            issues.append(
                "CORS no puede usar '*' "
                "en produccion."
            )

        for origin in self.cors_origins:
            parsed = urlparse(
                origin
            )

            local = (
                parsed.hostname
                in {
                    "localhost",
                    "127.0.0.1",
                }
            )

            if (
                parsed.scheme != "https"
                and not (
                    local
                    and self
                    .ALLOW_INSECURE_LOCAL_ORIGINS
                )
            ):
                issues.append(
                    "Los origenes CORS de "
                    "produccion deben usar HTTPS."
                )

                break

        if (
            self.REFRESH_COOKIE_SAMESITE
            == "none"
            and not self
            .refresh_cookie_secure
        ):
            issues.append(
                "SameSite=None requiere "
                "una cookie Secure."
            )

        if (
            self.ECONOMY_MODE
            != "simulation"
        ):
            issues.append(
                "ECONOMY_MODE debe permanecer "
                "en simulation."
            )

        if self.REAL_PAYMENTS_ENABLED:
            issues.append(
                "REAL_PAYMENTS_ENABLED debe "
                "permanecer desactivado."
            )

        return issues

    def assert_production_ready(
        self,
    ) -> None:
        issues = (
            self
            .production_security_issues()
        )

        if issues:
            raise RuntimeError(
                "Configuracion de produccion "
                "insegura: "
                + " ".join(
                    issues
                )
            )


settings = Settings()
