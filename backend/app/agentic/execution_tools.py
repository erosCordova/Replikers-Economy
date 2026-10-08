from __future__ import annotations

from langchain_core.tools import (
    BaseTool,
    StructuredTool,
)
from pydantic import (
    BaseModel,
    Field,
)
from sqlalchemy.orm import Session

from app.execution.docker_sandbox import (
    SandboxError,
)
from app.execution.tool_gateway import (
    ToolGateway,
)
from app.models.execution import (
    ExecutionWorkspace,
)


class WorkspaceReadInput(BaseModel):
    path: str = Field(
        min_length=1,
        max_length=900,
        description=(
            "Ruta relativa del archivo "
            "dentro del workspace."
        ),
    )


class WorkspaceWriteInput(BaseModel):
    path: str = Field(
        min_length=1,
        max_length=900,
        description=(
            "Ruta relativa del archivo "
            "dentro del workspace."
        ),
    )

    content: str = Field(
        max_length=2_000_000,
        description=(
            "Contenido UTF-8 completo "
            "que se escribira en el archivo."
        ),
    )


class RunPythonInput(BaseModel):
    path: str = Field(
        min_length=1,
        max_length=900,
        description=(
            "Ruta relativa de un archivo .py "
            "existente dentro del workspace."
        ),
    )


def build_execution_workspace_tools(
    *,
    db: Session,
    workspace: ExecutionWorkspace,
    actor_repliker_id: int | None = None,
) -> list[BaseTool]:
    """
    Construye las tools LangChain que un
    Repliker puede utilizar dentro de un
    workspace autorizado.

    Ninguna tool expone filesystem arbitrario,
    shell, subprocess, Docker CLI ni comandos
    del sistema.
    """

    gateway = ToolGateway(
        db=db,
        workspace=workspace,
        actor_repliker_id=
            actor_repliker_id,
    )

    def workspace_list_files() -> dict:
        """
        Lista todos los archivos visibles
        dentro del workspace asignado.
        """

        files = (
            gateway.list_files()
        )

        db.commit()

        return {
            "workspace_id":
                workspace.id,
            "files":
                files,
            "count":
                len(files),
        }

    def workspace_read_text(
        path: str,
    ) -> dict:
        """
        Lee un archivo de texto UTF-8
        dentro del workspace.
        """

        content = (
            gateway.read_text(
                path=path
            )
        )

        db.commit()

        return {
            "workspace_id":
                workspace.id,
            "path":
                path,
            "content":
                content,
        }

    def workspace_write_text(
        path: str,
        content: str,
    ) -> dict:
        """
        Crea o reemplaza un archivo de texto
        dentro del workspace.
        """

        artifact = (
            gateway.write_text(
                path=path,
                content=content,
            )
        )

        db.commit()

        db.refresh(
            artifact
        )

        return {
            "workspace_id":
                workspace.id,
            "artifact_id":
                artifact.id,
            "path":
                artifact.relative_path,
            "media_type":
                artifact.media_type,
            "size_bytes":
                artifact.size_bytes,
            "sha256":
                artifact.sha256,
        }

    def run_python(
        path: str,
    ) -> dict:
        """
        Ejecuta Python exclusivamente dentro
        del sandbox Docker autorizado.

        Si el sandbox no esta disponible,
        informa al agente mediante un resultado
        estructurado y nunca ejecuta Python
        directamente en el host.
        """
        try:
            result = gateway.run_python(
                path=path
            )

        except SandboxError as exc:
            # ToolGateway ya registra el fallo
            # en ToolExecutionLog. Confirmamos
            # esa auditoria antes de devolver
            # control al agente.
            db.commit()

            return {
                "workspace_id":
                    workspace.id,
                "path":
                    path,
                "operation":
                    "run_python",
                "image":
                    "",
                "exit_code":
                    None,
                "stdout":
                    "",
                "stderr":
                    str(exc),
                "timed_out":
                    False,
                "duration_ms":
                    0,
                "ok":
                    False,
                "sandbox_available":
                    False,
                "error":
                    str(exc),
            }

        db.commit()

        return {
            "workspace_id":
                workspace.id,
            "path":
                path,
            **result.as_dict(),
            "sandbox_available":
                True,
            "error":
                "",
        }


    return [
        StructuredTool.from_function(
            func=
                workspace_list_files,
            name=
                "workspace_list_files",
            description=(
                "Lista los archivos del workspace "
                "aislado asignado al contrato. "
                "Usala antes de modificar archivos "
                "para conocer la estructura actual."
            ),
        ),

        StructuredTool.from_function(
            func=
                workspace_read_text,
            name=
                "workspace_read_text",
            description=(
                "Lee el contenido completo de un "
                "archivo de texto del workspace. "
                "Solo acepta rutas relativas "
                "autorizadas."
            ),
            args_schema=
                WorkspaceReadInput,
        ),

        StructuredTool.from_function(
            func=
                workspace_write_text,
            name=
                "workspace_write_text",
            description=(
                "Crea o reemplaza un archivo de "
                "texto dentro del workspace "
                "asignado. No permite escribir "
                "fuera del workspace."
            ),
            args_schema=
                WorkspaceWriteInput,
        ),

        StructuredTool.from_function(
            func=
                run_python,
            name=
                "run_python",
            description=(
                "Ejecuta un archivo .py existente "
                "del workspace dentro de un "
                "contenedor Docker rootless "
                "aislado. No proporciona shell, "
                "red, argumentos Docker ni acceso "
                "al sistema anfitrion."
            ),
            args_schema=
                RunPythonInput,
        ),
    ]
