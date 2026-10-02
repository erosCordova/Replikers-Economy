from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agentic.qa_retry_graph import (
    decide_qa_followup,
)
from app.models.contract import (
    TaskContract,
)
from app.models.qa import (
    QACriterionResult,
    QAReview,
)
from app.models.qa_workflow import (
    QAReputationEvent,
    QARetryRun,
)
from app.models.repliker import (
    Repliker,
)
from app.models.task import (
    TaskAcceptanceCriterion,
)
from app.services.execution_agent_service import (
    run_contract_execution,
)
from app.services.qa_service import (
    prepare_qa_review,
)


MAX_QA_ATTEMPTS = 3


class QAWorkflowError(
    ValueError
):
    pass


def _contract_for_review(
    *,
    db: Session,
    review: QAReview,
) -> TaskContract:
    contract = db.get(
        TaskContract,
        review.contract_id,
    )

    if contract is None:
        raise QAWorkflowError(
            "Contrato QA no encontrado."
        )

    return contract


def _reputation_delta(
    *,
    review: QAReview,
) -> int:
    if review.status == "passed":
        return (
            2
            if review.attempt_number == 1
            else 1
        )

    if review.status == "failed":
        return -1

    if review.status == "needs_review":
        return 0

    raise QAWorkflowError(
        "La revision QA aun no tiene "
        "un resultado final."
    )


def apply_reputation_for_review(
    *,
    db: Session,
    review: QAReview,
) -> QAReputationEvent:
    existing = db.scalar(
        select(
            QAReputationEvent
        )
        .where(
            QAReputationEvent.review_id
            == review.id
        )
    )

    if existing is not None:
        return existing

    if review.status not in {
        "passed",
        "failed",
        "needs_review",
    }:
        raise QAWorkflowError(
            "No se puede actualizar "
            "reputacion desde una "
            "revision no finalizada."
        )

    contract = _contract_for_review(
        db=db,
        review=review,
    )

    repliker = db.get(
        Repliker,
        contract.repliker_id,
    )

    if repliker is None:
        raise QAWorkflowError(
            "Repliker del contrato "
            "no encontrado."
        )

    delta = _reputation_delta(
        review=review,
    )

    score_before = int(
        repliker.reputation_score
    )

    score_after = max(
        0,
        min(
            100,
            score_before + delta,
        ),
    )

    jobs_before = int(
        repliker.jobs_completed
    )

    jobs_after = jobs_before

    if review.status == "passed":
        previous_pass = db.scalar(
            select(
                QAReputationEvent.id
            )
            .where(
                QAReputationEvent.contract_id
                == contract.id,
                QAReputationEvent.outcome
                == "passed",
            )
            .limit(1)
        )

        if previous_pass is None:
            jobs_after += 1

    repliker.reputation_score = (
        score_after
    )

    repliker.jobs_completed = (
        jobs_after
    )

    if review.status == "passed":
        reason = (
            "Entrega aprobada por QA "
            "con evidencia verificable."
        )

    elif review.status == "failed":
        reason = (
            "La revision QA detecto "
            "incumplimientos verificables."
        )

    else:
        reason = (
            "QA requiere evidencia adicional; "
            "la reputacion permanece igual."
        )

    event = QAReputationEvent(
        review_id=
            review.id,
        contract_id=
            contract.id,
        repliker_id=
            repliker.id,
        outcome=
            review.status,
        delta=
            delta,
        score_before=
            score_before,
        score_after=
            score_after,
        jobs_completed_before=
            jobs_before,
        jobs_completed_after=
            jobs_after,
        reason=
            reason,
    )

    db.add(event)
    db.flush()

    return event


def build_retry_feedback(
    *,
    db: Session,
    review: QAReview,
) -> str:
    rows = list(
        db.scalars(
            select(
                QACriterionResult
            )
            .where(
                QACriterionResult.review_id
                == review.id,
                QACriterionResult.status.in_(
                    [
                        "failed",
                        "needs_review",
                    ]
                ),
            )
            .order_by(
                QACriterionResult.id
            )
        ).all()
    )

    if not rows:
        raise QAWorkflowError(
            "No existen criterios "
            "pendientes de corregir."
        )

    lines = [
        (
            "Esta es una correccion QA "
            f"del intento #{review.attempt_number}."
        ),
        "",
        (
            "Corrige la entrega existente. "
            "Debes modificar o crear artifacts "
            "reales y verificar el resultado "
            "con las tools autorizadas."
        ),
        "",
        "OBSERVACIONES QA:",
    ]

    for row in rows:
        criterion = db.get(
            TaskAcceptanceCriterion,
            row.criterion_id,
        )

        description = (
            criterion.description
            if criterion is not None
            else (
                f"Criterio #{row.criterion_id}"
            )
        )

        lines.extend(
            [
                "",
                (
                    f"- Criterio "
                    f"#{row.criterion_id}: "
                    f"{description}"
                ),
                (
                    f"  Estado QA: "
                    f"{row.status}"
                ),
                (
                    f"  Motivo: "
                    f"{row.reason or 'Sin detalle.'}"
                ),
                (
                    "  Evidencia observada: "
                    f"{row.evidence_summary or 'Insuficiente.'}"
                ),
            ]
        )

    lines.extend(
        [
            "",
            (
                "Conserva las partes que "
                "ya son correctas."
            ),
            (
                "Genera nueva evidencia "
                "verificable para todos los "
                "criterios pendientes."
            ),
        ]
    )

    return "\n".join(
        lines
    )[:12000]


def retry_review(
    *,
    db: Session,
    review: QAReview,
    executor=run_contract_execution,
) -> QARetryRun:
    followup = decide_qa_followup(
        review_status=
            review.status,
        attempt_number=
            review.attempt_number,
        max_attempts=
            MAX_QA_ATTEMPTS,
    )

    action = str(
        followup["action"]
    )

    existing = db.scalar(
        select(
            QARetryRun
        )
        .where(
            QARetryRun.source_review_id
            == review.id
        )
    )

    if existing is not None:
        return existing

    if action == "complete":
        raise QAWorkflowError(
            "La entrega ya fue aprobada."
        )

    if action == "exhausted":
        raise QAWorkflowError(
            "Se alcanzo el limite "
            f"de {MAX_QA_ATTEMPTS} "
            "intentos QA."
        )

    if action != "retry":
        raise QAWorkflowError(
            "La revision no permite "
            "un reintento automatico."
        )

    feedback = build_retry_feedback(
        db=db,
        review=review,
    )

    retry = QARetryRun(
        contract_id=
            review.contract_id,
        source_review_id=
            review.id,
        next_review_id=
            None,
        attempt_number=
            review.attempt_number + 1,
        status=
            "running",
        execution_status=
            "pending",
        artifact_count=
            0,
        feedback=
            feedback,
        error_summary=
            "",
    )

    db.add(retry)

    # Persistimos que el retry empezo
    # antes de ejecutar un proceso externo.
    db.commit()
    db.refresh(retry)

    try:
        state = executor(
            db=db,
            contract_id=
                review.contract_id,
            instruction=
                feedback,
        )

    except Exception as exc:
        retry.status = (
            "execution_failed"
        )

        retry.execution_status = (
            "failed"
        )

        retry.error_summary = (
            str(exc)[:4000]
        )

        retry.completed_at = (
            datetime.now(
                timezone.utc
            )
        )

        db.commit()
        db.refresh(retry)

        return retry

    execution_status = str(
        state.get(
            "status",
            "unknown",
        )
    )

    artifact_count = int(
        state.get(
            "artifact_count",
            0,
        )
    )

    retry.execution_status = (
        execution_status
    )

    retry.artifact_count = (
        artifact_count
    )

    if (
        execution_status != "completed"
        or artifact_count <= 0
    ):
        retry.status = (
            "execution_failed"
        )

        retry.error_summary = str(
            state.get(
                "error",
                (
                    "El Repliker no produjo "
                    "artifacts verificables."
                ),
            )
        )[:4000]

        retry.completed_at = (
            datetime.now(
                timezone.utc
            )
        )

        db.commit()
        db.refresh(retry)

        return retry

    try:
        next_review = prepare_qa_review(
            db=db,
            contract_id=
                review.contract_id,
        )

        if next_review.id == review.id:
            raise QAWorkflowError(
                "No se genero un nuevo "
                "intento QA."
            )

        expected_attempt = (
            review.attempt_number + 1
        )

        if (
            next_review.attempt_number
            != expected_attempt
        ):
            raise QAWorkflowError(
                "La secuencia de intentos "
                "QA es inconsistente."
            )

    except Exception as exc:
        # La ejecucion del Repliker pudo
        # completarse correctamente, pero
        # el pipeline QA posterior fallo.
        # Cerramos el retry de forma
        # determinista en lugar de dejarlo
        # permanentemente en running.
        retry.status = (
            "execution_failed"
        )

        retry.error_summary = (
            "QA_PREPARE_FAILED: "
            + str(exc)
        )[:4000]

        retry.completed_at = (
            datetime.now(
                timezone.utc
            )
        )

        db.commit()
        db.refresh(retry)

        return retry

    retry.next_review_id = (
        next_review.id
    )

    retry.status = "completed"

    retry.completed_at = (
        datetime.now(
            timezone.utc
        )
    )

    db.commit()
    db.refresh(retry)

    return retry


def build_followup(
    *,
    db: Session,
    review: QAReview,
    run_retry: bool = True,
) -> dict:
    if review.status not in {
        "passed",
        "failed",
        "needs_review",
    }:
        raise QAWorkflowError(
            "La revision QA debe estar "
            "finalizada antes del follow-up."
        )

    reputation = (
        apply_reputation_for_review(
            db=db,
            review=review,
        )
    )

    followup = decide_qa_followup(
        review_status=
            review.status,
        attempt_number=
            review.attempt_number,
        max_attempts=
            MAX_QA_ATTEMPTS,
    )

    action = str(
        followup["action"]
    )

    retry = db.scalar(
        select(
            QARetryRun
        )
        .where(
            QARetryRun.source_review_id
            == review.id
        )
    )

    if (
        action == "retry"
        and run_retry
        and retry is None
    ):
        retry = retry_review(
            db=db,
            review=review,
        )

    db.commit()

    return {
        "review":
            review,
        "reputation":
            reputation,
        "retry":
            retry,
        "action":
            action,
        "trace":
            list(
                followup.get(
                    "trace",
                    [],
                )
            ),
    }
