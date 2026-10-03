from __future__ import annotations

import unittest
from pathlib import Path

import app.models  # noqa: F401

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError

from app.database.base import Base
from app.models.project_specialist import (
    ProjectSpecialistOffer,
)
from app.services.repliker_matching_service import (
    RESERVED_TASK_SPECIALTIES,
)


class Phase13SafetyHardeningTests(
    unittest.TestCase
):
    def test_final_reviewer_is_reserved_from_tasks(
        self,
    ):
        self.assertIn(
            "final reviewer",
            RESERVED_TASK_SPECIALTIES,
        )

    def test_only_one_accepted_offer_per_requirement(
        self,
    ):
        engine = create_engine(
            "sqlite:///:memory:"
        )

        Base.metadata.create_all(
            engine
        )

        table = (
            ProjectSpecialistOffer
            .__table__
        )

        with engine.begin() as connection:
            connection.execute(
                table.insert().values(
                    project_id=1,
                    requirement_id=1,
                    repliker_id=10,
                    status="accepted",
                    confidence_score=100,
                    message="Acepto.",
                    reasoning="Disponible.",
                )
            )

            with self.assertRaises(
                IntegrityError
            ):
                connection.execute(
                    table.insert().values(
                        project_id=1,
                        requirement_id=1,
                        repliker_id=11,
                        status="accepted",
                        confidence_score=100,
                        message="Acepto.",
                        reasoning="Disponible.",
                    )
                )

        engine.dispose()

    def test_workflow_titles_do_not_expose_internal_stage(
        self,
    ):
        source = Path(
            "app/agentic/project_graph.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertNotIn(
            'f"Etapa {stage}',
            source,
        )

        self.assertNotIn(
            '"Retry de ejecucion "',
            source,
        )

        self.assertIn(
            "visible_stage_label",
            source,
        )


if __name__ == "__main__":
    unittest.main()
