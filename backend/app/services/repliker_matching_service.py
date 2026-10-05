from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.models.repliker import Repliker
from app.models.task import Task


RESERVED_TASK_SPECIALTIES = {
    "product / requirements",
    "final reviewer",
}

GENERALIST_SPECIALTIES = {
    "",
    "generalist",
    "generalista",
}

AVAILABLE_STATUSES = {
    "available",
}


MINIMUM_MARKET_SKILL_COVERAGE = 60.0


@dataclass(
    frozen=True,
    slots=True,
)
class ReplikerCandidate:
    repliker: Repliker

    skill_coverage: float

    skills_met: int
    skills_total: int

    meets_all_skills: bool


def market_candidate_is_relevant(
    candidate: ReplikerCandidate,
) -> bool:
    """
    Solo consulta IA para candidatos con
    una cobertura técnica significativa.

    Una tarea sin habilidades explícitas
    conserva su comportamiento normal.
    """

    if candidate.skills_total == 0:
        return True

    return (
        candidate.skill_coverage
        >= MINIMUM_MARKET_SKILL_COVERAGE
    )


def normalize_market_text(
    value: str | None,
) -> str:
    return " ".join(
        str(
            value or ""
        )
        .strip()
        .casefold()
        .split()
    )


def _skill_map(
    repliker: Repliker,
) -> dict[str, int]:
    result: dict[str, int] = {}

    for skill in repliker.skills:
        name = normalize_market_text(
            skill.name
        )

        if not name:
            continue

        result[name] = max(
            0,
            min(
                100,
                int(
                    skill.level
                ),
            ),
        )

    return result


def resolve_skill_level(
    *,
    required_name: str,
    actual_skills: dict[str, int],
) -> int:
    """
    Resuelve habilidades equivalentes o compuestas
    sin relajar los niveles mínimos solicitados.

    Ejemplos:
    - HTML/CSS requiere HTML y CSS.
    - Frontend Development requiere lenguaje
      frontend + HTML + CSS.
    """

    normalized = normalize_market_text(
        required_name
    )

    exact = actual_skills.get(
        normalized
    )

    if exact is not None:
        return exact

    compact = (
        normalized
        .replace(" ", "")
    )

    if compact in {
        "html/css",
        "html+css",
        "html&css",
    }:
        html = actual_skills.get(
            "html",
            0,
        )

        css = actual_skills.get(
            "css",
            0,
        )

        if html <= 0 or css <= 0:
            return 0

        return min(
            html,
            css,
        )

    if normalized in {
        "frontend development",
        "frontend developer",
        "desarrollo frontend",
        "desarrollo de frontend",
    }:
        javascript = max(
            actual_skills.get(
                "javascript",
                0,
            ),
            actual_skills.get(
                "typescript",
                0,
            ),
        )

        html = actual_skills.get(
            "html",
            0,
        )

        css = actual_skills.get(
            "css",
            0,
        )

        if (
            javascript <= 0
            or html <= 0
            or css <= 0
        ):
            return 0

        return min(
            javascript,
            html,
            css,
        )

    return 0


def _skill_metrics(
    *,
    task: Task,
    repliker: Repliker,
) -> tuple[
    float,
    int,
    int,
    bool,
]:
    requirements = list(
        task.required_skills
    )

    if not requirements:
        return (
            100.0,
            0,
            0,
            True,
        )

    actual_skills = _skill_map(
        repliker
    )

    total_score = 0.0
    skills_met = 0

    for requirement in requirements:
        name = normalize_market_text(
            requirement.skill_name
        )

        minimum = max(
            0,
            int(
                requirement.minimum_level
            ),
        )

        actual = resolve_skill_level(
            required_name=name,
            actual_skills=actual_skills,
        )

        if actual >= minimum:
            skills_met += 1

        if minimum <= 0:
            ratio = 1.0
        else:
            ratio = min(
                actual / minimum,
                1.0,
            )

        total_score += (
            ratio * 100.0
        )

    skills_total = len(
        requirements
    )

    coverage = round(
        total_score
        / skills_total,
        2,
    )

    return (
        coverage,
        skills_met,
        skills_total,
        skills_met
        == skills_total,
    )


def _specialty_matches(
    *,
    task: Task,
    repliker: Repliker,
) -> bool:
    required = normalize_market_text(
        task.required_specialty
    )

    actual = normalize_market_text(
        repliker.specialty
    )

    if (
        required
        in GENERALIST_SPECIALTIES
    ):
        return True

    return actual == required


def rank_task_candidates(
    *,
    task: Task,
    replikers: Iterable[
        Repliker
    ],
) -> list[
    ReplikerCandidate
]:
    candidates: list[
        ReplikerCandidate
    ] = []

    for repliker in replikers:
        if not repliker.is_active:
            continue

        if not repliker.is_published:
            continue

        status = normalize_market_text(
            repliker.status
        )

        if (
            status
            not in AVAILABLE_STATUSES
        ):
            continue

        specialty = (
            normalize_market_text(
                repliker.specialty
            )
        )

        if (
            specialty
            in RESERVED_TASK_SPECIALTIES
        ):
            continue

        if not _specialty_matches(
            task=task,
            repliker=repliker,
        ):
            continue

        (
            coverage,
            skills_met,
            skills_total,
            meets_all,
        ) = _skill_metrics(
            task=task,
            repliker=repliker,
        )

        candidates.append(
            ReplikerCandidate(
                repliker=repliker,
                skill_coverage=
                    coverage,
                skills_met=
                    skills_met,
                skills_total=
                    skills_total,
                meets_all_skills=
                    meets_all,
            )
        )

    candidates.sort(
        key=lambda candidate: (
            -int(
                candidate
                .meets_all_skills
            ),
            -candidate.skill_coverage,
            -int(
                candidate
                .repliker
                .reputation_score
            ),
            -int(
                candidate
                .repliker
                .jobs_completed
            ),
            int(
                candidate
                .repliker
                .id
                or 0
            ),
        )
    )

    return candidates
