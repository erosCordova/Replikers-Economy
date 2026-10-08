from __future__ import annotations

from sqlalchemy.orm import Session

from app.execution.docker_sandbox import (
    DockerSandboxRunner,
    SandboxError,
    SandboxResult,
)
from app.execution.policy import (
    ExecutionPolicyError,
    ensure_workspace_ready,
    normalize_relative_path,
)
from app.models.execution import (
    ExecutionWorkspace,
)
from app.services.workspace_service import (
    list_workspace_files,
    log_tool_execution,
    read_text_file,
    workspace_root,
    write_text_file,
)


class ToolGateway:
    """
    Autoridad unica para operaciones
    sobre un workspace.

    Ningun agente debe acceder directamente
    al filesystem, Docker o subprocess.
    """

    def __init__(
        self,
        *,
        db: Session,
        workspace: ExecutionWorkspace,
        actor_repliker_id: int | None = None,
    ):
        self.db = db
        self.workspace = workspace
        self.actor_repliker_id = (
            actor_repliker_id
        )

    @staticmethod
    def _normalize_path(
        path: str,
    ) -> str:
        return normalize_relative_path(
            path
        )

    def list_files(
        self,
    ) -> list[str]:
        tool_name = (
            "workspace_list_files"
        )

        try:
            result = list_workspace_files(
                workspace=self.workspace
            )

            log_tool_execution(
                db=self.db,
                workspace=self.workspace,
                actor_repliker_id=
                    self.actor_repliker_id,
                tool_name=tool_name,
                status="success",
                output_summary=(
                    f"{len(result)} archivos"
                ),
            )

            self.db.flush()

            return result

        except Exception as exc:
            log_tool_execution(
                db=self.db,
                workspace=self.workspace,
                actor_repliker_id=
                    self.actor_repliker_id,
                tool_name=tool_name,
                status="denied",
                error_summary=str(exc),
            )

            self.db.flush()

            raise

    def read_text(
        self,
        *,
        path: str,
    ) -> str:
        tool_name = (
            "workspace_read_text"
        )

        normalized_path = (
            self._normalize_path(
                path
            )
        )

        try:
            result = read_text_file(
                workspace=self.workspace,
                relative_path=
                    normalized_path,
            )

            log_tool_execution(
                db=self.db,
                workspace=self.workspace,
                actor_repliker_id=
                    self.actor_repliker_id,
                tool_name=tool_name,
                status="success",
                target_path=
                    normalized_path,
                output_summary=(
                    f"{len(result.encode('utf-8'))} bytes"
                ),
            )

            self.db.flush()

            return result

        except Exception as exc:
            log_tool_execution(
                db=self.db,
                workspace=self.workspace,
                actor_repliker_id=
                    self.actor_repliker_id,
                tool_name=tool_name,
                status="denied",
                target_path=
                    normalized_path,
                error_summary=str(exc),
            )

            self.db.flush()

            raise

    def write_text(
        self,
        *,
        path: str,
        content: str,
    ):
        tool_name = (
            "workspace_write_text"
        )

        normalized_path = (
            self._normalize_path(
                path
            )
        )

        try:
            artifact = write_text_file(
                db=self.db,
                workspace=self.workspace,
                relative_path=
                    normalized_path,
                content=content,
            )

            log_tool_execution(
                db=self.db,
                workspace=self.workspace,
                actor_repliker_id=
                    self.actor_repliker_id,
                tool_name=tool_name,
                status="success",
                target_path=
                    normalized_path,
                input_summary=(
                    f"{len(content.encode('utf-8'))} bytes"
                ),
                output_summary=(
                    f"sha256={artifact.sha256}"
                ),
            )

            self.db.flush()

            return artifact

        except (
            ExecutionPolicyError,
            FileNotFoundError,
            OSError,
        ) as exc:
            log_tool_execution(
                db=self.db,
                workspace=self.workspace,
                actor_repliker_id=
                    self.actor_repliker_id,
                tool_name=tool_name,
                status="denied",
                target_path=
                    normalized_path,
                error_summary=str(exc),
            )

            self.db.flush()

            raise

    def run_python(
        self,
        *,
        path: str,
    ) -> SandboxResult:
        """
        Ejecuta exclusivamente un archivo Python
        existente dentro del workspace mediante
        Docker rootless.

        No acepta comandos shell, argumentos
        Docker ni rutas externas.
        """

        tool_name = "run_python"

        normalized_path = (
            self._normalize_path(
                path
            )
        )

        try:
            ensure_workspace_ready(
                self.workspace.status
            )

            root = workspace_root(
                self.workspace
            )

            runner = (
                DockerSandboxRunner()
            )

            result = (
                runner.run_python_file(
                    workspace_root=root,
                    relative_path=
                        normalized_path,
                )
            )

            if result.timed_out:
                log_status = "failed"

                error_summary = (
                    "timeout; "
                    f"duration_ms={result.duration_ms}; "
                    f"{result.stderr}"
                )

            elif result.ok:
                log_status = "success"
                error_summary = ""

            else:
                log_status = "failed"
                error_summary = (
                    result.stderr
                )

            output_summary = (
                f"exit_code={result.exit_code}; "
                f"duration_ms={result.duration_ms}; "
                f"image={result.image}"
            )

            if result.stdout:
                output_summary += (
                    "\nstdout:\n"
                    + result.stdout
                )

            log_tool_execution(
                db=self.db,
                workspace=self.workspace,
                actor_repliker_id=
                    self.actor_repliker_id,
                tool_name=tool_name,
                status=log_status,
                target_path=
                    normalized_path,
                input_summary=(
                    "isolated_python_execution"
                ),
                output_summary=
                    output_summary,
                error_summary=
                    error_summary,
            )

            self.db.flush()

            return result

        except (
            ExecutionPolicyError,
            FileNotFoundError,
            OSError,
        ) as exc:
            log_tool_execution(
                db=self.db,
                workspace=self.workspace,
                actor_repliker_id=
                    self.actor_repliker_id,
                tool_name=tool_name,
                status="denied",
                target_path=
                    normalized_path,
                error_summary=str(exc),
            )

            self.db.flush()

            raise

        except SandboxError as exc:
            log_tool_execution(
                db=self.db,
                workspace=self.workspace,
                actor_repliker_id=
                    self.actor_repliker_id,
                tool_name=tool_name,
                status="failed",
                target_path=
                    normalized_path,
                error_summary=str(exc),
            )

            self.db.flush()

            raise
