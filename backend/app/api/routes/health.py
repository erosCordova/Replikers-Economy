from fastapi import (
    APIRouter,
    Response,
    status,
)

from app.core.config import settings
from app.core.version import (
    APP_VERSION,
)
from app.services.health_service import (
    check_readiness,
)


router = APIRouter(
    prefix="/health",
    tags=[
        "Health",
    ],
)


@router.get(
    "/live",
)
def live():
    return {
        "status": "ok",
        "service":
            "backend",
        "version":
            APP_VERSION,
        "environment":
            settings.ENVIRONMENT,
    }


@router.get(
    "/ready",
)
def ready(
    response: Response,
):
    result = (
        check_readiness()
    )

    if not result.ready:
        response.status_code = (
            status
            .HTTP_503_SERVICE_UNAVAILABLE
        )

    return {
        "status": (
            "ready"
            if result.ready
            else "not_ready"
        ),
        "service":
            "backend",
        "version":
            APP_VERSION,
        "database":
            result.database,
        "migrations":
            result.migrations,
    }
