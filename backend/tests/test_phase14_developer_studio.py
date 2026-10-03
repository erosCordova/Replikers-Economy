from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import app.models  # noqa: F401

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.base import Base
from app.models.repliker import Repliker
from app.models.user import User
from app.schemas.repliker_developer import (
    ReplikerDeveloperUpdate,
)
from app.services.repliker_developer_service import (
    ReplikerDeveloperError,
    developer_prompt_section,
    developer_snapshot,
    materialize_developer_module,
    save_developer_module,
    validate_developer_source,
)


VALID_CODE = """
import math

def run(data):
    value = data.get("value", 0)
    return {
        "resultado": math.sqrt(value)
    }
""".strip()


class FakeGateway:
    writes = []

    def __init__(
        self,
        *,
        db,
        workspace,
    ):
        _ = db
        _ = workspace

    def write_text(
        self,
        *,
        path,
        content,
    ):
        self.writes.append(
            (
                path,
                content,
            )
        )

        return SimpleNamespace(
            sha256="test"
        )


class Phase14DeveloperStudioTests(
    unittest.TestCase
):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:"
        )

        Base.metadata.create_all(
            self.engine
        )

        self.db = Session(
            bind=self.engine,
            expire_on_commit=False,
        )

        owner = User(
            full_name="Propietario",
            email="developer@test.local",
            password_hash="test",
            role="user",
            is_active=True,
        )

        self.db.add(owner)
        self.db.flush()

        self.repliker = Repliker(
            owner_id=owner.id,
            name="Atlas",
            specialty="Backend Developer",
            description="Servidor.",
            status="available",
            reputation_score=80,
            base_price_credits=50,
            balance_credits=0,
            total_earnings_credits=0,
            jobs_completed=0,
            is_active=True,
        )

        self.db.add(
            self.repliker
        )

        self.db.commit()

        FakeGateway.writes = []

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_valid_code_is_accepted(
        self,
    ):
        source = (
            validate_developer_source(
                VALID_CODE
            )
        )

        self.assertIn(
            "def run(data):",
            source,
        )

    def test_dangerous_import_is_rejected(
        self,
    ):
        source = """
import subprocess

def run(data):
    return data
"""

        with self.assertRaises(
            ReplikerDeveloperError
        ):
            validate_developer_source(
                source
            )

    def test_missing_entrypoint_is_rejected(
        self,
    ):
        with self.assertRaises(
            ReplikerDeveloperError
        ):
            validate_developer_source(
                "def otra(data):\n"
                "    return data\n"
            )

    def test_save_and_version(
        self,
    ):
        first = save_developer_module(
            db=self.db,
            repliker_id=
                self.repliker.id,
            payload=
                ReplikerDeveloperUpdate(
                    enabled=True,
                    source_code=
                        VALID_CODE,
                ),
        )

        self.db.commit()

        second = save_developer_module(
            db=self.db,
            repliker_id=
                self.repliker.id,
            payload=
                ReplikerDeveloperUpdate(
                    enabled=True,
                    source_code=
                        VALID_CODE,
                ),
        )

        self.db.commit()

        self.assertEqual(
            first["version"],
            1,
        )

        self.assertEqual(
            second["version"],
            2,
        )

        self.assertTrue(
            second["enabled"]
        )

        self.assertEqual(
            len(
                second["checksum"]
            ),
            64,
        )

    def test_disabled_default_is_safe(
        self,
    ):
        result = (
            developer_snapshot(
                db=self.db,
                repliker_id=
                    self.repliker.id,
            )
        )

        self.assertFalse(
            result["enabled"]
        )

        self.assertEqual(
            result["version"],
            0,
        )

    def test_materialization_uses_gateway(
        self,
    ):
        save_developer_module(
            db=self.db,
            repliker_id=
                self.repliker.id,
            payload=
                ReplikerDeveloperUpdate(
                    enabled=True,
                    source_code=
                        VALID_CODE,
                ),
        )

        self.db.commit()

        workspace = SimpleNamespace(
            id=10,
            status="ready",
        )

        with patch(
            "app.services."
            "repliker_developer_service."
            "ToolGateway",
            FakeGateway,
        ):
            context = (
                materialize_developer_module(
                    db=self.db,
                    workspace=workspace,
                    repliker_id=
                        self.repliker.id,
                )
            )

        self.assertTrue(
            context["enabled"]
        )

        self.assertEqual(
            FakeGateway.writes[0][0],
            "repliker_extension.py",
        )

    def test_prompt_explains_security_boundary(
        self,
    ):
        text = developer_prompt_section(
            {
                "enabled": True,
                "filename":
                    "repliker_extension.py",
            }
        )

        self.assertIn(
            "no amplía tus permisos",
            text,
        )

        self.assertIn(
            "herramienta segura",
            text,
        )

    def test_module_is_materialized_before_baseline(
        self,
    ):
        source = Path(
            "app/services/"
            "execution_agent_service.py"
        ).read_text(
            encoding="utf-8",
        )

        materialize_position = (
            source.index(
                "developer_context = ("
            )
        )

        baseline_position = (
            source.index(
                "baseline = (",
                materialize_position,
            )
        )

        self.assertLess(
            materialize_position,
            baseline_position,
        )

    def test_router_is_registered(
        self,
    ):
        source = Path(
            "app/main.py"
        ).read_text(
            encoding="utf-8",
        )

        self.assertIn(
            "repliker_developer_router",
            source,
        )


if __name__ == "__main__":
    unittest.main()
