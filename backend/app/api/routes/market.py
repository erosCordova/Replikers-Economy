from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from sqlalchemy import select
from sqlalchemy.orm import (
    Session,
    selectinload,
)

from app.auth.dependencies import (
    get_current_user,
    get_db,
)
from app.models.market import (
    ReplikerTaskDecision,
)
from app.models.project import Project
from app.models.repliker import Repliker
from app.models.task import (
    Task,
    TaskBid,
)
from app.models.user import User
from app.orchestration.repliker_market import (
    evaluate_repliker_for_task,
)
from app.schemas.market import (
    DecisionPublic,
    MarketRunResponse,
    MarketSnapshotResponse,
    MarketTaskResult,
)
from app.services.activity_service import (
    record_activity,
)
from app.services.message_service import (
    record_message,
)
from app.services.agentic_service import (
    resolve_repliker_tool_names,
)
from app.services.gemini_client import (
    GeminiConfigurationError,
    GeminiResponseError,
)
from app.services.repliker_behavior_service import (
    load_repliker_behavior_context,
)
from app.services.repliker_matching_service import (
    normalize_market_text,
    rank_task_candidates,
)


router = APIRouter(
    prefix="/market",
    tags=[
        "Mercado autonomo",
    ],
)


def _find_iris(
    replikers: list[Repliker],
) -> Repliker | None:
    for repliker in replikers:
        if (
            normalize_market_text(
                repliker.name
            )
            == "iris"
            and
            normalize_market_text(
                repliker.specialty
            )
            == "product / requirements"
        ):
            return repliker

    return None


def _check_project_access(
    project: Project,
    current_user: User,
):
    if (
        project.client_id
        != current_user.id
        and current_user.role
        != "admin"
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "No tienes acceso "
                "a este proyecto."
            ),
        )


def _decision_public(
    decision:
        ReplikerTaskDecision,
    repliker: Repliker,
) -> DecisionPublic:
    return DecisionPublic(
        id=decision.id,
        task_id=
            decision.task_id,
        repliker_id=
            decision.repliker_id,
        repliker_name=
            repliker.name,
        repliker_specialty=(
            repliker.specialty
        ),
        decision=
            decision.decision,
        amount_cents=(
            decision.amount_cents
        ),
        confidence_score=(
            decision.confidence_score
        ),
        estimated_minutes=(
            decision.estimated_minutes
        ),
        message=
            decision.message,
        created_at=
            decision.created_at,
    )


def _snapshot(
    *,
    db: Session,
    project: Project,
) -> MarketSnapshotResponse:
    tasks = list(
        db.scalars(
            select(Task)
            .options(
                selectinload(
                    Task.required_skills
                ),
                selectinload(
                    Task.acceptance_criteria
                ),
            )
            .where(
                Task.project_id
                == project.id
            )
            .order_by(
                Task.id
            )
        ).all()
    )

    task_results = []

    bid_count = 0
    pass_count = 0

    for task in tasks:
        rows = db.execute(
            select(
                ReplikerTaskDecision,
                Repliker,
            )
            .join(
                Repliker,
                Repliker.id
                ==
                ReplikerTaskDecision
                .repliker_id,
            )
            .where(
                ReplikerTaskDecision
                .task_id
                == task.id
            )
            .order_by(
                ReplikerTaskDecision
                .id
            )
        ).all()

        decisions = []

        for decision, repliker in rows:
            if (
                decision.decision
                == "bid"
            ):
                bid_count += 1
            else:
                pass_count += 1

            decisions.append(
                _decision_public(
                    decision,
                    repliker,
                )
            )

        task_results.append(
            MarketTaskResult(
                task_id=task.id,
                title=task.title,
                status=task.status,
                decisions=decisions,
            )
        )

    return MarketSnapshotResponse(
        project_id=
            project.id,
        project_status=
            project.status,
        bid_count=
            bid_count,
        pass_count=
            pass_count,
        tasks=
            task_results,
    )


@router.post(
    "/projects/{project_id}/run",
    response_model=
        MarketRunResponse,
)
def run_autonomous_market(
    project_id: int,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    project = db.scalar(
        select(Project)
        .options(
            selectinload(
                Project.tasks
            ).selectinload(
                Task.required_skills
            ),
            selectinload(
                Project.tasks
            ).selectinload(
                Task.acceptance_criteria
            ),
        )
        .where(
            Project.id
            == project_id
        )
    )

    if project is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Proyecto no encontrado."
            ),
        )

    _check_project_access(
        project,
        current_user,
    )

    if not project.tasks:
        raise HTTPException(
            status_code=400,
            detail=(
                "El proyecto no "
                "contiene tareas."
            ),
        )

    eligible_tasks = [
        task
        for task
        in project.tasks
        if task.status
        in {
            "planned",
            "open",
        }
    ]

    if not eligible_tasks:
        raise HTTPException(
            status_code=400,
            detail=(
                "No existen tareas "
                "disponibles para "
                "abrir al mercado."
            ),
        )

    replikers = list(
        db.scalars(
            select(Repliker)
            .options(
                selectinload(
                    Repliker.skills
                )
            )
            .where(
                Repliker.is_active
                .is_(True),
                Repliker.is_published
                .is_(True),
                Repliker.owner_id
                != project.client_id,
            )
            .order_by(
                Repliker.id
            )
        ).all()
    )

    if not replikers:
        raise HTTPException(
            status_code=400,
            detail=(
                "No existen Replikers "
                "activos en el mercado."
            ),
        )

    iris = _find_iris(
        replikers
    )

    market_was_open = (
        project.status
        == "market_open"
    )

    for task in eligible_tasks:
        if (
            task.status
            == "planned"
        ):
            task.status = "open"

            record_activity(
                db=db,
                actor_type="system",
                event_type=(
                    "task_opened"
                ),
                project_id=
                    project.id,
                task_id=
                    task.id,
                title=(
                    "Tarea abierta "
                    "al mercado"
                ),
                description=(
                    f"{task.title} "
                    f"ya puede recibir "
                    f"decisiones y ofertas "
                    f"de Replikers."
                ),
            )

    project.status = (
        "market_open"
    )

    if not market_was_open:
        record_activity(
            db=db,
            actor_type="system",
            event_type=(
                "market_opened"
            ),
            project_id=
                project.id,
            title=(
                "Mercado autonomo abierto"
            ),
            description=(
                f"{len(eligible_tasks)} "
                f"tareas entraron en "
                f"busqueda dirigida. "
                f"Iris ofrecera cada tarea "
                f"solamente a Replikers "
                f"compatibles."
            ),
        )

        record_message(
            db=db,
            project_id=project.id,
            sender_type=(
                "repliker"
                if iris is not None
                else "market"
            ),
            sender_repliker_id=(
                iris.id
                if iris is not None
                else None
            ),
            receiver_type="replikers",
            message_type="market_open",
            content=(
                f"Ya analice el proyecto "
                f"'{project.title}'. "
                f"Voy a buscar los Replikers "
                f"mas adecuados para cada tarea "
                f"y les enviare las oportunidades "
                f"una por una."
            ),
        )

    db.commit()

    new_decisions = 0
    bid_count = 0
    pass_count = 0
    agents_considered = 0

    errors: list[str] = []

    for task in eligible_tasks:
        task_data = {
            "id":
                task.id,
            "title":
                task.title,
            "description":
                task.description,
            "required_specialty":
                task.required_specialty,
            "complexity":
                task.complexity,
            "max_budget_cents": (
                task.max_budget_cents
            ),
            "required_skills": [
                {
                    "skill_name":
                        skill.skill_name,
                    "minimum_level":
                        skill.minimum_level,
                }
                for skill
                in task.required_skills
            ],
            "acceptance_criteria": [
                criterion.description
                for criterion
                in task
                .acceptance_criteria
            ],
        }

        project_data = {
            "id":
                project.id,
            "title":
                project.title,
            "description":
                project.description,
            "currency":
                project.currency,
            "budget_limit_cents":
                project
                .budget_limit_cents,
            "quoted_amount_cents":
                project
                .quoted_amount_cents,
        }

        candidate_matches = (
            rank_task_candidates(
                task=task,
                replikers=replikers,
            )
        )

        active_bid = db.scalar(
            select(TaskBid)
            .join(
                Repliker,
                Repliker.id
                == TaskBid.repliker_id,
            )
            .where(
                TaskBid.task_id
                == task.id,

                TaskBid.status.in_(
                    (
                        "pending",
                        "accepted",
                    )
                ),

                Repliker.is_active
                .is_(True),

                Repliker.is_published
                .is_(True),

                Repliker.status
                == "available",

                Repliker.owner_id
                != project.client_id,
            )
            .order_by(
                TaskBid.id
            )
        )

        if active_bid is not None:
            db.commit()
            continue

        if not candidate_matches:
            errors.append(
                f"Tarea {task.id}: "
                f"no hay Replikers disponibles "
                f"compatibles con la "
                f"especialidad requerida."
            )

            record_activity(
                db=db,
                actor_type=(
                    "repliker"
                    if iris is not None
                    else "system"
                ),
                event_type=(
                    "candidate_search_empty"
                ),
                project_id=
                    project.id,
                task_id=
                    task.id,
                repliker_id=(
                    iris.id
                    if iris is not None
                    else None
                ),
                title=(
                    "Iris no encontro "
                    "un candidato disponible"
                ),
                description=(
                    f"La tarea '{task.title}' "
                    f"queda pendiente hasta que "
                    f"aparezca un Repliker "
                    f"compatible."
                ),
            )

            db.commit()
            continue

        for candidate in candidate_matches:
            repliker = (
                candidate.repliker
            )

            existing_decision = (
                db.scalar(
                    select(
                        ReplikerTaskDecision
                    )
                    .where(
                        ReplikerTaskDecision
                        .task_id
                        == task.id,
                        ReplikerTaskDecision
                        .repliker_id
                        == repliker.id,
                    )
                )
            )

            if existing_decision:
                continue

            existing_bid = (
                db.scalar(
                    select(TaskBid)
                    .where(
                        TaskBid.task_id
                        == task.id,
                        TaskBid.repliker_id
                        == repliker.id,
                    )
                )
            )

            if existing_bid:
                continue

            repliker_data = {
                "id":
                    repliker.id,
                "name":
                    repliker.name,
                "specialty":
                    repliker.specialty,
                "description":
                    repliker.description,
                "reputation_score":
                    repliker
                    .reputation_score,
                "jobs_completed":
                    repliker
                    .jobs_completed,
                "status":
                    repliker.status,
                "skills": [
                    {
                        "name":
                            skill.name,
                        "level":
                            skill.level,
                    }
                    for skill
                    in repliker.skills
                ],
            }

            repliker_data[
                "studio_behavior"
            ] = (
                load_repliker_behavior_context(
                    db=db,
                    repliker_id=
                        repliker.id,
                )
            )

            allowed_tool_names = (
                resolve_repliker_tool_names(
                    db=db,
                    repliker=repliker,
                )
            )

            record_activity(
                db=db,
                actor_type=(
                    "repliker"
                    if iris is not None
                    else "system"
                ),
                event_type=(
                    "task_offer_sent"
                ),
                project_id=
                    project.id,
                task_id=
                    task.id,
                repliker_id=(
                    iris.id
                    if iris is not None
                    else None
                ),
                title=(
                    f"Iris envio una "
                    f"oportunidad a "
                    f"{repliker.name}"
                ),
                description=(
                    f"Coincidencia tecnica: "
                    f"{candidate.skill_coverage:.0f}%. "
                    f"El Repliker puede aceptar "
                    f"o rechazar libremente."
                ),
            )

            record_message(
                db=db,
                project_id=
                    project.id,
                task_id=
                    task.id,
                sender_type=(
                    "repliker"
                    if iris is not None
                    else "market"
                ),
                sender_repliker_id=(
                    iris.id
                    if iris is not None
                    else None
                ),
                receiver_type=
                    "repliker",
                receiver_repliker_id=
                    repliker.id,
                message_type=
                    "task_offer",
                content=(
                    f"Hola {repliker.name}. "
                    f"Tengo una oportunidad "
                    f"que coincide con tu perfil: "
                    f"'{task.title}'. "
                    f"Revisala y decide con libertad "
                    f"si deseas presentar una oferta."
                ),
            )

            # La oferta queda guardada antes
            # de esperar la respuesta de la IA.
            db.commit()

            agents_considered += 1

            try:
                ai_decision = (
                    evaluate_repliker_for_task(
                        repliker_data=
                            repliker_data,
                        task_data=
                            task_data,
                        project_data=
                            project_data,
                        allowed_tool_names=
                            allowed_tool_names,
                    )
                )

            except (
                GeminiConfigurationError
            ) as exc:
                raise HTTPException(
                    status_code=503,
                    detail=str(exc),
                ) from exc

            except (
                GeminiResponseError
            ) as exc:
                errors.append(
                    f"Tarea {task.id} / "
                    f"Repliker "
                    f"{repliker.id}: "
                    f"{exc}"
                )

                record_activity(
                    db=db,
                    actor_type=
                        "repliker",
                    event_type=(
                        "evaluation_failed"
                    ),
                    project_id=
                        project.id,
                    task_id=
                        task.id,
                    repliker_id=
                        repliker.id,
                    title=(
                        f"{repliker.name} "
                        f"no pudo completar "
                        f"la evaluacion"
                    ),
                    description=(
                        "La evaluacion autonoma "
                        "encontro un error temporal. "
                        "Iris continuara con "
                        "el siguiente candidato."
                    ),
                )

                db.commit()
                continue

            decision = (
                ReplikerTaskDecision(
                    task_id=
                        task.id,
                    repliker_id=
                        repliker.id,
                    decision=(
                        ai_decision
                        .decision
                    ),
                    amount_cents=(
                        ai_decision
                        .amount_cents
                    ),
                    confidence_score=(
                        ai_decision
                        .confidence_score
                    ),
                    estimated_minutes=(
                        ai_decision
                        .estimated_minutes
                    ),
                    message=(
                        ai_decision
                        .message
                    ),
                    reasoning=(
                        ai_decision
                        .reasoning
                    ),
                )
            )

            db.add(
                decision
            )

            db.flush()

            new_decisions += 1

            if (
                ai_decision.decision
                == "bid"
            ):
                bid_count += 1

                bid = TaskBid(
                    task_id=
                        task.id,
                    repliker_id=
                        repliker.id,
                    amount_cents=(
                        ai_decision
                        .amount_cents
                    ),
                    confidence_score=(
                        ai_decision
                        .confidence_score
                    ),
                    estimated_minutes=(
                        ai_decision
                        .estimated_minutes
                    ),
                    message=(
                        ai_decision
                        .message
                    ),
                    status="pending",
                )

                db.add(
                    bid
                )

                amount = (
                    (
                        ai_decision
                        .amount_cents
                        or 0
                    )
                    / 100
                )

                record_activity(
                    db=db,
                    actor_type=
                        "repliker",
                    event_type=(
                        "bid_created"
                    ),
                    project_id=
                        project.id,
                    task_id=
                        task.id,
                    repliker_id=
                        repliker.id,
                    title=(
                        f"{repliker.name} "
                        f"acepto la oportunidad"
                    ),
                    description=(
                        f"Oferta: "
                        f"{project.currency} "
                        f"{amount:.2f}. "
                        f"Confianza: "
                        f"{ai_decision.confidence_score}%. "
                        f"Tiempo estimado: "
                        f"{ai_decision.estimated_minutes} "
                        f"minutos."
                    ),
                )

                record_message(
                    db=db,
                    project_id=
                        project.id,
                    task_id=
                        task.id,
                    sender_type=
                        "repliker",
                    sender_repliker_id=
                        repliker.id,
                    receiver_type=(
                        "repliker"
                        if iris is not None
                        else "market"
                    ),
                    receiver_repliker_id=(
                        iris.id
                        if iris is not None
                        else None
                    ),
                    message_type="bid",
                    content=
                        ai_decision.message,
                )

                db.commit()

                # Una oferta valida detiene la
                # busqueda para esta tarea.
                break

            pass_count += 1

            record_activity(
                db=db,
                actor_type=
                    "repliker",
                event_type=(
                    "task_passed"
                ),
                project_id=
                    project.id,
                task_id=
                    task.id,
                repliker_id=
                    repliker.id,
                title=(
                    f"{repliker.name} "
                    f"rechazo la oportunidad"
                ),
                description=(
                    f"El Repliker decidio "
                    f"no presentar una oferta "
                    f"para '{task.title}'. "
                    f"Iris continuara con "
                    f"el siguiente candidato."
                ),
            )

            record_message(
                db=db,
                project_id=
                    project.id,
                task_id=
                    task.id,
                sender_type=
                    "repliker",
                sender_repliker_id=
                    repliker.id,
                receiver_type=(
                    "repliker"
                    if iris is not None
                    else "market"
                ),
                receiver_repliker_id=(
                    iris.id
                    if iris is not None
                    else None
                ),
                message_type="pass",
                content=
                    ai_decision.message,
            )

            db.commit()

    if (
        new_decisions > 0
        or errors
    ):
        record_activity(
            db=db,
            actor_type="system",
            event_type=(
                "market_cycle_completed"
            ),
            project_id=
                project.id,
            title=(
                "Ciclo del mercado "
                "completado"
            ),
            description=(
                f"{new_decisions} nuevas "
                f"decisiones procesadas. "
                f"{bid_count} ofertas, "
                f"{pass_count} rechazos "
                f"y {len(errors)} errores."
            ),
        )

        record_message(
            db=db,
            project_id=project.id,
            sender_type="market",
            receiver_type="r00",
            message_type="market_summary",
            content=(
                f"El ciclo del mercado termino. "
                f"Se procesaron {new_decisions} "
                f"nuevas decisiones: "
                f"{bid_count} ofertas, "
                f"{pass_count} rechazos y "
                f"{len(errors)} errores."
            ),
        )

        db.commit()

    snapshot = _snapshot(
        db=db,
        project=project,
    )

    return MarketRunResponse(
        project_id=
            project.id,
        project_status=(
            project.status
        ),
        tasks_processed=
            len(
                eligible_tasks
            ),
        agents_considered=
            agents_considered,
        new_decisions=
            new_decisions,
        bid_count=
            snapshot.bid_count,
        pass_count=
            snapshot.pass_count,
        errors=
            errors,
        tasks=
            snapshot.tasks,
    )


@router.get(
    "/projects/{project_id}",
    response_model=
        MarketSnapshotResponse,
)
def get_market_snapshot(
    project_id: int,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    project = db.get(
        Project,
        project_id,
    )

    if project is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Proyecto no encontrado."
            ),
        )

    _check_project_access(
        project,
        current_user,
    )

    return _snapshot(
        db=db,
        project=project,
    )
