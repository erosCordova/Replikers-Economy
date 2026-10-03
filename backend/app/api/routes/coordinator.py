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
from app.models.project import Project
from app.models.repliker import Repliker
from app.models.task import (
    Task,
    TaskAcceptanceCriterion,
    TaskSkillRequirement,
)
from app.models.user import User
from app.orchestration.coordinator import (
    build_project_plan,
)
from app.replikers.catalogo_web import (
    get_web_repliker,
)
from app.schemas.coordinator import (
    CoordinatorPlanResponse,
    PlannedTaskResponse,
)
from app.services.activity_service import (
    record_activity,
)
from app.services.gemini_client import (
    GeminiConfigurationError,
    GeminiResponseError,
)
from app.services.message_service import (
    record_message,
)
from app.services.web_repliker_registry_service import (
    ECOSYSTEM_OWNER_EMAIL,
)


router = APIRouter(
    prefix="/coordinator",
    tags=["Coordinador IA"],
)


def _get_official_iris(
    db: Session,
) -> Repliker:
    definition = get_web_repliker(
        "product_requirements"
    )

    if definition is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "La definicion oficial de Iris "
                "no esta disponible."
            ),
        )

    owner = db.scalar(
        select(User)
        .where(
            User.email
            == ECOSYSTEM_OWNER_EMAIL
        )
    )

    if owner is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "El ecosistema oficial de "
                "Replikers no esta inicializado."
            ),
        )

    iris = db.scalar(
        select(Repliker)
        .options(
            selectinload(
                Repliker.skills
            )
        )
        .where(
            Repliker.owner_id == owner.id,
            Repliker.name == definition.name,
            Repliker.is_active.is_(True),
        )
    )

    if iris is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Iris no esta disponible "
                "en el ecosistema."
            ),
        )

    return iris


@router.post(
    "/projects/{project_id}/plan",
    response_model=CoordinatorPlanResponse,
)
def plan_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):
    statement = (
        select(Project)
        .options(
            selectinload(
                Project.requirements
            ),
            selectinload(
                Project.tasks
            ),
        )
        .where(
            Project.id == project_id
        )
    )

    project = db.scalar(
        statement
    )

    if project is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Proyecto no encontrado."
            ),
        )

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

    if project.tasks:
        raise HTTPException(
            status_code=409,
            detail=(
                "El proyecto ya contiene tareas."
            ),
        )

    iris = _get_official_iris(
        db
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
        ).all()
    )

    marketplace_data = [
        {
            "id":
                repliker.id,
            "name":
                repliker.name,
            "specialty":
                repliker.specialty,
            "reputation":
                repliker.reputation_score,
            "jobs_completed":
                repliker.jobs_completed,
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
        for repliker
        in replikers
    ]

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
            project.budget_limit_cents,
        "requirements": [
            {
                "title":
                    requirement.title,
                "description":
                    requirement.description,
                "mandatory":
                    requirement.is_mandatory,
            }
            for requirement
            in project.requirements
        ],
    }

    try:
        plan = build_project_plan(
            project_data=
                project_data,
            marketplace_data=
                marketplace_data,
        )

    except GeminiConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    except GeminiResponseError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    created_task_ids: list[int] = []

    for planned_task in plan.tasks:
        task = Task(
            project_id=
                project.id,
            title=
                planned_task.title,
            description=
                planned_task.description,
            required_specialty=(
                planned_task
                .required_specialty
                .strip()
            ),
            status=
                "planned",
            complexity=
                planned_task.complexity,
            max_budget_cents=(
                planned_task
                .max_budget_cents
            ),
        )

        db.add(task)
        db.flush()

        created_task_ids.append(
            task.id
        )

        for skill in (
            planned_task
            .required_skills
        ):
            db.add(
                TaskSkillRequirement(
                    task_id=
                        task.id,
                    skill_name=
                        skill.skill_name,
                    minimum_level=
                        skill.minimum_level,
                )
            )

        for criterion in (
            planned_task
            .acceptance_criteria
        ):
            db.add(
                TaskAcceptanceCriterion(
                    task_id=
                        task.id,
                    description=
                        criterion,
                    status=
                        "pending",
                    is_mandatory=
                        True,
                )
            )

        record_activity(
            db=db,
            actor_type="repliker",
            event_type="task_created",
            project_id=project.id,
            task_id=task.id,
            repliker_id=iris.id,
            title=(
                "Iris definio una tarea"
            ),
            description=(
                f"{task.title}. "
                f"Especialidad: "
                f"{task.required_specialty}. "
                f"Complejidad: "
                f"{task.complexity}/100. "
                f"Presupuesto maximo: "
                f"{project.currency} "
                f"{task.max_budget_cents / 100:.2f}."
            ),
        )

    planned_budget = sum(
        planned_task
        .max_budget_cents
        for planned_task
        in plan.tasks
    )

    project.quoted_amount_cents = (
        planned_budget
    )

    project.status = "planned"

    mandatory_specialists = [
        specialist
        for specialist
        in plan.required_specialists
        if specialist.mandatory
    ]

    record_activity(
        db=db,
        actor_type="repliker",
        event_type=
            "project_planned",
        project_id=
            project.id,
        repliker_id=
            iris.id,
        title=(
            "Iris termino el analisis "
            "del proyecto"
        ),
        description=(
            f"Se definieron "
            f"{len(plan.tasks)} tareas y "
            f"{len(mandatory_specialists)} "
            f"especialidades obligatorias. "
            f"Presupuesto planificado: "
            f"{project.currency} "
            f"{planned_budget / 100:.2f}."
        ),
    )

    record_message(
        db=db,
        project_id=
            project.id,
        sender_type=
            "repliker",
        sender_repliker_id=
            iris.id,
        receiver_type=
            "project",
        message_type=
            "planning_summary",
        content=(
            f"Ya termine de organizar "
            f"'{project.title}'. "
            f"{plan.summary} "
            f"Identifique "
            f"{len(mandatory_specialists)} "
            f"especialidades obligatorias "
            f"y prepare "
            f"{len(plan.tasks)} tareas. "
            f"El siguiente paso es buscar "
            f"Replikers compatibles."
        ),
    )

    db.commit()

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
                Task.id.in_(
                    created_task_ids
                )
            )
            .order_by(
                Task.id
            )
        ).all()
    )

    response_tasks = []

    for task in tasks:
        criteria = [
            criterion.description
            for criterion
            in task.acceptance_criteria
        ]

        response_tasks.append(
            PlannedTaskResponse(
                task=task,
                acceptance_criteria=
                    criteria,
            )
        )

    return CoordinatorPlanResponse(
        project_id=
            project.id,
        coordinator=
            iris.name,
        summary=
            plan.summary,
        strategy=
            plan.strategy,
        planned_budget_cents=
            planned_budget,
        client_budget_cents=(
            project.budget_limit_cents
        ),
        required_specialists=(
            plan.required_specialists
        ),
        market_gaps=
            plan.market_gaps,
        tasks=
            response_tasks,
    )
