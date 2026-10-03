from __future__ import annotations

import unittest

from unittest.mock import patch

import app.models  # noqa: F401

from sqlalchemy import (
    create_engine,
    select,
)
from sqlalchemy.orm import Session

from app.api.routes.market import (
    run_autonomous_market,
)
from app.agentic.repliker_runtime import (
    MARKET_AGENT_SYSTEM_PROMPT,
)
from app.database.base import Base
from app.models.market import (
    ReplikerTaskDecision,
)
from app.models.project import Project
from app.models.repliker import (
    Repliker,
    ReplikerSkill,
)
from app.models.task import (
    Task,
    TaskSkillRequirement,
)
from app.models.user import User
from app.schemas.market import (
    AgentDecisionAI,
)
from app.services.repliker_matching_service import (
    rank_task_candidates,
)


class Phase13A2DirectedMarketTests(
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

        self.client = User(
            full_name="Cliente",
            email="cliente@market.test",
            password_hash="test",
            role="user",
            is_active=True,
        )

        self.owner = User(
            full_name="Ecosistema",
            email="ecosistema@market.test",
            password_hash="test",
            role="system",
            is_active=False,
        )

        self.db.add_all(
            [
                self.client,
                self.owner,
            ]
        )

        self.db.flush()

        self.iris = self._repliker(
            name="Iris",
            specialty=
                "Product / Requirements",
            reputation=100,
            jobs=100,
            status="available",
            skill_name=
                "Specialist Selection",
            skill_level=100,
        )

        self.best_frontend = (
            self._repliker(
                name="Nova Principal",
                specialty=
                    "Frontend Developer",
                reputation=70,
                jobs=4,
                status="available",
                skill_name="React",
                skill_level=95,
            )
        )

        self.second_frontend = (
            self._repliker(
                name="Nova Alterna",
                specialty=
                    "Frontend Developer",
                reputation=99,
                jobs=30,
                status="available",
                skill_name="React",
                skill_level=70,
            )
        )

        self.backend = self._repliker(
            name="Bruno",
            specialty=
                "Backend Developer",
            reputation=100,
            jobs=100,
            status="available",
            skill_name="React",
            skill_level=100,
        )

        self.busy_frontend = (
            self._repliker(
                name="Nova Ocupada",
                specialty=
                    "Frontend Developer",
                reputation=100,
                jobs=100,
                status="working",
                skill_name="React",
                skill_level=100,
            )
        )

        self.vera = self._repliker(
            name="Vera",
            specialty=
                "Final Reviewer",
            reputation=100,
            jobs=100,
            status="available",
            skill_name="React",
            skill_level=100,
        )

        self.project = Project(
            client_id=self.client.id,
            title="Proyecto web",
            description=
                "Proyecto de prueba.",
            status="planned",
            currency="PEN",
            budget_limit_cents=10000,
            quoted_amount_cents=5000,
        )

        self.db.add(
            self.project
        )

        self.db.flush()

        self.task = Task(
            project_id=self.project.id,
            title="Construir interfaz",
            description=
                "Crear la interfaz.",
            required_specialty=
                "Frontend Developer",
            status="planned",
            complexity=60,
            max_budget_cents=5000,
        )

        self.db.add(
            self.task
        )

        self.db.flush()

        self.db.add(
            TaskSkillRequirement(
                task_id=self.task.id,
                skill_name="React",
                minimum_level=90,
            )
        )

        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _repliker(
        self,
        *,
        name: str,
        specialty: str,
        reputation: int,
        jobs: int,
        status: str,
        skill_name: str,
        skill_level: int,
    ) -> Repliker:
        repliker = Repliker(
            owner_id=self.owner.id,
            name=name,
            specialty=specialty,
            description="Prueba.",
            status=status,
            reputation_score=reputation,
            base_price_credits=50,
            balance_credits=0,
            total_earnings_credits=0,
            jobs_completed=jobs,
            is_active=True,
        )

        self.db.add(
            repliker
        )

        self.db.flush()

        self.db.add(
            ReplikerSkill(
                repliker_id=repliker.id,
                name=skill_name,
                level=skill_level,
            )
        )

        self.db.flush()

        return repliker

    def test_only_required_specialty_is_selected(
        self,
    ):
        candidates = rank_task_candidates(
            task=self.task,
            replikers=[
                self.iris,
                self.best_frontend,
                self.second_frontend,
                self.backend,
                self.busy_frontend,
                self.vera,
            ],
        )

        names = [
            item.repliker.name
            for item in candidates
        ]

        self.assertEqual(
            names,
            [
                "Nova Principal",
                "Nova Alterna",
            ],
        )

    def test_skill_coverage_precedes_reputation(
        self,
    ):
        candidates = rank_task_candidates(
            task=self.task,
            replikers=[
                self.second_frontend,
                self.best_frontend,
            ],
        )

        self.assertEqual(
            candidates[0]
            .repliker
            .name,
            "Nova Principal",
        )

        self.assertTrue(
            candidates[0]
            .meets_all_skills
        )

        self.assertFalse(
            candidates[1]
            .meets_all_skills
        )

    def test_busy_and_reserved_replikers_are_excluded(
        self,
    ):
        self.task.required_specialty = (
            "Generalist"
        )

        candidates = rank_task_candidates(
            task=self.task,
            replikers=[
                self.iris,
                self.busy_frontend,
                self.vera,
                self.backend,
            ],
        )

        names = {
            item.repliker.name
            for item in candidates
        }

        self.assertEqual(
            names,
            {
                "Bruno",
            },
        )

    def test_market_stops_after_first_bid(
        self,
    ):
        calls: list[str] = []

        def fake_evaluate(
            **kwargs,
        ):
            name = (
                kwargs[
                    "repliker_data"
                ]["name"]
            )

            calls.append(
                name
            )

            return AgentDecisionAI(
                decision="bid",
                amount_cents=4000,
                confidence_score=95,
                estimated_minutes=60,
                message=(
                    "Acepto la oportunidad."
                ),
                reasoning=(
                    "El perfil coincide."
                ),
            )

        with (
            patch(
                "app.api.routes.market."
                "resolve_repliker_tool_names",
                return_value=(),
            ),
            patch(
                "app.api.routes.market."
                "evaluate_repliker_for_task",
                side_effect=fake_evaluate,
            ),
        ):
            response = run_autonomous_market(
                project_id=
                    self.project.id,
                db=self.db,
                current_user=
                    self.client,
            )

        self.assertEqual(
            calls,
            [
                "Nova Principal",
            ],
        )

        self.assertEqual(
            response.agents_considered,
            1,
        )

        decisions = list(
            self.db.scalars(
                select(
                    ReplikerTaskDecision
                )
                .where(
                    ReplikerTaskDecision
                    .task_id
                    == self.task.id
                )
            ).all()
        )

        self.assertEqual(
            len(decisions),
            1,
        )

        self.assertEqual(
            decisions[0].decision,
            "bid",
        )

    def test_market_moves_to_next_after_rejection(
        self,
    ):
        calls: list[str] = []

        def fake_evaluate(
            **kwargs,
        ):
            name = (
                kwargs[
                    "repliker_data"
                ]["name"]
            )

            calls.append(
                name
            )

            if (
                name
                == "Nova Principal"
            ):
                return AgentDecisionAI(
                    decision="pass",
                    amount_cents=None,
                    confidence_score=65,
                    estimated_minutes=None,
                    message=(
                        "Prefiero no tomar "
                        "esta oportunidad."
                    ),
                    reasoning=(
                        "Decision autonoma."
                    ),
                )

            return AgentDecisionAI(
                decision="bid",
                amount_cents=3500,
                confidence_score=82,
                estimated_minutes=80,
                message=(
                    "Acepto presentar "
                    "una oferta."
                ),
                reasoning=(
                    "Puedo realizarla."
                ),
            )

        with (
            patch(
                "app.api.routes.market."
                "resolve_repliker_tool_names",
                return_value=(),
            ),
            patch(
                "app.api.routes.market."
                "evaluate_repliker_for_task",
                side_effect=fake_evaluate,
            ),
        ):
            response = run_autonomous_market(
                project_id=
                    self.project.id,
                db=self.db,
                current_user=
                    self.client,
            )

        self.assertEqual(
            calls,
            [
                "Nova Principal",
                "Nova Alterna",
            ],
        )

        self.assertEqual(
            response.agents_considered,
            2,
        )

        decisions = list(
            self.db.scalars(
                select(
                    ReplikerTaskDecision
                )
                .where(
                    ReplikerTaskDecision
                    .task_id
                    == self.task.id
                )
                .order_by(
                    ReplikerTaskDecision.id
                )
            ).all()
        )

        self.assertEqual(
            [
                item.decision
                for item in decisions
            ],
            [
                "pass",
                "bid",
            ],
        )

    def test_public_market_message_is_spanish(
        self,
    ):
        prompt = (
            MARKET_AGENT_SYSTEM_PROMPT
            .casefold()
        )

        self.assertIn(
            "español",
            prompt,
        )


if __name__ == "__main__":
    unittest.main()
