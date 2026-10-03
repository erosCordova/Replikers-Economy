from __future__ import annotations

import unittest

import app.models  # noqa: F401

from sqlalchemy import (
    create_engine,
    select,
)
from sqlalchemy.orm import Session

from app.database.base import Base
from app.models.project import Project
from app.models.project_specialist import (
    ProjectSpecialistOffer,
    ProjectSpecialistRequirement,
)
from app.models.repliker import Repliker
from app.models.user import User
from app.schemas.market import (
    SpecialistOfferDecisionAI,
)
from app.services.specialist_recruitment_service import (
    run_project_specialist_recruitment,
)


class Phase13A28RecruitmentTests(
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
            email="cliente@recruit.test",
            password_hash="test",
            role="user",
            is_active=True,
        )

        self.owner = User(
            full_name="Ecosistema",
            email="owner@recruit.test",
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

        self.vera = Repliker(
            owner_id=self.owner.id,
            name="Vera",
            specialty="Final Reviewer",
            description="Revisión final.",
            status="available",
            reputation_score=99,
            base_price_credits=50,
            balance_credits=0,
            total_earnings_credits=0,
            jobs_completed=20,
            is_active=True,
        )

        self.vera_two = Repliker(
            owner_id=self.owner.id,
            name="Vera Dos",
            specialty="Final Reviewer",
            description="Revisión final.",
            status="available",
            reputation_score=90,
            base_price_credits=50,
            balance_credits=0,
            total_earnings_credits=0,
            jobs_completed=10,
            is_active=True,
        )

        self.db.add_all(
            [
                self.vera,
                self.vera_two,
            ]
        )

        self.db.flush()

        self.project = Project(
            client_id=self.client.id,
            title="Proyecto",
            description="Proyecto de prueba.",
            status="market_open",
            currency="PEN",
            budget_limit_cents=10000,
        )

        self.db.add(
            self.project
        )

        self.db.flush()

        self.requirement = (
            ProjectSpecialistRequirement(
                project_id=self.project.id,
                specialty="Final Reviewer",
                reason=(
                    "Validar la entrega final."
                ),
                is_mandatory=True,
                is_final_gate=True,
                coverage_status="pending",
            )
        )

        self.db.add(
            self.requirement
        )

        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_acceptance_covers_role(
        self,
    ):
        def evaluator(**kwargs):
            _ = kwargs

            return (
                SpecialistOfferDecisionAI(
                    decision="accept",
                    confidence_score=98,
                    message=(
                        "Acepto revisar "
                        "la entrega final."
                    ),
                    reasoning=(
                        "El puesto coincide "
                        "con mi perfil."
                    ),
                )
            )

        result = (
            run_project_specialist_recruitment(
                db=self.db,
                project_id=self.project.id,
                evaluator=evaluator,
            )
        )

        self.assertEqual(
            result.accepted,
            1,
        )

        self.db.refresh(
            self.requirement
        )

        self.assertEqual(
            self.requirement
            .coverage_status,
            "covered",
        )

        self.assertEqual(
            self.requirement
            .assigned_repliker_id,
            self.vera.id,
        )

        offer = self.db.scalar(
            select(
                ProjectSpecialistOffer
            )
            .where(
                ProjectSpecialistOffer
                .requirement_id
                == self.requirement.id
            )
        )

        self.assertIsNotNone(
            offer
        )

        self.assertEqual(
            offer.status,
            "accepted",
        )

    def test_rejection_moves_to_next_candidate(
        self,
    ):
        names: list[str] = []

        def evaluator(
            *,
            repliker_data,
            **kwargs,
        ):
            _ = kwargs

            names.append(
                repliker_data["nombre"]
            )

            if (
                repliker_data["nombre"]
                == "Vera"
            ):
                return (
                    SpecialistOfferDecisionAI(
                        decision="reject",
                        confidence_score=90,
                        message=(
                            "Prefiero no asumir "
                            "esta revisión."
                        ),
                        reasoning=(
                            "Decisión autónoma."
                        ),
                    )
                )

            return (
                SpecialistOfferDecisionAI(
                    decision="accept",
                    confidence_score=95,
                    message=(
                        "Acepto realizar "
                        "la revisión final."
                    ),
                    reasoning=(
                        "El puesto coincide."
                    ),
                )
            )

        result = (
            run_project_specialist_recruitment(
                db=self.db,
                project_id=self.project.id,
                evaluator=evaluator,
            )
        )

        self.assertEqual(
            names,
            [
                "Vera",
                "Vera Dos",
            ],
        )

        self.assertEqual(
            result.rejected,
            1,
        )

        self.assertEqual(
            result.accepted,
            1,
        )

        offers = list(
            self.db.scalars(
                select(
                    ProjectSpecialistOffer
                )
                .where(
                    ProjectSpecialistOffer
                    .requirement_id
                    == self.requirement.id
                )
                .order_by(
                    ProjectSpecialistOffer
                    .id
                )
            ).all()
        )

        self.assertEqual(
            [
                item.status
                for item in offers
            ],
            [
                "rejected",
                "accepted",
            ],
        )

        self.db.refresh(
            self.requirement
        )

        self.assertEqual(
            self.requirement
            .assigned_repliker_id,
            self.vera_two.id,
        )

    def test_rejected_candidate_is_not_offered_again(
        self,
    ):
        calls = 0

        def reject_all(**kwargs):
            nonlocal calls
            _ = kwargs

            calls += 1

            return (
                SpecialistOfferDecisionAI(
                    decision="reject",
                    confidence_score=70,
                    message=(
                        "No aceptaré "
                        "la propuesta."
                    ),
                    reasoning="No disponible.",
                )
            )

        first = (
            run_project_specialist_recruitment(
                db=self.db,
                project_id=self.project.id,
                evaluator=reject_all,
            )
        )

        self.assertEqual(
            first.rejected,
            2,
        )

        first_calls = calls

        second = (
            run_project_specialist_recruitment(
                db=self.db,
                project_id=self.project.id,
                evaluator=reject_all,
            )
        )

        self.assertEqual(
            calls,
            first_calls,
        )

        self.assertEqual(
            second.offers_sent,
            0,
        )

    def test_no_transaction_is_open_during_ai(
        self,
    ):
        transaction_states = []

        def evaluator(**kwargs):
            _ = kwargs

            transaction_states.append(
                self.db.in_transaction()
            )

            return (
                SpecialistOfferDecisionAI(
                    decision="accept",
                    confidence_score=100,
                    message="Acepto.",
                    reasoning="Disponible.",
                )
            )

        run_project_specialist_recruitment(
            db=self.db,
            project_id=self.project.id,
            evaluator=evaluator,
        )

        self.assertEqual(
            transaction_states,
            [False],
        )

    def test_visible_role_context_is_spanish(
        self,
    ):
        captured = {}

        def evaluator(
            *,
            repliker_data,
            requirement_data,
            **kwargs,
        ):
            _ = kwargs

            captured.update(
                {
                    "repliker":
                        repliker_data[
                            "especialidad"
                        ],
                    "puesto":
                        requirement_data[
                            "especialidad"
                        ],
                }
            )

            return (
                SpecialistOfferDecisionAI(
                    decision="accept",
                    confidence_score=100,
                    message=(
                        "Acepto realizar "
                        "la revisión final."
                    ),
                    reasoning="Compatible.",
                )
            )

        run_project_specialist_recruitment(
            db=self.db,
            project_id=self.project.id,
            evaluator=evaluator,
        )

        self.assertEqual(
            captured["repliker"],
            "Revisor Final",
        )

        self.assertEqual(
            captured["puesto"],
            "Revisor Final",
        )

    def test_configuration_error_is_reported_without_crashing(
        self,
    ):
        from app.services.gemini_client import (
            GeminiConfigurationError,
        )

        calls = 0

        def unavailable(**kwargs):
            nonlocal calls
            _ = kwargs

            calls += 1

            raise GeminiConfigurationError(
                "Configuración no disponible."
            )

        result = (
            run_project_specialist_recruitment(
                db=self.db,
                project_id=self.project.id,
                evaluator=unavailable,
            )
        )

        self.assertEqual(
            calls,
            1,
        )

        self.assertEqual(
            result.accepted,
            0,
        )

        self.assertEqual(
            result.offers_sent,
            1,
        )

        self.assertTrue(
            result.errors,
        )



if __name__ == "__main__":
    unittest.main()
