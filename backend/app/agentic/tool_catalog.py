from dataclasses import dataclass

import unicodedata

from langchain_core.tools import (
    BaseTool,
    StructuredTool,
)


TOOL_DEFINITIONS = {
    "inspect_repliker_profile": {
        "label": "Inspeccionar perfil",
        "pack": "market_core",
        "description": (
            "Consulta el perfil real del Repliker, "
            "sus habilidades, reputacion y experiencia."
        ),
        "risk": "low",
        "permission_level": "read",
    },

    "inspect_project": {
        "label": "Inspeccionar proyecto",
        "pack": "market_core",
        "description": (
            "Consulta los datos y limites reales "
            "del proyecto."
        ),
        "risk": "low",
        "permission_level": "read",
    },

    "inspect_task": {
        "label": "Inspeccionar tarea",
        "pack": "market_core",
        "description": (
            "Consulta requisitos, presupuesto, "
            "complejidad y criterios de la tarea."
        ),
        "risk": "low",
        "permission_level": "read",
    },

    "inspect_tool_permissions": {
        "label": "Inspeccionar permisos",
        "pack": "market_core",
        "description": (
            "Permite al agente conocer exactamente "
            "que tools tiene autorizadas."
        ),
        "risk": "low",
        "permission_level": "read",
    },

    "evaluate_skill_coverage": {
        "label": "Evaluar habilidades",
        "pack": "market_core",
        "description": (
            "Compara deterministicamente las "
            "habilidades del Repliker con las "
            "exigidas por la tarea."
        ),
        "risk": "low",
        "permission_level": "compute",
    },
}


MARKET_CORE_TOOLS = tuple(
    TOOL_DEFINITIONS.keys()
)


TOOL_PACKS = {
    "market_core":
        MARKET_CORE_TOOLS,

    # Fase 7:
    "execution_backend": (),

    "execution_frontend": (),

    "execution_data": (),

    # Fase 8:
    "quality_assurance": (),

    # Se ampliara cuando exista una
    # implementacion real y segura.
    "research": (),
}


@dataclass(
    frozen=True,
)
class MarketToolContext:
    repliker_data: dict

    task_data: dict

    project_data: dict

    allowed_tool_names: tuple[
        str,
        ...,
    ]


def list_tool_catalog() -> list[dict]:
    result = []

    for (
        name,
        definition,
    ) in TOOL_DEFINITIONS.items():
        result.append(
            {
                "name": name,
                **definition,
            }
        )

    return result


def _normalize(
    value: str,
) -> str:
    value = (
        value
        .strip()
        .lower()
    )

    normalized = (
        unicodedata.normalize(
            "NFKD",
            value,
        )
    )

    normalized = "".join(
        character
        for character
        in normalized
        if not unicodedata.combining(
            character
        )
    )

    return " ".join(
        normalized
        .replace("_", " ")
        .replace("-", " ")
        .split()
    )


def _skill_coverage(
    context: MarketToolContext,
) -> dict:
    available = {
        _normalize(
            str(
                skill.get(
                    "name",
                    "",
                )
            )
        ): int(
            skill.get(
                "level",
                0,
            )
            or 0
        )
        for skill
        in context
        .repliker_data
        .get(
            "skills",
            [],
        )
    }

    requirements = (
        context
        .task_data
        .get(
            "required_skills",
            [],
        )
    )

    details = []

    passed = 0

    for requirement in requirements:
        skill_name = str(
            requirement.get(
                "skill_name",
                "",
            )
        )

        minimum = int(
            requirement.get(
                "minimum_level",
                0,
            )
            or 0
        )

        current = available.get(
            _normalize(
                skill_name
            ),
            0,
        )

        meets = (
            current >= minimum
        )

        if meets:
            passed += 1

        details.append(
            {
                "skill": skill_name,
                "required_level": minimum,
                "current_level": current,
                "meets_requirement": meets,
            }
        )

    total = len(
        requirements
    )

    coverage_percent = (
        100
        if total == 0
        else round(
            passed
            / total
            * 100
        )
    )

    return {
        "requirements": details,
        "requirements_met": passed,
        "requirements_total": total,
        "coverage_percent":
            coverage_percent,
    }


def resolve_market_tool_names(
    repliker_data: dict,
) -> tuple[str, ...]:
    """
    Politica por defecto.

    Cuando el Repliker posee configuracion
    persistida, agentic_service sustituye esta
    politica por sus tools explicitamente
    asignadas.
    """

    _ = repliker_data

    return MARKET_CORE_TOOLS


def build_market_tools(
    *,
    repliker_data: dict,
    task_data: dict,
    project_data: dict,
    allowed_tool_names:
        tuple[str, ...]
        | None = None,
) -> list[BaseTool]:
    if allowed_tool_names is None:
        allowed_tool_names = (
            resolve_market_tool_names(
                repliker_data
            )
        )

    context = MarketToolContext(
        repliker_data=
            repliker_data,
        task_data=
            task_data,
        project_data=
            project_data,
        allowed_tool_names=
            allowed_tool_names,
    )

    def inspect_repliker_profile():
        return (
            context.repliker_data
        )

    def inspect_project():
        return (
            context.project_data
        )

    def inspect_task():
        return (
            context.task_data
        )

    def inspect_tool_permissions():
        return {
            "allowed_tools": list(
                context
                .allowed_tool_names
            ),
            "tool_count": len(
                context
                .allowed_tool_names
            ),
        }

    def evaluate_skill_coverage():
        return _skill_coverage(
            context
        )

    implementations = {
        "inspect_repliker_profile":
            StructuredTool.from_function(
                func=
                    inspect_repliker_profile,
                name=(
                    "inspect_repliker_profile"
                ),
                description=(
                    TOOL_DEFINITIONS[
                        "inspect_repliker_profile"
                    ][
                        "description"
                    ]
                ),
            ),

        "inspect_project":
            StructuredTool.from_function(
                func=inspect_project,
                name="inspect_project",
                description=(
                    TOOL_DEFINITIONS[
                        "inspect_project"
                    ][
                        "description"
                    ]
                ),
            ),

        "inspect_task":
            StructuredTool.from_function(
                func=inspect_task,
                name="inspect_task",
                description=(
                    TOOL_DEFINITIONS[
                        "inspect_task"
                    ][
                        "description"
                    ]
                ),
            ),

        "inspect_tool_permissions":
            StructuredTool.from_function(
                func=
                    inspect_tool_permissions,
                name=(
                    "inspect_tool_permissions"
                ),
                description=(
                    TOOL_DEFINITIONS[
                        "inspect_tool_permissions"
                    ][
                        "description"
                    ]
                ),
            ),

        "evaluate_skill_coverage":
            StructuredTool.from_function(
                func=
                    evaluate_skill_coverage,
                name=(
                    "evaluate_skill_coverage"
                ),
                description=(
                    TOOL_DEFINITIONS[
                        "evaluate_skill_coverage"
                    ][
                        "description"
                    ]
                ),
            ),
    }

    tools = []

    for tool_name in (
        allowed_tool_names
    ):
        tool = implementations.get(
            tool_name
        )

        if tool is not None:
            tools.append(
                tool
            )

    return tools
