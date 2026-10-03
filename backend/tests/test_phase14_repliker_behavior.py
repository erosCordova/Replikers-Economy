from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import app.models  # noqa: F401

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.agentic.execution_runtime import (
    execution_system_prompt,
)
from app.agentic.repliker_runtime import (
    build_market_agent,
    run_specialist_offer_agent,
)
from app.database.base import Base
from app.models.repliker import Repliker
from app.models.repliker_studio import (
    ReplikerKnowledgeItem,
    ReplikerRule,
    ReplikerStudioProfile,
)
from app.models.user import User
from app.schemas.market import (
    SpecialistOfferDecisionAI,
)
from app.services.repliker_behavior_service import (
    behavior_prompt_section,
    load_repliker_behavior_context,
)


class FakeSpecialistAgent:
    def invoke(
        self,
        payload,
    ):
        _ = payload

        return {
            "structured_response":
                SpecialistOfferDecisionAI(
                    decision="accept",
                    confidence_score=95,
                    message="Acepto.",
                    reasoning=(
                        "El puesto coincide "
                        "con mi perfil."
                    ),
                )
        }


class Phase14ReplikerBehaviorTests(
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
            email="behavior@test.local",
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

        self.db.flush()

        self.db.add(
            ReplikerStudioProfile(
                repliker_id=
                    self.repliker.id,
                purpose=(
                    "Crear servicios robustos."
                ),
                personality=(
                    "Analitico y cuidadoso."
                ),
                communication_style=(
                    "Claro y directo."
                ),
                instructions=(
                    "Comprueba el trabajo "
                    "antes de entregarlo."
                ),
                config_version=3,
            )
        )

        self.db.add_all(
            [
                ReplikerKnowledgeItem(
                    repliker_id=
                        self.repliker.id,
                    title="Convenciones",
                    content=(
                        "Usar validacion estricta."
                    ),
                    enabled=True,
                ),
                ReplikerKnowledgeItem(
                    repliker_id=
                        self.repliker.id,
                    title="Desactivado",
                    content=(
                        "No debe llegar al agente."
                    ),
                    enabled=False,
                ),
            ]
        )

        self.db.add_all(
            [
                ReplikerRule(
                    repliker_id=
                        self.repliker.id,
                    title="Pruebas",
                    instruction=(
                        "Verificar antes "
                        "de finalizar."
                    ),
                    priority=100,
                    enabled=True,
                ),
                ReplikerRule(
                    repliker_id=
                        self.repliker.id,
                    title="Desactivada",
                    instruction=(
                        "No debe aplicarse."
                    ),
                    priority=90,
                    enabled=False,
                ),
            ]
        )

        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def behavior(self):
        return (
            load_repliker_behavior_context(
                db=self.db,
                repliker_id=
                    self.repliker.id,
            )
        )

    def test_only_enabled_knowledge_and_rules_are_loaded(
        self,
    ):
        behavior = self.behavior()

        self.assertEqual(
            behavior["config_version"],
            3,
        )

        self.assertEqual(
            len(
                behavior["knowledge"]
            ),
            1,
        )

        self.assertEqual(
            len(
                behavior["rules"]
            ),
            1,
        )

        self.assertEqual(
            behavior[
                "knowledge"
            ][0]["title"],
            "Convenciones",
        )

        self.assertEqual(
            behavior[
                "rules"
            ][0]["title"],
            "Pruebas",
        )

    def test_owner_configuration_cannot_override_system(
        self,
    ):
        section = (
            behavior_prompt_section(
                self.behavior()
            )
        )

        self.assertIn(
            "PROPOSITO",
            section,
        )

        self.assertIn(
            "CONOCIMIENTO DISPONIBLE",
            section,
        )

        self.assertIn(
            "REGLAS PERSONALES",
            section,
        )

        self.assertIn(
            "subordinada",
            section,
        )

        self.assertIn(
            "seguridad",
            section,
        )

    def test_market_agent_receives_studio_behavior(
        self,
    ):
        repliker_data = {
            "id":
                self.repliker.id,
            "name":
                self.repliker.name,
            "skills":
                [],
            "studio_behavior":
                self.behavior(),
        }

        with (
            patch(
                "app.agentic.repliker_runtime."
                "get_chat_model",
                return_value=object(),
            ),
            patch(
                "app.agentic.repliker_runtime."
                "create_agent",
                return_value=object(),
            ) as create_agent,
        ):
            build_market_agent(
                repliker_data=
                    repliker_data,
                task_data={},
                project_data={},
                allowed_tool_names=(),
            )

        prompt = (
            create_agent
            .call_args
            .kwargs[
                "system_prompt"
            ]
        )

        self.assertIn(
            "Crear servicios robustos.",
            prompt,
        )

        self.assertIn(
            "Verificar antes de finalizar.",
            prompt,
        )

    def test_specialist_offer_receives_studio_behavior(
        self,
    ):
        repliker_data = {
            "id":
                self.repliker.id,
            "studio_behavior":
                self.behavior(),
        }

        with (
            patch(
                "app.agentic.repliker_runtime."
                "get_chat_model",
                return_value=object(),
            ),
            patch(
                "app.agentic.repliker_runtime."
                "create_agent",
                return_value=
                    FakeSpecialistAgent(),
            ) as create_agent,
        ):
            result = (
                run_specialist_offer_agent(
                    repliker_data=
                        repliker_data,
                    requirement_data={
                        "especialidad":
                            "Revisor Final",
                    },
                    project_data={
                        "id": 1,
                    },
                )
            )

        self.assertEqual(
            result.decision,
            "accept",
        )

        prompt = (
            create_agent
            .call_args
            .kwargs[
                "system_prompt"
            ]
        )

        self.assertIn(
            "Analitico y cuidadoso.",
            prompt,
        )

    def test_execution_prompt_receives_studio_behavior(
        self,
    ):
        prompt = execution_system_prompt(
            contract=
                SimpleNamespace(
                    id=10,
                    project_id=20,
                ),
            repliker=
                SimpleNamespace(
                    id=self.repliker.id,
                    name=self.repliker.name,
                    specialty=
                        self.repliker.specialty,
                ),
            task=
                SimpleNamespace(
                    id=30,
                    title="Crear servicio",
                    description=(
                        "Construir una API."
                    ),
                ),
            behavior_context=
                self.behavior(),
        )

        self.assertIn(
            "Claro y directo.",
            prompt,
        )

        self.assertIn(
            "Usar validacion estricta.",
            prompt,
        )

    def test_runtime_wiring_is_present(
        self,
    ):
        from pathlib import Path

        files = [
            "app/api/routes/market.py",
            (
                "app/services/"
                "specialist_recruitment_service.py"
            ),
            (
                "app/services/"
                "execution_agent_service.py"
            ),
        ]

        for filename in files:
            source = Path(
                filename
            ).read_text(
                encoding="utf-8"
            )

            self.assertIn(
                "load_repliker_behavior_context",
                source,
            )


if __name__ == "__main__":
    unittest.main()
