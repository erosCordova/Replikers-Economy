from __future__ import annotations

from sqlalchemy.orm import Session

from app.execution.policy import (
    ExecutionPolicyError,
)
from app.models.execution import (
    ExecutionWorkspace,
)
from app.services.workspace_service import (
    list_workspace_files,
    log_tool_execution,
    read_text_file,
    write_text_file,
)


class ToolGateway:
    """
    Autoridad unica para operaciones
    sobre un workspace.

    Ningun agente debe acceder directamente
    al filesystem.
    """

    def __init__(
        self,
        *,
        db: Session,
        workspace:
            ExecutionWorkspace,
    ):
        self.db = db

        self.workspace = (
            workspace
        )

    def list_files(
        self,
    ) -> list[str]:
        tool_name = (
            "workspace_list_files"
        )

        try:
            result = (
                list_workspace_files(
                    workspace=
                        self.workspace
                )
            )

            log_tool_execution(
                db=self.db,
                workspace=
                    self.workspace,
                tool_name=
                    tool_name,
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
                workspace=
                    self.workspace,
                tool_name=
                    tool_name,
                status="denied",
                error_summary=
                    str(exc),
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

        try:
            result = (
                read_text_file(
                    workspace=
                        self.workspace,
                    relative_path=
                        path,
                )
            )

            log_tool_execution(
                db=self.db,
                workspace=
                    self.workspace,
                tool_name=
                    tool_name,
                status="success",
                target_path=
                    path,
                output_summary=(
                    f"{len(result.encode('utf-8'))} bytes"
                ),
            )

            self.db.flush()

            return result

        except Exception as exc:
            log_tool_execution(
                db=self.db,
                workspace=
                    self.workspace,
                tool_name=
                    tool_name,
                status="denied",
                target_path=
                    path,
                error_summary=
                    str(exc),
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

        try:
            artifact = (
                write_text_file(
                    db=self.db,
                    workspace=
                        self.workspace,
                    relative_path=
                        path,
                    content=
                        content,
                )
            )

            log_tool_execution(
                db=self.db,
                workspace=
                    self.workspace,
                tool_name=
                    tool_name,
                status="success",
                target_path=
                    path,
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
                workspace=
                    self.workspace,
                tool_name=
                    tool_name,
                status="denied",
                target_path=
                    path,
                error_summary=
                    str(exc),
            )

            self.db.flush()

            raise
