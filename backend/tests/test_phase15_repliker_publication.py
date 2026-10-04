from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

import app.models  # noqa: F401

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.routes.replikers import (
    router,
)
from app.database.base import Base
from app.models.repliker import (
    Repliker,
    ReplikerSkill,
)
from app.models.user import User
from app.services.repliker_matching_service import (
    rank_task_candidates,
)
from app.services.repliker_publication_service import (
    ReplikerPublicationError,
    set_repliker_publication,
)


class Phase15PublicationTests(
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
            email="phase15@test.local",
            password_hash="test",
            role="user",
            is_active=True,
        )

        self.db.add(
            self.owner
        )

        self.db.flush()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def make_repliker(
        self,
        *,
        name: str = "Atlas",
        description: str = (
            "Especialista listo "
            "para trabajar."
        ),
        published: bool = False,
        system: bool = False,
        with_skill: bool = True,
    ) -> Repliker:
        repliker = Repliker(
            owner_id=self.owner.id,
            name=name,
            specialty="Backend Developer",
            description=description,
            status="available",
            reputation_score=80,
            base_price_credits=50,
            balance_credits=0,
            total_earnings_credits=0,
            jobs_completed=0,
            is_active=True,
            is_system=system,
            is_published=published,
        )

        self.db.add(
            repliker
        )

        self.db.flush()

        if with_skill:
            self.db.add(
                ReplikerSkill(
                    repliker_id=
                        repliker.id,
                    name="Python",
                    level=90,
                )
            )

            self.db.flush()

            self.db.refresh(
                repliker
            )

        return repliker

    def test_publication_requires_description(
        self,
    ):
        repliker = self.make_repliker(
            description="",
        )

        with self.assertRaises(
            ReplikerPublicationError
        ):
            set_repliker_publication(
                repliker=repliker,
                published=True,
            )

    def test_publication_requires_skill(
        self,
    ):
        repliker = self.make_repliker(
            with_skill=False,
        )

        with self.assertRaises(
            ReplikerPublicationError
        ):
            set_repliker_publication(
                repliker=repliker,
                published=True,
            )

    def test_publish_and_unpublish(
        self,
    ):
        repliker = self.make_repliker()

        set_repliker_publication(
            repliker=repliker,
            published=True,
        )

        self.assertTrue(
            repliker.is_published
        )

        self.assertIsNotNone(
            repliker.published_at
        )

        set_repliker_publication(
            repliker=repliker,
            published=False,
        )

        self.assertFalse(
            repliker.is_published
        )

        self.assertIsNone(
            repliker.published_at
        )

    def test_system_repliker_is_protected(
        self,
    ):
        repliker = self.make_repliker(
            system=True,
            published=True,
        )

        with self.assertRaises(
            ReplikerPublicationError
        ):
            set_repliker_publication(
                repliker=repliker,
                published=False,
            )

    def test_matching_ignores_drafts(
        self,
    ):
        draft = self.make_repliker(
            name="Borrador",
            published=False,
        )

        published = self.make_repliker(
            name="Publicado",
            published=True,
        )

        task = SimpleNamespace(
            required_specialty=
                "Backend Developer",
            required_skills=[],
        )

        candidates = (
            rank_task_candidates(
                task=task,
                replikers=[
                    draft,
                    published,
                ],
            )
        )

        ids = [
            candidate.repliker.id
            for candidate
            in candidates
        ]

        self.assertNotIn(
            draft.id,
            ids,
        )

        self.assertIn(
            published.id,
            ids,
        )

    def test_publication_route_exists(
        self,
    ):
        paths = {
            route.path
            for route
            in router.routes
        }

        self.assertIn(
            (
                "/replikers/"
                "{repliker_id}/publication"
            ),
            paths,
        )

    def test_user_creation_is_draft(
        self,
    ):
        source = Path(
            "app/api/routes/replikers.py"
        ).read_text(
            encoding="utf-8",
        )

        self.assertIn(
            "is_published=False",
            source,
        )

        self.assertIn(
            "is_system=False",
            source,
        )

    def test_market_wiring_uses_publication(
        self,
    ):
        files = [
            "app/api/routes/market.py",
            "app/api/routes/coordinator.py",
            (
                "app/services/"
                "specialist_recruitment_service.py"
            ),
            (
                "app/services/"
                "ecosystem_service.py"
            ),
        ]

        for filename in files:
            with self.subTest(
                filename=filename
            ):
                source = Path(
                    filename
                ).read_text(
                    encoding="utf-8",
                )

                self.assertIn(
                    "Repliker.is_published",
                    source,
                )

    def test_existing_coverage_keeps_commitments(
        self,
    ):
        source = Path(
            "app/services/"
            "specialist_coverage_service.py"
        ).read_text(
            encoding="utf-8",
        )

        self.assertNotIn(
            "Repliker.is_published",
            source,
        )


    def test_secondary_new_work_paths_require_publication(
        self,
    ):
        files = [
            "app/api/routes/tasks.py",
            (
                "app/services/"
                "delegation_service.py"
            ),
            (
                "app/services/"
                "contract_service.py"
            ),
        ]

        for filename in files:
            with self.subTest(
                filename=filename
            ):
                source = Path(
                    filename
                ).read_text(
                    encoding="utf-8",
                )

                self.assertIn(
                    "is_published",
                    source,
                )

    def test_public_detail_hides_drafts(
        self,
    ):
        source = Path(
            "app/api/routes/replikers.py"
        ).read_text(
            encoding="utf-8",
        )

        self.assertIn(
            "if not repliker.is_published:",
            source,
        )


    def test_registry_marks_official_replikers(
        self,
    ):
        source = Path(
            "app/services/"
            "web_repliker_registry_service.py"
        ).read_text(
            encoding="utf-8",
        )

        self.assertIn(
            "is_system=True",
            source,
        )

        self.assertIn(
            "is_published=True",
            source,
        )


if __name__ == "__main__":
    unittest.main()
