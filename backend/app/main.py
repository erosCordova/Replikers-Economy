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




from app.api.routes.repliker_developer import (




    router as repliker_developer_router,




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




from app.api.routes.health import (




    router as health_router,




)









from app.core.config import settings




from app.core.version import (




    APP_VERSION,




)




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




    version=APP_VERSION,




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




    health_router,




    prefix="/api/v1",




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




    repliker_developer_router,




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














@app.get(




    "/api/v1/health"




)




def health():




    return {




        "status":




            "ok",




        "service":




            "backend",




        "version":




            APP_VERSION,




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




        "version":




            APP_VERSION,




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












# REPLIKERS_WORLD_OWNER_READ_API_V1



from app.api.routes.world_read import router as world_owner_router



app.include_router(world_owner_router, prefix='/api/v1')









# REPLIKERS_WORLD_AUTONOMY_POLICY_V1


from app.api.routes.world_autonomy import router as world_autonomy_router


app.include_router(world_autonomy_router, prefix='/api/v1')






# REPLIKERS_WORLD_OBSERVABILITY_V1

from app.api.routes.world_observability import router as world_observability_router

app.include_router(world_observability_router, prefix='/api/v1')



# REPLIKERS_WORLD_EVENTS_V1
from app.api.routes.world_events import router as world_events_router
app.include_router(world_events_router, prefix='/api/v1')

# REPLIKERS_WORLD_SCHEDULER_STATUS_V1
from app.api.routes.world_scheduler_status import (
    router as world_scheduler_status_router,
)
app.include_router(
    world_scheduler_status_router,
    prefix="/api/v1",
)

# REPLIKERS_WORLD_LIFECYCLE_V1
from contextlib import asynccontextmanager as _rw_asynccontextmanager
from app.agentic.world_scheduler_lifecycle import (
    configured_world_scheduler_lifecycle as _rw_scheduler_lifecycle,
)

_rw_previous_lifespan = app.router.lifespan_context

@_rw_asynccontextmanager
async def _rw_lifespan_with_supervisor(current_app):
    async with _rw_previous_lifespan(current_app):
        with _rw_scheduler_lifecycle(
            engine, settings.ENVIRONMENT
        ):
            yield

app.router.lifespan_context = _rw_lifespan_with_supervisor


# RW_LEDGER_DIRECT_REGISTRATION_V3

from app.api.routes.world_events import (
    rw_my_world_ledger as _rw_ledger_handler,
)

_rw_ledger_path = (
    "/api/v1/world/events/economy/ledger/mine"
)

if not any(
    getattr(route, "path", None) == _rw_ledger_path
    and "GET" in getattr(route, "methods", set())
    for route in app.routes
):
    app.add_api_route(
        _rw_ledger_path,
        _rw_ledger_handler,
        methods=["GET"],
        tags=["World Economic Ledger"],
        name="rw_world_economic_ledger",
    )


# RW_WORLD_DIRECT_GET_REGISTRATION_V4
# Registrar rutas GET originales, sin exponer POST/PUT/DELETE.

from importlib import import_module as _rw_import_v4
from fastapi import APIRouter as _RWRouterV4
from fastapi.routing import APIRoute as _RWRouteV4

_rw_modules_v4 = ('app.api.routes.world_autonomy', 'app.api.routes.world_events', 'app.api.routes.world_observability', 'app.api.routes.world_read', 'app.api.routes.world_scheduler_status')

_rw_registered_v4 = {
    (route.path, method)
    for route in app.routes
    if isinstance(route, _RWRouteV4)
    for method in (route.methods or set())
}

_rw_seen_routers_v4 = set()

for _rw_module_name_v4 in _rw_modules_v4:

    _rw_module_v4 = _rw_import_v4(
        _rw_module_name_v4
    )

    for _rw_router_v4 in vars(
        _rw_module_v4
    ).values():

        if not isinstance(
            _rw_router_v4, _RWRouterV4
        ):
            continue

        if id(_rw_router_v4) in _rw_seen_routers_v4:
            continue

        _rw_seen_routers_v4.add(
            id(_rw_router_v4)
        )

        for _rw_route_v4 in _rw_router_v4.routes:

            if not isinstance(
                _rw_route_v4, _RWRouteV4
            ):
                continue

            _rw_methods_v4 = set(
                _rw_route_v4.methods or ()
            )

            if (
                "GET" not in _rw_methods_v4
                or not _rw_methods_v4.issubset(
                    {"GET", "HEAD"}
                )
            ):
                continue

            _rw_path_v4 = _rw_route_v4.path

            if _rw_path_v4.startswith(
                "/api/v1/world/"
            ):
                _rw_target_v4 = _rw_path_v4

            elif _rw_path_v4.startswith(
                "/world/"
            ):
                _rw_target_v4 = (
                    "/api/v1" + _rw_path_v4
                )

            else:
                continue

            if (
                _rw_target_v4,
                "GET",
            ) in _rw_registered_v4:
                continue

            # Registro directo probado anteriormente
            # con el endpoint economico.
            #
            # Conservar Depends del endpoint,
            # dependencias del router y response_model.
            app.add_api_route(
                path=_rw_target_v4,
                endpoint=_rw_route_v4.endpoint,
                methods=["GET"],
                dependencies=list(
                    _rw_route_v4.dependencies
                ),
                response_model=(
                    _rw_route_v4.response_model
                ),
                response_class=(
                    _rw_route_v4.response_class
                ),
                status_code=(
                    _rw_route_v4.status_code
                ),
                tags=list(
                    _rw_route_v4.tags or []
                ),
                summary=_rw_route_v4.summary,
                description=_rw_route_v4.description,
                responses=_rw_route_v4.responses,
                deprecated=_rw_route_v4.deprecated,
                include_in_schema=(
                    _rw_route_v4.include_in_schema
                ),
                name=_rw_route_v4.name,
            )

            _rw_registered_v4.add((
                _rw_target_v4,
                "GET",
            ))


# RW_LIVE_SUPERVISOR_DIRECT_HTTP_V3
# Registro directo: evita el problema de _IncludedRouter.
from app.api.routes import world_live_supervisor_http as _rw_live_http

_rw_live_http_prefix = (
    "/api/v1/world/scheduler/live/control/mine"
)

app.add_api_route(
    _rw_live_http_prefix,
    _rw_live_http.my_control_status,
    methods=["GET"],
    tags=["Replikers World - Supervisor"],
)

app.add_api_route(
    _rw_live_http_prefix + "/start",
    _rw_live_http.start_my_supervisor,
    methods=["POST"],
    tags=["Replikers World - Supervisor"],
)

app.add_api_route(
    _rw_live_http_prefix + "/stop",
    _rw_live_http.stop_my_supervisor,
    methods=["POST"],
    tags=["Replikers World - Supervisor"],
)
