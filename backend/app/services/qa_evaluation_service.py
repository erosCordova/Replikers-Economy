from __future__ import annotations

import hashlib

from datetime import (
    datetime,
    timezone,
)

from sqlalchemy import (
    select,
)
from sqlalchemy.orm import Session

from app.agentic.qa_runtime import (
    evaluate_qa_context,
)
from app.execution.policy import (
    ExecutionPolicyError,
)
from app.models.execution import (
    ExecutionArtifact,
    ExecutionWorkspace,
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
from app.schemas.qa_ai import (
    QAReviewDecisionAI,
)
from app.services.qa_service import (
    build_qa_snapshot,
    get_latest_qa_review,
)
from app.services.workspace_service import (
    read_workspace_file_bytes,
)


class QAEvaluationError(
    ValueError
):
    pass


TEXT_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".json",
    ".html",
    ".css",
    ".md",
    ".txt",
    ".sql",
    ".xml",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".csv",
}


MAX_ARTIFACT_CONTEXT_CHARS = (
    12_000
)

MAX_TOTAL_ARTIFACT_CONTEXT_CHARS = (
    40_000
)


def _artifact_is_text(
    artifact: ExecutionArtifact,
) -> bool:
    media_type = (
        artifact.media_type
        or ""
    ).lower()

    if (
        media_type.startswith(
            "text/"
        )
        or media_type
        in {
            "application/json",
            "application/javascript",
            "application/xml",
        }
    ):
        return True

    path = (
        artifact.relative_path
        .lower()
    )

    return any(
        path.endswith(
            extension
        )
        for extension
        in TEXT_EXTENSIONS
    )


def _artifact_contents(
    *,
    db: Session,
    review: QAReview,
) -> list[dict]:
    """
    Construye el contexto QA exclusivamente
    desde el snapshot de QAEvidence asociado
    a esta revision.

    Cada artifact se valida contra:

    1. evidencia capturada,
    2. metadatos persistidos,
    3. bytes reales del workspace.

    Si cualquiera difiere, la revision se
    considera obsoleta y no se envia al LLM.
    """

    workspace = db.get(
        ExecutionWorkspace,
        review.workspace_id,
    )

    if workspace is None:
        raise QAEvaluationError(
            "Workspace QA no encontrado."
        )

    evidence_rows = list(
        db.scalars(
            select(
                QAEvidence
            )
            .where(
                QAEvidence.review_id
                == review.id,
                QAEvidence
                .criterion_result_id
                .is_(None),
                QAEvidence.evidence_type
                == "artifact",
            )
            .order_by(
                QAEvidence.id
            )
        ).all()
    )

    result: list[dict] = []

    consumed = 0

    for evidence in evidence_rows:

        if evidence.artifact_id is None:
            raise QAEvaluationError(
                "Snapshot QA inconsistente: "
                "evidencia artifact sin "
                "artifact_id."
            )

        artifact = db.get(
            ExecutionArtifact,
            evidence.artifact_id,
        )

        if artifact is None:
            raise QAEvaluationError(
                "Snapshot QA obsoleto: "
                f"artifact #{evidence.artifact_id} "
                "ya no existe."
            )

        if (
            artifact.workspace_id
            != workspace.id
        ):
            raise QAEvaluationError(
                "Snapshot QA invalido: "
                "el artifact pertenece "
                "a otro workspace."
            )

        if (
            artifact.relative_path
            != evidence.reference
        ):
            raise QAEvaluationError(
                "Snapshot QA obsoleto: "
                "la ruta del artifact cambio."
            )

        snapshot_sha = str(
            evidence.sha256
            or ""
        ).strip().lower()

        persisted_sha = str(
            artifact.sha256
            or ""
        ).strip().lower()

        if not snapshot_sha:
            raise QAEvaluationError(
                "Snapshot QA invalido: "
                "artifact sin SHA-256."
            )

        if (
            persisted_sha
            != snapshot_sha
        ):
            raise QAEvaluationError(
                "Snapshot QA obsoleto: "
                f"artifact "
                f"'{artifact.relative_path}' "
                "cambio despues de preparar "
                "la revision."
            )

        try:
            payload = (
                read_workspace_file_bytes(
                    workspace=workspace,
                    relative_path=
                        artifact.relative_path,
                )
            )

        except (
            FileNotFoundError,
            ExecutionPolicyError,
            OSError,
        ) as exc:
            raise QAEvaluationError(
                "No se pudo verificar "
                f"'{artifact.relative_path}': "
                f"{str(exc)[:300]}"
            ) from exc

        actual_sha = (
            hashlib.sha256(
                payload
            )
            .hexdigest()
            .lower()
        )

        if (
            actual_sha
            != snapshot_sha
        ):
            raise QAEvaluationError(
                "Integridad QA rechazada: "
                f"'{artifact.relative_path}' "
                "no coincide con el SHA-256 "
                "capturado."
            )

        if (
            len(payload)
            != artifact.size_bytes
        ):
            raise QAEvaluationError(
                "Integridad QA rechazada: "
                f"'{artifact.relative_path}' "
                "cambio de tamano."
            )

        item = {
            "artifact_id":
                artifact.id,
            "evidence_id":
                evidence.id,
            "relative_path":
                artifact.relative_path,
            "media_type":
                artifact.media_type,
            "size_bytes":
                len(payload),
            "sha256":
                snapshot_sha,
            "text_content":
                None,
        }

        if (
            not _artifact_is_text(
                artifact
            )
        ):
            result.append(
                item
            )
            continue

        if (
            consumed
            >= MAX_TOTAL_ARTIFACT_CONTEXT_CHARS
        ):
            item[
                "text_content"
            ] = (
                "[contenido omitido por "
                "limite de contexto QA]"
            )

            result.append(
                item
            )

            continue

        try:
            content = payload.decode(
                "utf-8"
            )

        except UnicodeDecodeError:
            item[
                "text_content"
            ] = (
                "[contenido no disponible: "
                "el archivo no es UTF-8]"
            )

            result.append(
                item
            )

            continue

        remaining = (
            MAX_TOTAL_ARTIFACT_CONTEXT_CHARS
            - consumed
        )

        limit = min(
            MAX_ARTIFACT_CONTEXT_CHARS,
            remaining,
        )

        clipped = content[
            :limit
        ]

        consumed += len(
            clipped
        )

        item[
            "text_content"
        ] = clipped

        if (
            len(content)
            > len(clipped)
        ):
            item[
                "text_content"
            ] += (
                "\n[contenido truncado]"
            )

        result.append(
            item
        )

    return result


def build_qa_agent_context(
    *,
    db: Session,
    review: QAReview,
) -> dict:
    snapshot = build_qa_snapshot(
        db=db,
        review=review,
    )

    task = db.get(
        Task,
        review.task_id,
    )

    if task is None:
        raise QAEvaluationError(
            "Tarea QA no encontrada."
        )

    raw_evidence = [
        item
        for item
        in snapshot["evidence"]
        if (
            item[
                "criterion_result_id"
            ]
            is None
        )
    ]

    return {
        "review": {
            "id":
                review.id,
            "attempt_number":
                review.attempt_number,
            "contract_id":
                review.contract_id,
            "workspace_id":
                review.workspace_id,
        },
        "task": {
            "id":
                task.id,
            "title":
                task.title,
            "description":
                task.description,
        },
        "criteria": [
            {
                "criterion_id":
                    item[
                        "criterion_id"
                    ],
                "description":
                    item[
                        "criterion_description"
                    ],
                "is_mandatory":
                    item[
                        "is_mandatory"
                    ],
            }
            for item
            in snapshot[
                "criteria"
            ]
        ],
        "evidence": [
            {
                "evidence_id":
                    item["id"],
                "type":
                    item[
                        "evidence_type"
                    ],
                "reference":
                    item[
                        "reference"
                    ],
                "sha256":
                    item[
                        "sha256"
                    ],
                "summary":
                    item[
                        "summary"
                    ],
            }
            for item
            in raw_evidence
        ],
        "artifacts": (
            _artifact_contents(
                db=db,
                review=review,
            )
        ),
    }


def _criterion_rows(
    *,
    db: Session,
    review_id: int,
) -> dict[int, QACriterionResult]:
    rows = list(
        db.scalars(
            select(
                QACriterionResult
            )
            .where(
                QACriterionResult.review_id
                == review_id
            )
        ).all()
    )

    return {
        row.criterion_id:
            row
        for row in rows
    }


def _criterion_models(
    *,
    db: Session,
    criterion_ids: set[int],
) -> dict[int, TaskAcceptanceCriterion]:
    if not criterion_ids:
        return {}

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

    return {
        row.id:
            row
        for row in rows
    }


def _available_evidence(
    *,
    db: Session,
    review_id: int,
) -> dict[int, QAEvidence]:
    rows = list(
        db.scalars(
            select(
                QAEvidence
            )
            .where(
                QAEvidence.review_id
                == review_id,
                QAEvidence.criterion_result_id
                .is_(None),
            )
        ).all()
    )

    return {
        row.id:
            row
        for row in rows
    }


def _validate_ai_result(
    *,
    decision: QAReviewDecisionAI,
    criterion_rows:
        dict[int, QACriterionResult],
    evidence:
        dict[int, QAEvidence],
):
    returned_ids = [
        item.criterion_id
        for item
        in decision.criteria
    ]

    if (
        len(returned_ids)
        != len(
            set(returned_ids)
        )
    ):
        raise QAEvaluationError(
            "El QA Agent devolvio "
            "criterios duplicados."
        )

    expected = set(
        criterion_rows
    )

    returned = set(
        returned_ids
    )

    if returned != expected:
        raise QAEvaluationError(
            "El QA Agent no devolvio "
            "exactamente los criterios "
            "de la revision."
        )

    available_evidence_ids = set(
        evidence
    )

    for item in decision.criteria:
        unknown = (
            set(
                item.evidence_ids
            )
            - available_evidence_ids
        )

        if unknown:
            raise QAEvaluationError(
                "El QA Agent hizo referencia "
                "a evidencia inexistente."
            )


def _bind_evidence(
    *,
    db: Session,
    review: QAReview,
    criterion_result:
        QACriterionResult,
    evidence_ids: list[int],
    evidence:
        dict[int, QAEvidence],
):
    for evidence_id in dict.fromkeys(
        evidence_ids
    ):
        source = evidence[
            evidence_id
        ]

        db.add(
            QAEvidence(
                review_id=
                    review.id,
                criterion_result_id=
                    criterion_result.id,
                evidence_type=
                    source.evidence_type,
                artifact_id=
                    source.artifact_id,
                tool_execution_log_id=
                    source.tool_execution_log_id,
                reference=
                    source.reference,
                sha256=
                    source.sha256,
                summary=(
                    source.summary
                ),
            )
        )


def apply_qa_decision(
    *,
    db: Session,
    review: QAReview,
    decision: QAReviewDecisionAI,
) -> QAReview:
    if review.status not in {
        "prepared",
        "running",
    }:
        raise QAEvaluationError(
            "La revision QA ya fue "
            "finalizada."
        )

    criterion_rows = (
        _criterion_rows(
            db=db,
            review_id=
                review.id,
        )
    )

    if not criterion_rows:
        raise QAEvaluationError(
            "La revision QA no tiene "
            "criterios registrados."
        )

    criterion_models = (
        _criterion_models(
            db=db,
            criterion_ids=
                set(
                    criterion_rows
                ),
        )
    )

    evidence = (
        _available_evidence(
            db=db,
            review_id=
                review.id,
        )
    )

    _validate_ai_result(
        decision=decision,
        criterion_rows=
            criterion_rows,
        evidence=
            evidence,
    )

    final_statuses: dict[
        int,
        str,
    ] = {}

    final_scores: list[int] = []

    for ai_item in decision.criteria:
        row = criterion_rows[
            ai_item.criterion_id
        ]

        criterion = (
            criterion_models.get(
                ai_item.criterion_id
            )
        )

        if criterion is None:
            raise QAEvaluationError(
                "Criterio QA no encontrado."
            )

        status = (
            ai_item.status
        )

        score = int(
            ai_item.score
        )

        reason = (
            ai_item.reason.strip()
        )

        evidence_ids = list(
            dict.fromkeys(
                ai_item.evidence_ids
            )
        )

        evidence_summary = (
            ai_item
            .evidence_summary
            .strip()
        )

        if (
            status == "passed"
            and not evidence_ids
        ):
            status = (
                "needs_review"
            )

            score = min(
                score,
                50,
            )

            reason = (
                reason
                + " No se proporciono "
                "evidencia verificable "
                "para aprobar el criterio."
            ).strip()

        row.status = status
        row.score = score
        row.reason = (
            reason[:4000]
        )

        evidence_id_text = (
            ", ".join(
                str(item)
                for item
                in evidence_ids
            )
        )

        row.evidence_summary = (
            (
                evidence_summary
                + (
                    f" [evidence_ids: "
                    f"{evidence_id_text}]"
                    if evidence_ids
                    else ""
                )
            )
            .strip()
            [:4000]
        )

        criterion.status = (
            status
        )

        criterion.evidence = (
            row.evidence_summary
        )

        _bind_evidence(
            db=db,
            review=review,
            criterion_result=row,
            evidence_ids=
                evidence_ids,
            evidence=
                evidence,
        )

        final_statuses[
            criterion.id
        ] = status

        final_scores.append(
            score
        )

    mandatory_statuses = [
        final_statuses[
            criterion_id
        ]
        for criterion_id, criterion
        in criterion_models.items()
        if criterion.is_mandatory
    ]

    if not mandatory_statuses:
        raise QAEvaluationError(
            "La tarea no tiene criterios "
            "obligatorios verificables."
        )

    if (
        "failed"
        in mandatory_statuses
    ):
        overall_status = (
            "failed"
        )

    elif (
        "needs_review"
        in mandatory_statuses
    ):
        overall_status = (
            "needs_review"
        )

    else:
        overall_status = (
            "passed"
        )

    review.status = (
        overall_status
    )

    review.score = (
        round(
            sum(final_scores)
            / len(final_scores)
        )
        if final_scores
        else None
    )

    review.reviewer_type = (
        "langchain_qa"
    )

    review.reviewer_repliker_id = (
        None
    )

    review.summary = (
        decision.summary[:5000]
    )

    review.completed_at = (
        datetime.now(
            timezone.utc
        )
    )

    db.flush()

    return review


def evaluate_prepared_review(
    *,
    db: Session,
    review: QAReview,
    evaluator=evaluate_qa_context,
) -> QAReview:
    if review.status != "prepared":
        raise QAEvaluationError(
            "La ultima revision QA "
            "no esta preparada para evaluar."
        )

    context = build_qa_agent_context(
        db=db,
        review=review,
    )

    review.status = "running"

    db.flush()

    decision = evaluator(
        context=context,
    )

    return apply_qa_decision(
        db=db,
        review=review,
        decision=decision,
    )


def evaluate_contract_qa(
    *,
    db: Session,
    contract_id: int,
) -> QAReview:
    review = get_latest_qa_review(
        db=db,
        contract_id=
            contract_id,
    )

    if review is None:
        raise QAEvaluationError(
            "Primero debe prepararse "
            "una revision QA."
        )

    return evaluate_prepared_review(
        db=db,
        review=review,
    )
