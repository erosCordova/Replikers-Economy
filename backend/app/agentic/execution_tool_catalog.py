from dataclasses import (
    dataclass,
)


@dataclass(
    frozen=True
)
class ExecutionToolDefinition:
    name: str

    label: str

    description: str

    risk: str

    permission_level: str


EXECUTION_TOOL_DEFINITIONS = {
    "workspace_list_files":
        ExecutionToolDefinition(
            name=(
                "workspace_list_files"
            ),
            label=(
                "Listar archivos"
            ),
            description=(
                "Lista archivos del workspace "
                "del contrato."
            ),
            risk="low",
            permission_level="read",
        ),

    "workspace_read_text":
        ExecutionToolDefinition(
            name=(
                "workspace_read_text"
            ),
            label=(
                "Leer archivo"
            ),
            description=(
                "Lee texto UTF-8 dentro del "
                "workspace autorizado."
            ),
            risk="low",
            permission_level="read",
        ),

    "workspace_write_text":
        ExecutionToolDefinition(
            name=(
                "workspace_write_text"
            ),
            label=(
                "Escribir archivo"
            ),
            description=(
                "Crea o reemplaza archivos "
                "dentro del workspace."
            ),
            risk="medium",
            permission_level="write",
        ),
}


EXECUTION_CORE_TOOLS = tuple(
    EXECUTION_TOOL_DEFINITIONS
)
