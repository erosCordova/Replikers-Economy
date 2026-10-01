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

from app.database.base import Base
from app.database.session import engine

import app.models  # noqa: F401


Base.metadata.create_all(
    bind=engine
)


app = FastAPI(
    title="Repliker Economy API",
    version="1.1.0",
    description=(
        "Backend de Repliker Economy: "
        "coordinacion, mercado, contratacion, "
        "colaboracion, delegacion, ecosistema "
        "y economia autonoma de agentes."
    ),
)


allowed_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


@app.get("/api/v1/health")
def health():
    return {
        "status": "ok",
        "service": "backend",
        "version": "1.1.0",
    }


@app.get("/")
def root():
    return {
        "name": "Repliker Economy",
        "status": "online",
        "api": "/api/v1",
    }
