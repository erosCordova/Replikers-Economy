from __future__ import annotations

import unittest

import app.models  # noqa: F401

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.base import Base
from app.models.ecosystem import (
    AgentMessage,
)
from app.models.project import Project
from app.models.project_specialist import (
    ProjectFinalReview,
)
from app.services.project_version_service import (
    build_delivery_version_history,
)


class Phase22VersionHistoryTests(
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

        self.project = Project(
            client_id=1,
            title="Proyecto versionado",
            description=(
                "Prueba del historial."
            ),
            status="completed",
            currency="PEN",
            payment_status="settled",
        )

        self.db.add(
            self.project
        )

        self.db.flush()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def add_review(
        self,
        *,
        attempt: int,
        status: str,
        score: int | None,
    ):
        review = ProjectFinalReview(
            project_id=
                self.project.id,

            requirement_id=100,

            reviewer_repliker_id=200,

            attempt_number=
                attempt,

            status=status,

            score=score,

            summary=(
                f"Revisión técnica "
                f"{attempt}."
            ),

            corrections_json="[]",

            reasoning="Prueba.",
        )

        self.db.add(
            review
        )

        self.db.flush()

        return review

    def add_decision(
        self,
        *,
        attempt: int,
        decision: str,
        comment: str,
    ):
        if decision == "accepted":
            content = (
                "DECISIÓN DE ENTREGA — "
                f"Versión v{attempt} — "
                "Aceptada. "
                f"Comentario: {comment}"
            )

        else:
            content = (
                "DECISIÓN DE ENTREGA — "
                f"Versión v{attempt} — "
                "Correcciones solicitadas. "
                f"Solicitud: {comment}"
            )

        message = AgentMessage(
            project_id=
                self.project.id,

            sender_type=
                "project",

            receiver_type=
                "r00",

            message_type=
                "client_response",

            content=
                content,
        )

        self.db.add(
            message
        )

        self.db.flush()

    def test_only_approved_reviews_create_versions(
        self,
    ):
        self.add_review(
            attempt=1,
            status="approved",
            score=91,
        )

        self.add_review(
            attempt=2,
            status="corrections_requested",
            score=70,
        )

        self.add_review(
            attempt=4,
            status="approved",
            score=97,
        )

        self.add_decision(
            attempt=1,
            decision="corrections_requested",
            comment=(
                "Ajustar el panel."
            ),
        )

        self.db.commit()

        result = (
            build_delivery_version_history(
                db=self.db,
                project_id=
                    self.project.id,
            )
        )

        self.assertEqual(
            result["versions_total"],
            2,
        )

        self.assertEqual(
            result["current_version"],
            "v1.1",
        )

        self.assertEqual(
            result["items"][0][
                "version"
            ],
            "v1.0",
        )

        self.assertEqual(
            result["items"][1][
                "version"
            ],
            "v1.1",
        )

        self.assertEqual(
            result["items"][0][
                "review_attempt"
            ],
            1,
        )

        self.assertEqual(
            result["items"][1][
                "review_attempt"
            ],
            4,
        )

        self.assertEqual(
            result["items"][0][
                "client_decision"
            ],
            "corrections_requested",
        )

        self.assertTrue(
            result["items"][1][
                "is_current"
            ]
        )

    def test_internal_failed_reviews_do_not_skip_versions(
        self,
    ):
        self.add_review(
            attempt=1,
            status="failed",
            score=None,
        )

        self.add_review(
            attempt=3,
            status="approved",
            score=95,
        )

        self.db.commit()

        result = (
            build_delivery_version_history(
                db=self.db,
                project_id=
                    self.project.id,
            )
        )

        self.assertEqual(
            result["versions_total"],
            1,
        )

        self.assertEqual(
            result["items"][0][
                "version"
            ],
            "v1.0",
        )

        self.assertEqual(
            result["items"][0][
                "review_attempt"
            ],
            3,
        )


if __name__ == "__main__":
    unittest.main()
