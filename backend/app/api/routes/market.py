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


router = APIRouter(
    prefix="/market",
    tags=[
        "Mercado autonomo",
    ],
)


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
                f"tareas fueron puestas "
                f"a disposicion de "
                f"{len(replikers)} "
                f"Replikers activos."
            ),
        )

        record_message(
            db=db,
            project_id=project.id,
            sender_type="market",
            receiver_type="replikers",
            message_type="market_open",
            content=(
                f"El proyecto '{project.title}' "
                f"ha abierto {len(eligible_tasks)} "
                f"tareas al mercado. "
                f"Los Replikers disponibles ya "
                f"pueden evaluarlas."
            ),
        )

    db.commit()

    new_decisions = 0
    bid_count = 0
    pass_count = 0

    errors: list[str] = []

    for task in eligible_tasks:
        task_data = {
            "id":
                task.id,
            "title":
                task.title,
            "description":
                task.description,
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

        for repliker in replikers:
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

            allowed_tool_names = (
                resolve_repliker_tool_names(
                    db=db,
                    repliker=repliker,
                )
            )

            # existing_decision, existing_bid y la resolución
            # de herramientas son solamente lecturas.
            # Cerramos esa transacción antes de esperar
            # al modelo para no dejar PostgreSQL bloqueado.
            db.commit()

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
                error_text = (
                    f"Task {task.id} / "
                    f"Repliker "
                    f"{repliker.id}: "
                    f"{exc}"
                )

                errors.append(
                    error_text
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
                        "La evaluacion "
                        "autonoma de la "
                        "tarea encontro "
                        "un error temporal."
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
                        f"envio una oferta"
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
                    project_id=project.id,
                    task_id=task.id,
                    sender_type="repliker",
                    sender_repliker_id=repliker.id,
                    receiver_type="r00",
                    message_type="bid",
                    content=ai_decision.message,
                )

            else:
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
                        f"decidio no ofertar"
                    ),
                    description=(
                        f"El Repliker evaluo "
                        f"la tarea "
                        f"'{task.title}' y "
                        f"decidio no competir "
                        f"por ella. "
                        f"Confianza declarada: "
                        f"{ai_decision.confidence_score}%."
                    ),
                )

                record_message(
                    db=db,
                    project_id=project.id,
                    task_id=task.id,
                    sender_type="repliker",
                    sender_repliker_id=repliker.id,
                    receiver_type="r00",
                    message_type="pass",
                    content=ai_decision.message,
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
            len(
                replikers
            ),
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
