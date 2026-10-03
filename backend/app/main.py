from contextlib import (
    asynccontextmanager,
)

from fastapi import FastAPI
from fastapi.middleware.cors import (
    CORSMiddleware,
)

from app.api.routes.auth import (
    router as auth_router,
)
from app.api.routes.users import (
    router as users_router,
)
from app.api.routes.replikers import (
    router as replikers_router,
)
from app.api.routes.projects import (
    router as projects_router,
)
from app.api.routes.tasks import (
    router as tasks_router,
)
from app.api.routes.coordinator import (
    router as coordinator_router,
)
from app.api.routes.market import (
    router as market_router,
)
from app.api.routes.ecosystem import (
    router as ecosystem_router,
)
from app.api.routes.contracts import (
    router as contracts_router,
)
from app.api.routes.collaboration import (
    router as collaboration_router,
)
from app.api.routes.delegations import (
    router as delegations_router,
)
from app.api.routes.agentic import (
    router as agentic_router,
)
from app.api.routes.execution import (
    router as execution_router,
)
from app.api.routes.execution_agent import (
    router as execution_agent_router,
)
from app.api.routes.qa import (
    router as qa_router,
)
from app.api.routes.economy import (
    router as economy_router,
)
from app.api.routes.realtime import (
    router as realtime_router,
)

from app.core.config import settings
from app.database.migrations import (
    assert_database_migrations_current,
)
from app.database.session import engine
from app.middleware.security_headers import (
    SecurityHeadersMiddleware,
)


@asynccontextmanager
async def lifespan(
    _: FastAPI,
):
    if (
        settings.ENVIRONMENT
        == "production"
    ):
        settings.assert_production_ready()

        assert_database_migrations_current(
            engine
        )

    yield


app = FastAPI(
    title="Repliker Economy API",
    version="1.7.0",
    description=(
        "Backend de Repliker Economy: "
        "LangChain para agentes y tools, "
        "LangGraph para orquestacion, "
        "mercado, contratacion, delegacion, "
        "ejecucion aislada, QA verificable, "
        "economia simulada con ledger, "
        "PostgreSQL y seguridad endurecida."
    ),
    lifespan=lifespan,
)


app.add_middleware(
    SecurityHeadersMiddleware,
    production=(
        settings.ENVIRONMENT
        == "production"
    ),
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=
        settings.cors_origins,
    allow_credentials=True,
    allow_methods=[
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "OPTIONS",
    ],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "Last-Event-ID",
    ],
)


app.include_router(
    auth_router,
    prefix="/api/v1",
)

app.include_router(
    users_router,
    prefix="/api/v1",
)

app.include_router(
    replikers_router,
    prefix="/api/v1",
)

app.include_router(
    projects_router,
    prefix="/api/v1",
)

app.include_router(
    tasks_router,
    prefix="/api/v1",
)

app.include_router(
    coordinator_router,
    prefix="/api/v1",
)

app.include_router(
    market_router,
    prefix="/api/v1",
)

app.include_router(
    ecosystem_router,
    prefix="/api/v1",
)

app.include_router(
    contracts_router,
    prefix="/api/v1",
)

app.include_router(
    collaboration_router,
    prefix="/api/v1",
)

app.include_router(
    delegations_router,
    prefix="/api/v1",
)

app.include_router(
    agentic_router,
    prefix="/api/v1",
)

app.include_router(
    execution_router,
    prefix="/api/v1",
)

app.include_router(
    execution_agent_router,
    prefix="/api/v1",
)

app.include_router(
    qa_router,
    prefix="/api/v1",
)

app.include_router(
    economy_router,
    prefix="/api/v1",
)

app.include_router(
    realtime_router,
    prefix="/api/v1",
)


@app.get("/api/v1/health")
def health():
    return {
        "status":
            "ok",
        "service":
            "backend",
        "version":
            "1.7.0",
        "environment":
            settings.ENVIRONMENT,
        "database_schema":
            "alembic",
        "agentic_framework":
            "LangChain + LangGraph",
        "qa":
            "enabled",
        "economy":
            "simulation",
        "real_money":
            False,
    }


@app.get("/")
def root():
    return {
        "name":
            "Repliker Economy",
        "status":
            "online",
        "api":
            "/api/v1",
        "environment":
            settings.ENVIRONMENT,
        "database_schema":
            "alembic",
        "agentic_framework":
            "LangChain + LangGraph",
        "qa":
            "enabled",
        "economy":
            "simulation",
        "real_money":
            False,
    }
