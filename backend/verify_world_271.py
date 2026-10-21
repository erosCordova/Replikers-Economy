import hashlib
import ipaddress
import os
import re
import secrets
import socket
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
TESTS = BACKEND / "tests"
BACKUPS = Path.home() / "Documents/replikers-world-backups"

SOURCES = {
    "base8": BACKUPS / "replikers_world_costos_1e64b4d3d0b9720a.db",
    "base10": BACKUPS / "replikers_world_costos_fix_501af149eac67267.db",
    "base11": BACKUPS / "replikers_world_events_172d128ed43723b0.db",
}

EXPECTED_COUNTS = {
    "base8": (8, 0),
    "base10": (10, 1),
    "base11": (11, 2),
}

MODULES = [
    BACKEND / "app/agentic" / name
    for name in (
        "world_autonomy_runtime.py",
        "world_social_learning.py",
        "world_governed_runtime.py",
        "world_event_runtime.py",
        "world_scheduler_bridge.py",
        "world_scheduler_lifecycle.py",
    )
]

def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def verify_database(path):
    with sqlite3.connect(
        path.resolve().as_uri() + "?mode=ro",
        uri=True,
    ) as db:
        db.execute("PRAGMA query_only=ON")

        assert db.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0] == "ok"

        assert not db.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

def clone(source, label):
    target = BACKUPS / (
        "rw_verify_"
        + label
        + "_"
        + secrets.token_hex(8)
        + ".db"
    )

    with sqlite3.connect(
        source.resolve().as_uri() + "?mode=ro",
        uri=True,
    ) as origin:
        with sqlite3.connect(str(target)) as copy:
            origin.backup(copy)

    return target

def clean_autonomy_history(path):
    with sqlite3.connect(str(path)) as db:
        db.execute("PRAGMA foreign_keys=ON")

        tables = {
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'"
            )
        }

        protected = {
            "users",
            "replikers",
            "ledger_accounts",
            "ledger_transactions",
            "world_agent_autonomy_policies",
        }

        roots = {
            "world_negotiations",
            "world_negotiation_events",
            "world_agent_events",
            "world_agent_memories",
        }

        removable = roots & tables

        def quote(name):
            return '"' + name.replace('"', '""') + '"'

        dependencies = {
            table: {
                row[2]
                for row in db.execute(
                    "PRAGMA foreign_key_list("
                    + quote(table)
                    + ")"
                )
            }
            for table in tables
        }

        while True:
            expanded = removable | {
                table
                for table, parents in dependencies.items()
                if parents & removable
            }

            if expanded == removable:
                break

            removable = expanded

        if removable & protected:
            raise RuntimeError(
                "La limpieza afectaria datos protegidos."
            )

        before = {
            table: db.execute(
                "SELECT * FROM " + quote(table)
            ).fetchall()
            for table in protected & tables
        }

        db.execute("PRAGMA foreign_keys=OFF")

        try:
            db.execute("BEGIN IMMEDIATE")

            for table in sorted(removable):
                db.execute(
                    "DELETE FROM " + quote(table)
                )

            if db.execute(
                "PRAGMA foreign_key_check"
            ).fetchall():
                raise RuntimeError(
                    "Referencias SQLite invalidas."
                )

            for table, original_rows in before.items():
                current = db.execute(
                    "SELECT * FROM " + quote(table)
                ).fetchall()

                if current != original_rows:
                    raise RuntimeError(
                        "Datos economicos o de agentes alterados."
                    )

            db.commit()

        except Exception:
            db.rollback()
            raise

        finally:
            db.execute("PRAGMA foreign_keys=ON")

    verify_database(path)

def run_suite(name, filenames, database, expected):
    env = os.environ.copy()

    env.update({
        "DATABASE_URL": "sqlite:///" + database.as_posix(),
        "REPLIKERS_WORLD_TEST_DB": str(database),
        "REPLIKERS_WORLD_ATOMIC_TEST_DB": str(database),
        "ENVIRONMENT": "development",
        "ECONOMY_MODE": "simulation",
        "REAL_PAYMENTS_ENABLED": "false",
        "RW_SUPERVISOR_BIND": "0",
        "AUTO_ENABLED": "false",
        "GOOGLE_API_KEY": "",
        "GEMINI_API_KEY": "",
        "GOOGLE_GENAI_USE_VERTEXAI": "false",
        "SECRET_KEY": secrets.token_urlsafe(48),
        "PYTHONPATH": str(BACKEND),
        "PYTHONDONTWRITEBYTECODE": "1",
    })

    # Bloqueo de conexiones TCP externas.
    guarded_pytest = r'''
import socket
import ipaddress
import sys
import pytest

connect_original = socket.socket.connect
connect_ex_original = socket.socket.connect_ex
getaddrinfo_original = socket.getaddrinfo

def check(sock, address):
    if sock.family in (socket.AF_INET, socket.AF_INET6):
        if not isinstance(address, tuple):
            raise OSError("Direccion invalida")

        host = str(address[0]).split("%")[0]

        if host != "localhost":
            try:
                ip = ipaddress.ip_address(host)
            except ValueError:
                raise OSError("Conexion externa bloqueada")

            if not ip.is_loopback:
                raise OSError("Conexion externa bloqueada")

    elif sock.family != getattr(socket, "AF_UNIX", -1):
        raise OSError("Socket no autorizado")

def guarded_connect(sock, address):
    check(sock, address)
    return connect_original(sock, address)

def guarded_connect_ex(sock, address):
    check(sock, address)
    return connect_ex_original(sock, address)

def guarded_getaddrinfo(host, port, *args, **kwargs):
    if host is not None:
        name = str(host).split("%")[0]

        if name != "localhost":
            try:
                ip = ipaddress.ip_address(name)
            except ValueError:
                raise OSError("DNS externo bloqueado")

            if not ip.is_loopback:
                raise OSError("DNS externo bloqueado")

    return getaddrinfo_original(
        host, port, *args, **kwargs
    )

socket.socket.connect = guarded_connect
socket.socket.connect_ex = guarded_connect_ex
socket.getaddrinfo = guarded_getaddrinfo

raise SystemExit(pytest.main(sys.argv[1:]))
'''

    command = [
        sys.executable,
        "-c",
        guarded_pytest,
        "-p",
        "no:cacheprovider",
        "-q",
        "--tb=short",
        "--maxfail=1",
        *[str(TESTS / name) for name in filenames],
    ]

    result = subprocess.run(
        command,
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=240,
    )

    matches = re.findall(
        r"(\d+)\s+passed\b",
        result.stdout,
    )

    actual = int(matches[-1]) if matches else -1

    if result.returncode != 0 or actual != expected:
        print(
            "\nERROR_EN_SUITE=" + name,
            flush=True,
        )
        print(result.stdout[-3500:], flush=True)
        print(result.stderr[-1000:], flush=True)
        raise RuntimeError(
            "La suite "
            + name
            + " no supero sus verificaciones."
        )

    verify_database(database)

    print(
        name + "=" + str(actual) + "_APROBADAS",
        flush=True,
    )

    return actual

def main():
    print("=" * 64)
    print("REPLIKERS WORLD - VALIDACION ESTABLE 271 PRUEBAS")
    print("=" * 64)

    print("\n===== 1. INTEGRIDAD DE FUENTES =====")

    protected = {}

    for label, path in SOURCES.items():
        if not path.is_file():
            raise RuntimeError(
                "Base ausente: " + path.name
            )

        verify_database(path)

        with sqlite3.connect(
            path.resolve().as_uri() + "?mode=ro",
            uri=True,
        ) as db:
            actual = (
                db.execute(
                    "SELECT COUNT(*) FROM ledger_transactions"
                ).fetchone()[0],
                db.execute(
                    "SELECT COUNT(*) FROM world_contract_expenses"
                ).fetchone()[0],
            )

        if actual != EXPECTED_COUNTS[label]:
            raise RuntimeError(
                "Base historica incompatible: "
                + path.name
            )

        protected[path] = fingerprint(path)
        print(label.upper() + "=VERIFICADA")

    for path in (
        *MODULES,
        BACKEND / "replikers.db",
    ):
        if path.is_file():
            protected[path] = fingerprint(path)

    test_file = TESTS / "test_world_owner_isolation.py"

    if not test_file.is_file():
        raise RuntimeError(
            "Falta la prueba del aislamiento instalado."
        )

    print("\n===== 2. PREPARAR COPIAS INDEPENDIENTES =====")

    databases = {
        "AISLAMIENTO": clone(SOURCES["base11"], "aislamiento"),
        "SUPERVISOR": clone(SOURCES["base11"], "supervisor"),
        "WORLD": clone(SOURCES["base11"], "world"),
        "AUTONOMIA": clone(SOURCES["base8"], "autonomia"),
        "CONCURRENCIA": clone(SOURCES["base10"], "concurrencia"),
        "ECONOMIA": clone(SOURCES["base8"], "economia"),
    }

    # La autonomia necesita 8 transacciones y
    # las tablas de historial sin registros previos.
    clean_autonomy_history(databases["AUTONOMIA"])

    # World necesita su historial social intacto.
    print("AUTONOMIA=HISTORIAL_LIMPIO")
    print("WORLD=PROCEDENCIA_HISTORICA_CONSERVADA")
    print("BASES_ORIGINALES=SOLO_LECTURA")

    groups = [
        (
            "AISLAMIENTO",
            ["test_world_owner_isolation.py"],
            11,
        ),
        (
            "SUPERVISOR",
            [
                "test_world_scheduler_lifecycle.py",
                "test_world_scheduler_status.py",
                "test_world_scheduler_bridge.py",
                "test_world_autonomous_scheduler.py",
                "test_world_gemini_quota_guard.py",
                "test_world_gemini_json_wiring.py",
                "test_world_gemini_json_client.py",
                "test_world_gemini_model_config.py",
                "test_world_gemini_governed.py",
            ],
            62,
        ),
        (
            "WORLD",
            [
                "test_world_governed_runtime.py",
                "test_world_autonomy_policy.py",
                "test_world_read_api.py",
                "test_world_observability.py",
                "test_world_events.py",
            ],
            104,
        ),
        (
            "AUTONOMIA",
            ["test_world_autonomy_runtime.py"],
            16,
        ),
        (
            "CONCURRENCIA",
            ["test_world_atomic_cost_service.py"],
            15,
        ),
        (
            "ECONOMIA",
            [
                "test_world_cost_service.py",
                "test_world_strategy_evaluation.py",
                "test_world_contract_service.py",
                "test_world_settlement_service.py",
            ],
            63,
        ),
    ]

    print("\n===== 3. PRUEBAS COMPLETAS =====")

    total = 0

    for name, filenames, expected in groups:
        total += run_suite(
            name,
            filenames,
            databases[name],
            expected,
        )

    print("\n===== 4. PROTECCION DE ORIGINALES =====")

    for path, previous_hash in protected.items():
        if (
            not path.is_file()
            or fingerprint(path) != previous_hash
        ):
            raise RuntimeError(
                "Archivo original modificado: "
                + path.name
            )

    if total != 271:
        raise RuntimeError(
            "Total inesperado: " + str(total)
        )

    print("TOTAL_PRUEBAS_APROBADAS=" + str(total))
    print("ARCHIVOS_ORIGINALES_INTACTOS=True")
    print("GEMINI_REAL=NO")
    print("SUPABASE=NO")
    print("PAGOS_REALES=0")
    print("CONTROLADOR_CONTINUO=DESACTIVADO")
    print("RESULTADO=REPLIKERS_WORLD_VALIDADO")

try:
    main()
except Exception as error:
    print(
        "ERROR_TIPO=" + type(error).__name__
    )
    print(
        "ERROR_DETALLE="
        + str(error).encode(
            "ascii", "backslashreplace"
        ).decode("ascii")[:400]
    )
    print("RESULTADO=VALIDACION_PENDIENTE")

print("TERMINAL=PERMANECE_ABIERTA")
