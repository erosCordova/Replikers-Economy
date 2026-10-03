from __future__ import annotations

import unittest

import app.models  # noqa: F401

from sqlalchemy import (
    create_engine,
    func,
    select,
)
from sqlalchemy.orm import Session

from app.api.routes.replikers import (
    router,
)
from app.database.base import Base
from app.models.agentic import (
    ReplikerToolAssignment,
)
from app.models.repliker import (
    Repliker,
    ReplikerSkill,
)
from app.models.repliker_studio import (
    ReplikerKnowledgeItem,
    ReplikerRule,
    ReplikerStudioProfile,
)
from app.models.user import User
from app.schemas.repliker_studio import (
    ReplikerStudioUpdate,
    StudioKnowledgeUpdate,
    StudioRuleUpdate,
    StudioSkillUpdate,
)
from app.services.repliker_studio_service import (
    ReplikerStudioError,
    studio_snapshot,
    update_repliker_studio,
)


class Phase14ReplikerStudioTests(
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

        self.owner = User(
            full_name="Propietario",
            email="studio@test.local",
            password_hash="test",
            role="user",
            is_active=True,
        )

        self.db.add(
            self.owner
        )

        self.db.flush()

        self.repliker = Repliker(
            owner_id=self.owner.id,
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

        self.db.flush()

        self.db.add(
            ReplikerSkill(
                repliker_id=
                    self.repliker.id,
                name="Python",
                level=70,
            )
        )

        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def payload(self):
        return ReplikerStudioUpdate(
            name="Atlas",
            specialty="Backend Developer",
            description=(
                "Especialista en servicios."
            ),
            base_price_credits=75,
            purpose=(
                "Construir servicios robustos."
            ),
            personality=(
                "Analítico y preciso."
            ),
            communication_style=(
                "Claro y directo."
            ),
            instructions=(
                "Prioriza seguridad y pruebas."
            ),
            skills=[
                StudioSkillUpdate(
                    name="Python",
                    level=95,
                ),
                StudioSkillUpdate(
                    name="FastAPI",
                    level=90,
                ),
            ],
            knowledge=[
                StudioKnowledgeUpdate(
                    title="Convenciones",
                    content=(
                        "Usar validación estricta."
                    ),
                ),
            ],
            rules=[
                StudioRuleUpdate(
                    title="Pruebas",
                    instruction=(
                        "No entregar sin pruebas."
                    ),
                    priority=100,
                ),
            ],
            tool_names=[
                "inspect_repliker_profile",
                "inspect_project",
            ],
        )

    def test_studio_tables_are_registered(
        self,
    ):
        self.assertIn(
            "repliker_studio_profiles",
            Base.metadata.tables,
        )

        self.assertIn(
            "repliker_knowledge_items",
            Base.metadata.tables,
        )

        self.assertIn(
            "repliker_rules",
            Base.metadata.tables,
        )

    def test_studio_routes_exist(
        self,
    ):
        paths = {
            route.path
            for route in router.routes
        }

        self.assertIn(
            "/replikers/{repliker_id}/studio",
            paths,
        )

    def test_studio_updates_complete_configuration(
        self,
    ):
        result = update_repliker_studio(
            db=self.db,
            repliker=self.repliker,
            payload=self.payload(),
        )

        self.db.commit()

        self.assertEqual(
            result["purpose"],
            "Construir servicios robustos.",
        )

        self.assertEqual(
            result["personality"],
            "Analítico y preciso.",
        )

        self.assertEqual(
            result["config_version"],
            1,
        )

        self.assertEqual(
            len(result["skills"]),
            2,
        )

        self.assertEqual(
            len(result["knowledge"]),
            1,
        )

        self.assertEqual(
            len(result["rules"]),
            1,
        )

        self.assertEqual(
            len(result["tools"]),
            2,
        )

    def test_second_save_increments_version(
        self,
    ):
        update_repliker_studio(
            db=self.db,
            repliker=self.repliker,
            payload=self.payload(),
        )

        self.db.commit()

        update_repliker_studio(
            db=self.db,
            repliker=self.repliker,
            payload=self.payload(),
        )

        self.db.commit()

        profile = self.db.scalar(
            select(
                ReplikerStudioProfile
            )
            .where(
                ReplikerStudioProfile.repliker_id
                == self.repliker.id
            )
        )

        self.assertEqual(
            profile.config_version,
            2,
        )

    def test_replacement_does_not_duplicate_rows(
        self,
    ):
        update_repliker_studio(
            db=self.db,
            repliker=self.repliker,
            payload=self.payload(),
        )

        self.db.commit()

        update_repliker_studio(
            db=self.db,
            repliker=self.repliker,
            payload=self.payload(),
        )

        self.db.commit()

        skill_count = int(
            self.db.scalar(
                select(
                    func.count(
                        ReplikerSkill.id
                    )
                )
                .where(
                    ReplikerSkill.repliker_id
                    == self.repliker.id
                )
            )
            or 0
        )

        knowledge_count = int(
            self.db.scalar(
                select(
                    func.count(
                        ReplikerKnowledgeItem.id
                    )
                )
            )
            or 0
        )

        rule_count = int(
            self.db.scalar(
                select(
                    func.count(
                        ReplikerRule.id
                    )
                )
            )
            or 0
        )

        tool_count = int(
            self.db.scalar(
                select(
                    func.count(
                        ReplikerToolAssignment.id
                    )
                )
            )
            or 0
        )

        self.assertEqual(
            skill_count,
            2,
        )

        self.assertEqual(
            knowledge_count,
            1,
        )

        self.assertEqual(
            rule_count,
            1,
        )

        self.assertEqual(
            tool_count,
            2,
        )

    def test_duplicate_skill_is_rejected(
        self,
    ):
        payload = self.payload()

        payload.skills = [
            StudioSkillUpdate(
                name="Python",
                level=90,
            ),
            StudioSkillUpdate(
                name="python",
                level=80,
            ),
        ]

        with self.assertRaises(
            ReplikerStudioError
        ):
            update_repliker_studio(
                db=self.db,
                repliker=self.repliker,
                payload=payload,
            )

    def test_empty_studio_has_safe_defaults(
        self,
    ):
        snapshot = studio_snapshot(
            db=self.db,
            repliker=self.repliker,
        )

        self.assertEqual(
            snapshot["config_version"],
            0,
        )

        self.assertEqual(
            snapshot["purpose"],
            "",
        )

        self.assertFalse(
            snapshot[
                "explicit_tool_configuration"
            ]
        )


if __name__ == "__main__":
    unittest.main()
