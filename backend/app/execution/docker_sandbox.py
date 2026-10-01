from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import time
import uuid

from app.execution.sandbox_policy import (
    SandboxLimits,
    validate_python_target,
)


class SandboxError(RuntimeError):
    """Error base del sandbox."""


class SandboxUnavailableError(SandboxError):
    """Docker rootless no esta disponible."""


class SandboxStartError(SandboxError):
    """Docker no pudo crear el sandbox."""


@dataclass(frozen=True)
class SandboxResult:
    operation: str
    image: str
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool
    duration_ms: int

    @property
    def ok(self) -> bool:
        return (
            not self.timed_out
            and self.exit_code == 0
        )

    def as_dict(self) -> dict:
        return {
            "operation": self.operation,
            "image": self.image,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "timed_out": self.timed_out,
            "duration_ms": self.duration_ms,
            "ok": self.ok,
        }


class DockerSandboxRunner:
    """
    Ejecutor controlado para codigo de Replikers.

    Docker solo es accesible desde esta capa
    determinista del backend. Los agentes nunca
    reciben acceso directo al Docker CLI.
    """

    def __init__(
        self,
        *,
        context: str = "rootless",
        python_image: str = "python:3.13-alpine",
        limits: SandboxLimits | None = None,
    ):
        self.context = context
        self.python_image = python_image
        self.limits = limits or SandboxLimits()

        self.limits.validate()

        docker_binary = shutil.which(
            "docker"
        )

        if docker_binary is None:
            raise SandboxUnavailableError(
                "Docker CLI no esta disponible."
            )

        self.docker_binary = docker_binary

    def _prefix(self) -> list[str]:
        return [
            self.docker_binary,
            "--context",
            self.context,
        ]

    def _docker(
        self,
        args: list[str],
        *,
        timeout_seconds: int,
    ) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                *self._prefix(),
                *args,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
            shell=False,
        )

    def daemon_ready(self) -> bool:
        try:
            result = self._docker(
                ["info"],
                timeout_seconds=5,
            )
        except (
            OSError,
            subprocess.TimeoutExpired,
        ):
            return False

        return result.returncode == 0

    def image_ready(
        self,
        image: str,
    ) -> bool:
        try:
            result = self._docker(
                [
                    "image",
                    "inspect",
                    image,
                ],
                timeout_seconds=5,
            )
        except (
            OSError,
            subprocess.TimeoutExpired,
        ):
            return False

        return result.returncode == 0

    def _container_name(
        self,
        operation: str,
    ) -> str:
        safe_operation = operation.replace(
            "_",
            "-",
        )

        return (
            "replikers-sbx-"
            f"{safe_operation}-"
            f"{uuid.uuid4().hex[:12]}"
        )

    def _remove_container(
        self,
        name: str,
    ) -> None:
        try:
            self._docker(
                [
                    "rm",
                    "-f",
                    name,
                ],
                timeout_seconds=5,
            )
        except Exception:
            pass

    def _kill_container(
        self,
        name: str,
    ) -> None:
        try:
            self._docker(
                [
                    "kill",
                    name,
                ],
                timeout_seconds=5,
            )
        except Exception:
            pass

    def _decode_output(
        self,
        value: bytes,
    ) -> str:
        truncated = (
            len(value)
            > self.limits.max_output_bytes
        )

        if truncated:
            value = value[
                : self.limits.max_output_bytes
            ]

        text = value.decode(
            "utf-8",
            errors="replace",
        )

        if truncated:
            text += (
                "\n...[OUTPUT TRUNCATED]..."
            )

        return text

    def _logs(
        self,
        name: str,
    ) -> tuple[str, str]:
        try:
            result = self._docker(
                [
                    "logs",
                    name,
                ],
                timeout_seconds=5,
            )
        except Exception as exc:
            return (
                "",
                f"No se pudieron leer logs: {exc}",
            )

        return (
            self._decode_output(
                result.stdout
            ),
            self._decode_output(
                result.stderr
            ),
        )

    def _base_args(
        self,
        *,
        name: str,
        workspace_root: Path | None,
    ) -> list[str]:
        args = [
            "run",
            "-d",

            "--name",
            name,

            "--pull",
            "never",

            "--label",
            "replikers.sandbox=true",

            "--network",
            "none",

            "--read-only",

            "--cap-drop",
            "ALL",

            "--security-opt",
            "no-new-privileges",

            "--memory",
            self.limits.memory,

            "--cpus",
            self.limits.cpus,

            "--pids-limit",
            str(
                self.limits.pids_limit
            ),

            "--user",
            "65532:65532",

            "--tmpfs",
            (
                "/tmp:"
                "rw,noexec,nosuid,nodev,"
                f"size={self.limits.tmpfs_size}"
            ),

            "--ulimit",
            "nofile=256:256",

            "--hostname",
            "repliker-sandbox",

            "--env",
            "HOME=/tmp",

            "--env",
            "PYTHONDONTWRITEBYTECODE=1",

            "--env",
            "PYTHONNOUSERSITE=1",
        ]

        if workspace_root is not None:
            root = workspace_root.resolve()

            args.extend(
                [
                    "--volume",
                    f"{root}:/workspace:ro",

                    "--workdir",
                    "/workspace",
                ]
            )
        else:
            args.extend(
                [
                    "--workdir",
                    "/tmp",
                ]
            )

        return args

    def _execute(
        self,
        *,
        operation: str,
        image: str,
        command: list[str],
        workspace_root: Path | None,
    ) -> SandboxResult:
        if not self.daemon_ready():
            raise SandboxUnavailableError(
                "Docker rootless no responde."
            )

        if not self.image_ready(
            image
        ):
            raise SandboxUnavailableError(
                f"Imagen no disponible: {image}"
            )

        name = self._container_name(
            operation
        )

        started_at = time.monotonic()

        docker_args = [
            *self._base_args(
                name=name,
                workspace_root=workspace_root,
            ),
            image,
            *command,
        ]

        try:
            started = self._docker(
                docker_args,
                timeout_seconds=10,
            )
        except (
            OSError,
            subprocess.TimeoutExpired,
        ) as exc:
            raise SandboxStartError(
                "No se pudo iniciar el sandbox."
            ) from exc

        if started.returncode != 0:
            stderr = self._decode_output(
                started.stderr
            )

            self._remove_container(
                name
            )

            raise SandboxStartError(
                "Docker rechazo el sandbox: "
                + stderr
            )

        timed_out = False
        exit_code: int | None = None

        try:
            waited = self._docker(
                [
                    "wait",
                    name,
                ],
                timeout_seconds=(
                    self.limits
                    .timeout_seconds
                ),
            )

            if waited.returncode != 0:
                raise SandboxError(
                    "Docker wait fallo."
                )

            raw_code = (
                waited.stdout
                .decode(
                    "utf-8",
                    errors="replace",
                )
                .strip()
            )

            exit_code = int(
                raw_code
            )

        except subprocess.TimeoutExpired:
            timed_out = True

            self._kill_container(
                name
            )

        stdout, stderr = self._logs(
            name
        )

        self._remove_container(
            name
        )

        duration_ms = int(
            (
                time.monotonic()
                - started_at
            )
            * 1000
        )

        if timed_out:
            if stderr:
                stderr += "\n"

            stderr += (
                "Sandbox detenido por timeout."
            )

        return SandboxResult(
            operation=operation,
            image=image,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            timed_out=timed_out,
            duration_ms=duration_ms,
        )

    def probe(self) -> SandboxResult:
        return self._execute(
            operation="probe",
            image=self.python_image,
            workspace_root=None,
            command=[
                "python",
                "-B",
                "-c",
                (
                    "print("
                    "'REPLIKERS_SANDBOX_OK'"
                    ")"
                ),
            ],
        )

    def run_python_file(
        self,
        *,
        workspace_root: Path,
        relative_path: str,
    ) -> SandboxResult:
        normalized, _target = (
            validate_python_target(
                workspace_root=workspace_root,
                relative_path=relative_path,
            )
        )

        return self._execute(
            operation="run_python",
            image=self.python_image,
            workspace_root=workspace_root,
            command=[
                "python",
                "-B",
                (
                    "/workspace/"
                    + normalized
                ),
            ],
        )
