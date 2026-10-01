from pathlib import Path, PurePosixPath


class ExecutionPolicyError(ValueError):
    pass


DISALLOWED_PARTS = {
    "",
    ".",
    "..",
}


def normalize_relative_path(
    value: str,
) -> str:
    raw = value.strip().replace(
        "\\",
        "/",
    )

    if not raw:
        raise ExecutionPolicyError(
            "La ruta no puede estar vacia."
        )

    path = PurePosixPath(
        raw
    )

    if path.is_absolute():
        raise ExecutionPolicyError(
            "No se permiten rutas absolutas."
        )

    parts = path.parts

    if any(
        part in DISALLOWED_PARTS
        for part in parts
    ):
        raise ExecutionPolicyError(
            "La ruta contiene segmentos no permitidos."
        )

    if ":" in parts[0]:
        raise ExecutionPolicyError(
            "No se permiten rutas de unidad."
        )

    normalized = "/".join(
        parts
    )

    if len(normalized) > 900:
        raise ExecutionPolicyError(
            "La ruta supera el limite permitido."
        )

    return normalized


def resolve_inside_workspace(
    *,
    workspace_root: Path,
    relative_path: str,
) -> Path:
    normalized = normalize_relative_path(
        relative_path
    )

    root = workspace_root.resolve()

    candidate = (
        root
        / normalized
    ).resolve(
        strict=False
    )

    if (
        candidate != root
        and root
        not in candidate.parents
    ):
        raise ExecutionPolicyError(
            "La ruta intenta salir del workspace."
        )

    return candidate


def ensure_workspace_ready(
    status: str,
):
    if status != "ready":
        raise ExecutionPolicyError(
            "El workspace no esta disponible "
            "para escritura."
        )


def validate_text_payload(
    *,
    content: str,
    max_file_bytes: int,
) -> bytes:
    payload = content.encode(
        "utf-8"
    )

    if len(payload) > max_file_bytes:
        raise ExecutionPolicyError(
            "El archivo supera el limite "
            "de bytes permitido."
        )

    return payload
