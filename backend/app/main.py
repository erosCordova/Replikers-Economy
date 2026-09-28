from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.projects import router as projects_router
from app.api.routes.replikers import router as replikers_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.users import router as users_router

from app.core.config import settings
from app.database.base import Base
from app.database.session import engine

import app.models


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(
        bind=engine
    )

    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="0.4.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "app": settings.APP_NAME,
        "version": "0.4.0",
        "status": "online",
    }


@app.get("/api/v1/health")
def health():
    return {
        "status": "ok",
        "service": "backend",
    }


app.include_router(
    auth_router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    users_router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    replikers_router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    projects_router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    tasks_router,
    prefix=settings.API_V1_PREFIX,
)
