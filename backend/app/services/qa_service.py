from __future__ import annotations

from sqlalchemy import (
    func,
    select,
)
from sqlalchemy.orm import Session

from app.models.contract import (
    TaskContract,
)
from app.models.execution import (
    ExecutionArtifact,
    ExecutionWorkspace,
    ToolExecutionLog,
)
from app.models.qa import (
    QACriterionResult,
    QAEvidence,
    QAReview,
)
from app.models.task import (
    Task,
    TaskAcceptanceCriterion,
)


class QAServiceError(ValueError):
    pass


ACTIVE_QA_STATUSES = {
    "prepared",
    "running",
}


def _get_contract(
    *,
    db: Session,
    contract_id: int,
) -> TaskContract:
    contract = db.get(
        TaskContract,
        contract_id,
    )

    if contract is None:
        raise QAServiceError(
            "Contrato no encontrado."
        )

    return contract


def _get_workspace(
    *,
    db: Session,
    contract_id: int,
) -> ExecutionWorkspace:
    workspace = db.scalar(
        select(
            ExecutionWorkspace
        )
        .where(
            ExecutionWorkspace.contract_id
            == contract_id
        )
    )

    if workspace is None:
        raise QAServiceError(
            "El contrato todavia no tiene "
            "un workspace de ejecucion."
        )

    return workspace


def _get_criteria(
    *,
    db: Session,
    task_id: int,
) -> list[TaskAcceptanceCriterion]:
    criteria = list(
        db.scalars(
            select(
                TaskAcceptanceCriterion
            )
            .where(
                TaskAcceptanceCriterion.task_id
                == task_id
            )
            .order_by(
                TaskAcceptanceCriterion.id
            )
        ).all()
    )

    if not criteria:
        raise QAServiceError(
            "La tarea no tiene criterios "
            "de aceptacion verificables."
        )

    return criteria


def _latest_review(
    *,
    db: Session,
    contract_id: int,
) -> QAReview | None:
    return db.scalar(
        select(
            QAReview
        )
        .where(
            QAReview.contract_id
            == contract_id
        )
        .order_by(
            QAReview.attempt_number.desc()
        )
        .limit(1)
    )


def _next_attempt(
    *,
    db: Session,
    contract_id: int,
) -> int:
    last_attempt = db.scalar(
        select(
            func.max(
                QAReview.attempt_number
            )
        )
        .where(
            QAReview.contract_id
            == contract_id
        )
    )

    return int(
        last_attempt or 0
    ) + 1


def _collect_artifacts(
    *,
    db: Session,
    workspace_id: int,
) -> list[ExecutionArtifact]:
    return list(
        db.scalars(
            select(
                ExecutionArtifact
            )
            .where(
                ExecutionArtifact.workspace_id
                == workspace_id
            )
            .order_by(
                ExecutionArtifact.id
            )
        ).all()
    )


def _collect_tool_logs(
    *,
    db: Session,
    workspace_id: int,
) -> list[ToolExecutionLog]:
    return list(
        db.scalars(
            select(
                ToolExecutionLog
            )
            .where(
                ToolExecutionLog.workspace_id
                == workspace_id
            )
            .order_by(
                ToolExecutionLog.id.desc()
            )
            .limit(100)
        ).all()
    )


def _add_artifact_evidence(
    *,
    db: Session,
    review: QAReview,
    artifact: ExecutionArtifact,
):
    db.add(
        QAEvidence(
            review_id=
                review.id,
            criterion_result_id=
                None,
            evidence_type=
                "artifact",
            artifact_id=
                artifact.id,
            tool_execution_log_id=
                None,
            reference=
                artifact.relative_path,
            sha256=
                artifact.sha256,
            summary=(
                f"Artifact: "
                f"{artifact.relative_path}; "
                f"media_type="
                f"{artifact.media_type}; "
                f"size_bytes="
                f"{artifact.size_bytes}."
            ),
        )
    )


def _add_tool_evidence(
    *,
    db: Session,
    review: QAReview,
    log: ToolExecutionLog,
):
    target = (
        log.target_path
        or "-"
    )

    details = (
        f"Tool: {log.tool_name}; "
        f"status={log.status}; "
        f"target={target}."
    )

    if log.output_summary:
        details += (
            " Output: "
            + log.output_summary[:2500]
        )

    if log.error_summary:
        details += (
            " Error: "
            + log.error_summary[:1200]
        )

    db.add(
        QAEvidence(
            review_id=
                review.id,
            criterion_result_id=
                None,
            evidence_type=
                "tool_execution",
            artifact_id=
                None,
            tool_execution_log_id=
                log.id,
            reference=(
                f"tool-log:{log.id}"
            ),
            sha256="",
            summary=
                details[:4000],
        )
    )


def prepare_qa_review(
    *,
    db: Session,
    contract_id: int,
) -> QAReview:
    contract = _get_contract(
        db=db,
        contract_id=
            contract_id,
    )

    task = db.get(
        Task,
        contract.task_id,
    )

    if task is None:
        raise QAServiceError(
            "La tarea del contrato "
            "no existe."
        )

    workspace = _get_workspace(
        db=db,
        contract_id=
            contract.id,
    )

    criteria = _get_criteria(
        db=db,
        task_id=
            task.id,
    )

    latest = _latest_review(
        db=db,
        contract_id=
            contract.id,
    )

    if (
        latest is not None
        and latest.status
        in ACTIVE_QA_STATUSES
    ):
        return latest

    artifacts = _collect_artifacts(
        db=db,
        workspace_id=
            workspace.id,
    )

    tool_logs = _collect_tool_logs(
        db=db,
        workspace_id=
            workspace.id,
    )

    review = QAReview(
        contract_id=
            contract.id,
        task_id=
            task.id,
        workspace_id=
            workspace.id,
        execution_repliker_id=
            contract.repliker_id,
        reviewer_repliker_id=
            None,
        attempt_number=
            _next_attempt(
                db=db,
                contract_id=
                    contract.id,
            ),
        status=
            "prepared",
        score=
            None,
        reviewer_type=
            "system_precheck",
        summary=(
            f"QA preparado con "
            f"{len(criteria)} criterio(s), "
            f"{len(artifacts)} artifact(s) "
            f"y {len(tool_logs)} registro(s) "
            "de ejecucion."
        ),
    )

    db.add(
        review
    )

    db.flush()

    for criterion in criteria:
        db.add(
            QACriterionResult(
                review_id=
                    review.id,
                criterion_id=
                    criterion.id,
                status=
                    "pending",
                score=
                    None,
                reason="",
                evidence_summary="",
            )
        )

    db.flush()

    for artifact in artifacts:
        _add_artifact_evidence(
            db=db,
            review=review,
            artifact=artifact,
        )

    for log in tool_logs:
        _add_tool_evidence(
            db=db,
            review=review,
            log=log,
        )

    db.flush()

    return review


def get_latest_qa_review(
    *,
    db: Session,
    contract_id: int,
) -> QAReview | None:
    return _latest_review(
        db=db,
        contract_id=
            contract_id,
    )


def build_qa_snapshot(
    *,
    db: Session,
    review: QAReview,
) -> dict:
    results = list(
        db.scalars(
            select(
                QACriterionResult
            )
            .where(
                QACriterionResult.review_id
                == review.id
            )
            .order_by(
                QACriterionResult.id
            )
        ).all()
    )

    evidence = list(
        db.scalars(
            select(
                QAEvidence
            )
            .where(
                QAEvidence.review_id
                == review.id
            )
            .order_by(
                QAEvidence.id
            )
        ).all()
    )

    criterion_ids = [
        item.criterion_id
        for item in results
    ]

    criteria = {}

    if criterion_ids:
        rows = list(
            db.scalars(
                select(
                    TaskAcceptanceCriterion
                )
                .where(
                    TaskAcceptanceCriterion.id
                    .in_(
                        criterion_ids
                    )
                )
            ).all()
        )

        criteria = {
            item.id:
                item
            for item in rows
        }

    return {
        "id":
            review.id,
        "contract_id":
            review.contract_id,
        "task_id":
            review.task_id,
        "workspace_id":
            review.workspace_id,
        "execution_repliker_id":
            review.execution_repliker_id,
        "reviewer_repliker_id":
            review.reviewer_repliker_id,
        "attempt_number":
            review.attempt_number,
        "status":
            review.status,
        "score":
            review.score,
        "reviewer_type":
            review.reviewer_type,
        "summary":
            review.summary,
        "criteria": [
            {
                "id":
                    result.id,
                "criterion_id":
                    result.criterion_id,
                "criterion_description": (
                    criteria[
                        result.criterion_id
                    ].description
                    if result.criterion_id
                    in criteria
                    else ""
                ),
                "is_mandatory": (
                    criteria[
                        result.criterion_id
                    ].is_mandatory
                    if result.criterion_id
                    in criteria
                    else True
                ),
                "status":
                    result.status,
                "score":
                    result.score,
                "reason":
                    result.reason,
                "evidence_summary":
                    result.evidence_summary,
            }
            for result in results
        ],
        "evidence": [
            {
                "id":
                    item.id,
                "evidence_type":
                    item.evidence_type,
                "criterion_result_id":
                    item.criterion_result_id,
                "artifact_id":
                    item.artifact_id,
                "tool_execution_log_id":
                    item.tool_execution_log_id,
                "reference":
                    item.reference,
                "sha256":
                    item.sha256,
                "summary":
                    item.summary,
                "created_at":
                    item.created_at,
            }
            for item in evidence
        ],
        "created_at":
            review.created_at,
        "completed_at":
            review.completed_at,
    }
