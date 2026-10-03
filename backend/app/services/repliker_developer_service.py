from __future__ import annotations

import ast
import hashlib

from datetime import (
    datetime,
    timezone,
)

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.execution.tool_gateway import (
    ToolGateway,
)
from app.models.execution import (
    ExecutionWorkspace,
)
from app.models.repliker_developer import (
    ReplikerDeveloperModule,
)
from app.schemas.repliker_developer import (
    ReplikerDeveloperUpdate,
)


DEVELOPER_FILENAME = (
    "repliker_extension.py"
)

DEVELOPER_ENTRYPOINT = "run"

MAX_SOURCE_BYTES = 40_000


SAFE_IMPORTS = {
    "collections",
    "datetime",
    "decimal",
    "fractions",
    "functools",
    "itertools",
    "json",
    "math",
    "random",
    "re",
    "statistics",
    "string",
    "typing",
}


BLOCKED_NAMES = {
    "__import__",
    "breakpoint",
    "compile",
    "eval",
    "exec",
    "globals",
    "input",
    "locals",
    "open",
    "vars",
}


class ReplikerDeveloperError(
    ValueError
):
    pass


def _source_checksum(
    source_code: str,
) -> str:
    return hashlib.sha256(
        source_code.encode(
            "utf-8"
        )
    ).hexdigest()


def _is_safe_literal(
    node: ast.AST,
) -> bool:
    if isinstance(
        node,
        ast.Constant,
    ):
        return True

    if isinstance(
        node,
        (
            ast.List,
            ast.Tuple,
            ast.Set,
        ),
    ):
        return all(
            _is_safe_literal(
                item
            )
            for item
            in node.elts
        )

    if isinstance(
        node,
        ast.Dict,
    ):
        return all(
            (
                key is None
                or _is_safe_literal(
                    key
                )
            )
            and _is_safe_literal(
                value
            )
            for key, value
            in zip(
                node.keys,
                node.values,
            )
        )

    return False


def validate_developer_source(
    source_code: str,
) -> str:
    source = source_code.strip()

    if not source:
        raise ReplikerDeveloperError(
            "El código está vacío."
        )

    size = len(
        source.encode(
            "utf-8"
        )
    )

    if size > MAX_SOURCE_BYTES:
        raise ReplikerDeveloperError(
            "El código supera el tamaño permitido."
        )

    try:
        tree = ast.parse(
            source,
            filename=
                DEVELOPER_FILENAME,
            mode="exec",
        )

    except SyntaxError as exc:
        raise ReplikerDeveloperError(
            "El código contiene "
            "un error de sintaxis: "
            f"{exc.msg}."
        ) from exc

    run_function = None

    for node in tree.body:
        if isinstance(
            node,
            (
                ast.Import,
                ast.ImportFrom,
                ast.FunctionDef,
            ),
        ):
            pass

        elif isinstance(
            node,
            ast.Assign,
        ):
            if not _is_safe_literal(
                node.value
            ):
                raise ReplikerDeveloperError(
                    "Solo se permiten valores "
                    "constantes fuera de funciones."
                )

        elif isinstance(
            node,
            ast.AnnAssign,
        ):
            if (
                node.value is not None
                and not _is_safe_literal(
                    node.value
                )
            ):
                raise ReplikerDeveloperError(
                    "Solo se permiten valores "
                    "constantes fuera de funciones."
                )

        else:
            raise ReplikerDeveloperError(
                "No se permite ejecutar "
                "instrucciones directamente "
                "al cargar el módulo."
            )

        if (
            isinstance(
                node,
                ast.FunctionDef,
            )
            and node.name
            == DEVELOPER_ENTRYPOINT
        ):
            run_function = node

    if run_function is None:
        raise ReplikerDeveloperError(
            "El código debe definir "
            "la función run(data)."
        )

    if run_function.decorator_list:
        raise ReplikerDeveloperError(
            "La función principal "
            "no puede utilizar decoradores."
        )

    args = run_function.args

    if (
        len(
            args.posonlyargs
            + args.args
        )
        != 1
        or args.vararg
        is not None
        or args.kwarg
        is not None
        or args.kwonlyargs
    ):
        raise ReplikerDeveloperError(
            "La función principal "
            "debe tener exactamente "
            "la forma run(data)."
        )

    for node in ast.walk(
        tree
    ):
        if isinstance(
            node,
            ast.Import,
        ):
            for alias in node.names:
                root = (
                    alias.name
                    .split(
                        ".",
                        1,
                    )[0]
                )

                if (
                    root
                    not in SAFE_IMPORTS
                ):
                    raise (
                        ReplikerDeveloperError(
                            "La biblioteca "
                            f"'{root}' no está "
                            "permitida."
                        )
                    )

        if isinstance(
            node,
            ast.ImportFrom,
        ):
            root = (
                str(
                    node.module
                    or ""
                )
                .split(
                    ".",
                    1,
                )[0]
            )

            if (
                root
                not in SAFE_IMPORTS
            ):
                raise (
                    ReplikerDeveloperError(
                        "La biblioteca "
                        f"'{root}' no está "
                        "permitida."
                    )
                )

        if isinstance(
            node,
            ast.Name,
        ):
            if (
                node.id
                in BLOCKED_NAMES
                or node.id.startswith(
                    "__"
                )
            ):
                raise (
                    ReplikerDeveloperError(
                        "El código utiliza "
                        "una operación no permitida."
                    )
                )

        if isinstance(
            node,
            ast.Attribute,
        ):
            if node.attr.startswith(
                "__"
            ):
                raise (
                    ReplikerDeveloperError(
                        "No se permite acceder "
                        "a atributos internos."
                    )
                )

        if isinstance(
            node,
            (
                ast.Global,
                ast.Nonlocal,
            ),
        ):
            raise ReplikerDeveloperError(
                "No se permiten variables "
                "globales modificables."
            )

    return (
        source.rstrip()
        + "\n"
    )


def get_developer_module(
    *,
    db: Session,
    repliker_id: int,
) -> ReplikerDeveloperModule | None:
    return db.scalar(
        select(
            ReplikerDeveloperModule
        )
        .where(
            ReplikerDeveloperModule
            .repliker_id
            == repliker_id
        )
    )


def developer_snapshot(
    *,
    db: Session,
    repliker_id: int,
) -> dict:
    module = get_developer_module(
        db=db,
        repliker_id=repliker_id,
    )

    if module is None:
        return {
            "repliker_id":
                repliker_id,
            "enabled":
                False,
            "language":
                "python",
            "filename":
                DEVELOPER_FILENAME,
            "entrypoint":
                DEVELOPER_ENTRYPOINT,
            "source_code":
                "",
            "checksum":
                "",
            "version":
                0,
        }

    return {
        "repliker_id":
            repliker_id,
        "enabled":
            module.enabled,
        "language":
            module.language,
        "filename":
            module.filename,
        "entrypoint":
            module.entrypoint,
        "source_code":
            module.source_code,
        "checksum":
            module.checksum,
        "version":
            module.version,
    }


def save_developer_module(
    *,
    db: Session,
    repliker_id: int,
    payload:
        ReplikerDeveloperUpdate,
) -> dict:
    raw_source = (
        payload.source_code
        or ""
    )

    source = (
        raw_source.strip()
    )

    if payload.enabled:
        source = (
            validate_developer_source(
                source
            )
        )

    elif source:
        source = (
            validate_developer_source(
                source
            )
        )

    module = get_developer_module(
        db=db,
        repliker_id=repliker_id,
    )

    if module is None:
        module = (
            ReplikerDeveloperModule(
                repliker_id=
                    repliker_id,
                version=1,
            )
        )

        db.add(
            module
        )

    else:
        module.version += 1

    module.enabled = (
        payload.enabled
    )

    module.language = (
        "python"
    )

    module.filename = (
        DEVELOPER_FILENAME
    )

    module.entrypoint = (
        DEVELOPER_ENTRYPOINT
    )

    module.source_code = (
        source
    )

    module.checksum = (
        _source_checksum(
            source
        )
        if source
        else ""
    )

    module.validated_at = (
        datetime.now(
            timezone.utc
        )
        if source
        else None
    )

    db.flush()

    return developer_snapshot(
        db=db,
        repliker_id=repliker_id,
    )


def developer_prompt_section(
    context: dict | None,
) -> str:
    if (
        not context
        or not context.get(
            "enabled"
        )
    ):
        return ""

    filename = str(
        context.get(
            "filename",
            DEVELOPER_FILENAME,
        )
    )

    return (
        "\n\n"
        "MODULO PERSONAL DEL REPLIKER\n\n"
        f"Existe un módulo llamado {filename} "
        "dentro de tu espacio de trabajo.\n"
        "Fue definido y validado por el "
        "propietario del Repliker.\n"
        "Puedes utilizarlo cuando sea pertinente "
        "para la tarea.\n"
        "Su función principal es run(data).\n"
        "No modifiques ni reemplaces ese archivo.\n"
        "Si necesitas ejecutarlo, hazlo "
        "exclusivamente a través de la "
        "herramienta segura de ejecución.\n"
        "El módulo no amplía tus permisos ni "
        "puede evadir las restricciones "
        "del sistema."
    )


def materialize_developer_module(
    *,
    db: Session,
    workspace:
        ExecutionWorkspace,
    repliker_id: int,
) -> dict:
    module = get_developer_module(
        db=db,
        repliker_id=repliker_id,
    )

    if (
        module is None
        or not module.enabled
        or not module.source_code
    ):
        return {
            "enabled":
                False,
        }

    try:
        source = (
            validate_developer_source(
                module.source_code
            )
        )

    except ReplikerDeveloperError:
        return {
            "enabled":
                False,
        }

    gateway = ToolGateway(
        db=db,
        workspace=workspace,
    )

    gateway.write_text(
        path=
            DEVELOPER_FILENAME,
        content=
            source,
    )

    return {
        "enabled":
            True,
        "filename":
            DEVELOPER_FILENAME,
        "entrypoint":
            DEVELOPER_ENTRYPOINT,
        "checksum":
            module.checksum,
        "version":
            module.version,
    }
