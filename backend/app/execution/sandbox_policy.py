from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from app.execution.policy import (
    ExecutionPolicyError,
    normalize_relative_path,
    resolve_inside_workspace,
)


class SandboxPolicyError(ExecutionPolicyError):
    """Error de validacion de una ejecucion aislada."""


@dataclass(frozen=True)
class SandboxLimits:
    memory: str = "128m"
    cpus: str = "0.50"
    pids_limit: int = 64
    timeout_seconds: int = 20
    max_output_bytes: int = 65536
    tmpfs_size: str = "32m"

    def validate(self) -> None:
        if self.pids_limit <= 0:
            raise SandboxPolicyError(
                "El limite de procesos debe ser positivo."
            )

        if self.timeout_seconds <= 0:
            raise SandboxPolicyError(
                "El timeout debe ser positivo."
            )

        if self.max_output_bytes < 1024:
            raise SandboxPolicyError(
                "El limite de salida es demasiado pequeno."
            )


def validate_python_target(
    *,
    workspace_root: Path,
    relative_path: str,
) -> tuple[str, Path]:
    normalized = normalize_relative_path(
        relative_path
    )

    suffix = PurePosixPath(
        normalized
    ).suffix.lower()

    if suffix != ".py":
        raise SandboxPolicyError(
            "run_python solo permite archivos .py."
        )

    target = resolve_inside_workspace(
        workspace_root=workspace_root,
        relative_path=normalized,
    )

    if not target.exists():
        raise SandboxPolicyError(
            "El archivo no existe en el workspace."
        )

    if not target.is_file():
        raise SandboxPolicyError(
            "La ruta no corresponde a un archivo."
        )

    return normalized, target
