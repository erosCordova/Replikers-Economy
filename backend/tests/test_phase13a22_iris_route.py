import unittest
from unittest.mock import patch

import app.models  # noqa: F401

from sqlalchemy import (
    create_engine,
    select,
)
from sqlalchemy.orm import (
    Session,
    selectinload,
)

from app.api.routes.coordinator import (
    plan_project,
)
from app.database.base import Base
from app.models.ecosystem import (
    AgentMessage,
)
from app.models.project import (
    Project,
)
from app.models.repliker import (
    Repliker,
)
from app.models.task import (
    Task,
)
from app.models.user import (
    User,
)
from app.schemas.coordinator import (
    AIProjectPlan,
)
from app.services.web_repliker_registry_service import (
    ECOSYSTEM_OWNER_EMAIL,
)


class Phase13A22IrisRouteTests(
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
            self.engine
        )

        self.client = User(
            full_name="Cliente Test",
            email="cliente@test.invalid",
            password_hash="test",
            role="user",
            is_active=True,
        )

        owner = User(
            full_name="Replikers Ecosystem",
            email=ECOSYSTEM_OWNER_EMAIL,
            password_hash="test",
            role="system",
            is_active=False,
        )

        self.db.add_all(
            [
                self.client,
                owner,
            ]
        )

        self.db.flush()

        self.iris = Repliker(
            owner_id=owner.id,
            name="Iris",
            specialty=
                "Product / Requirements",
            description=
                "Product Repliker",
            status="available",
            reputation_score=50,
            base_price_credits=85,
            balance_credits=0,
            total_earnings_credits=0,
            jobs_completed=0,
            is_active=True,
        )

        self.frontend = Repliker(
            owner_id=owner.id,
            name="Nova",
            specialty=
                "Frontend Developer",
            description=
                "Frontend Repliker",
            status="available",
            reputation_score=50,
            base_price_credits=90,
            balance_credits=0,
            total_earnings_credits=0,
            jobs_completed=0,
            is_active=True,
        )

        self.db.add_all(
            [
                self.iris,
                self.frontend,
            ]
        )

        self.db.flush()

        self.project = Project(
            client_id=
                self.client.id,
            title=
                "Web veterinaria",
            description=(
                "Crear una web moderna "
                "para una veterinaria."
            ),
            status=
                "draft",
            currency=
                "PEN",
            budget_limit_cents=
                10000,
        )

        self.db.add(
            self.project
        )

        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _plan(self):
        return AIProjectPlan.model_validate(
            {
                "summary":
                    "Plan web.",
                "strategy":
                    "Construccion incremental.",
                "required_specialists": [
                    {
                        "specialty":
                            "Frontend Developer",
                        "reason":
                            "Construir interfaz.",
                        "mandatory":
                            True,
                        "final_gate":
                            False,
                    },
                    {
                        "specialty":
                            "Final Reviewer",
                        "reason":
                            "Revision final.",
                        "mandatory":
                            True,
                        "final_gate":
                            True,
                    },
                ],
                "market_gaps":
                    [],
                "tasks": [
                    {
                        "title":
                            "Crear frontend",
                        "description":
                            "Crear interfaz web.",
                        "required_specialty":
                            "Frontend Developer",
                        "complexity":
                            60,
                        "max_budget_cents":
                            5000,
                        "required_skills": [
                            {
                                "skill_name":
                                    "React",
                                "minimum_level":
                                    80,
                            }
                        ],
                        "acceptance_criteria": [
                            "Interfaz funcional."
                        ],
                    }
                ],
            }
        )

    def test_route_persists_specialty_and_iris(
        self,
    ):
        with patch(
            "app.api.routes.coordinator."
            "build_project_plan",
            return_value=self._plan(),
        ):
            response = plan_project(
                project_id=
                    self.project.id,
                db=
                    self.db,
                current_user=
                    self.client,
            )

        self.assertEqual(
            response.coordinator,
            "Iris",
        )

        self.assertEqual(
            len(
                response.required_specialists
            ),
            2,
        )

        task = self.db.scalar(
            select(Task)
            .options(
                selectinload(
                    Task.required_skills
                )
            )
            .where(
                Task.project_id
                == self.project.id
            )
        )

        self.assertIsNotNone(
            task
        )

        self.assertEqual(
            task.required_specialty,
            "Frontend Developer",
        )

        message = self.db.scalar(
            select(AgentMessage)
            .where(
                AgentMessage.project_id
                == self.project.id,
                AgentMessage.message_type
                == "planning_summary",
            )
        )

        self.assertIsNotNone(
            message
        )

        self.assertEqual(
            message.sender_repliker_id,
            self.iris.id,
        )

        self.assertEqual(
            message.sender_type,
            "repliker",
        )


if __name__ == "__main__":
    unittest.main()
