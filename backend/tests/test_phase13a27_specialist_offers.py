from __future__ import annotations

import unittest
from datetime import (
    datetime,
    timezone,
)

import app.models  # noqa: F401

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.base import Base
from app.models.project import Project
from app.models.project_specialist import (
    ProjectSpecialistOffer,
    ProjectSpecialistRequirement,
)
from app.models.repliker import Repliker
from app.models.user import User
from app.services.specialist_coverage_service import (
    sync_project_specialist_coverage,
)


class Phase13A27SpecialistOfferTests(
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
            email="cliente@offers.test",
            password_hash="test",
            role="user",
            is_active=True,
        )

        self.owner = User(
            full_name="Ecosistema",
            email="owner@offers.test",
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
            description="Revision final.",
            status="available",
            reputation_score=100,
            base_price_credits=50,
            balance_credits=0,
            total_earnings_credits=0,
            jobs_completed=20,
            is_active=True,
        )

        self.db.add(
            self.vera
        )

        self.db.flush()

        self.project = Project(
            client_id=self.client.id,
            title="Proyecto",
            description="Prueba.",
            status="planned",
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
                reason="Revision final.",
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

    def add_offer(
        self,
        *,
        status: str,
        repliker: Repliker | None = None,
    ) -> ProjectSpecialistOffer:
        repliker = (
            repliker
            or self.vera
        )

        offer = ProjectSpecialistOffer(
            project_id=self.project.id,
            requirement_id=
                self.requirement.id,
            repliker_id=repliker.id,
            status=status,
            confidence_score=95,
            message="Respuesta.",
            reasoning="Evaluacion operativa.",
            responded_at=(
                datetime.now(
                    timezone.utc
                )
                if status
                in {
                    "accepted",
                    "rejected",
                }
                else None
            ),
        )

        self.db.add(
            offer
        )

        self.db.flush()

        return offer

    def test_available_reviewer_is_not_auto_assigned(
        self,
    ):
        snapshot = (
            sync_project_specialist_coverage(
                db=self.db,
                project_id=self.project.id,
            )
        )

        self.assertFalse(
            snapshot.ready
        )

        self.assertIsNone(
            self.requirement
            .assigned_repliker_id
        )

        self.assertEqual(
            self.requirement
            .coverage_status,
            "pending",
        )

    def test_pending_offer_does_not_cover(
        self,
    ):
        self.add_offer(
            status="pending"
        )

        snapshot = (
            sync_project_specialist_coverage(
                db=self.db,
                project_id=self.project.id,
            )
        )

        self.assertFalse(
            snapshot.ready
        )

    def test_rejected_offer_does_not_cover(
        self,
    ):
        self.add_offer(
            status="rejected"
        )

        snapshot = (
            sync_project_specialist_coverage(
                db=self.db,
                project_id=self.project.id,
            )
        )

        self.assertFalse(
            snapshot.ready
        )

    def test_accepted_offer_covers_final_reviewer(
        self,
    ):
        self.add_offer(
            status="accepted"
        )

        snapshot = (
            sync_project_specialist_coverage(
                db=self.db,
                project_id=self.project.id,
            )
        )

        self.assertTrue(
            snapshot.ready
        )

        self.assertEqual(
            self.requirement
            .assigned_repliker_id,
            self.vera.id,
        )

        self.assertEqual(
            self.requirement
            .coverage_status,
            "covered",
        )

    def test_accepted_reviewer_cannot_cover_two_projects(
        self,
    ):
        self.add_offer(
            status="accepted"
        )

        first = (
            sync_project_specialist_coverage(
                db=self.db,
                project_id=self.project.id,
            )
        )

        self.assertTrue(
            first.ready
        )

        second_project = Project(
            client_id=self.client.id,
            title="Proyecto dos",
            description="Prueba dos.",
            status="planned",
            currency="PEN",
            budget_limit_cents=10000,
        )

        self.db.add(
            second_project
        )

        self.db.flush()

        second_requirement = (
            ProjectSpecialistRequirement(
                project_id=
                    second_project.id,
                specialty=
                    "Final Reviewer",
                reason="Revision final.",
                is_mandatory=True,
                is_final_gate=True,
                coverage_status="pending",
            )
        )

        self.db.add(
            second_requirement
        )

        self.db.flush()

        second_offer = (
            ProjectSpecialistOffer(
                project_id=
                    second_project.id,
                requirement_id=
                    second_requirement.id,
                repliker_id=self.vera.id,
                status="accepted",
                confidence_score=95,
                message="Acepto.",
                reasoning="Disponible.",
                responded_at=datetime.now(
                    timezone.utc
                ),
            )
        )

        self.db.add(
            second_offer
        )

        self.db.flush()

        second = (
            sync_project_specialist_coverage(
                db=self.db,
                project_id=
                    second_project.id,
            )
        )

        self.assertFalse(
            second.ready
        )

        self.assertIsNone(
            second_requirement
            .assigned_repliker_id
        )


if __name__ == "__main__":
    unittest.main()
