import unittest

from sqlalchemy import (
    create_engine,
    select,
)
from sqlalchemy.orm import (
    Session,
)

import app.models  # noqa: F401

from app.database.base import Base
from app.models.repliker import (
    Repliker,
)
from app.models.user import User
from app.replikers.catalogo_web import (
    WEB_REPLIKERS,
)
from app.services.web_repliker_registry_service import (
    ECOSYSTEM_OWNER_EMAIL,
    ECOSYSTEM_OWNER_ROLE,
    ensure_web_repliker_registry,
)


class Phase13A2WebRegistryTests(
    unittest.TestCase
):
    def setUp(self):
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:"
        )

        Base.metadata.create_all(
            self.engine
        )

        self.db = Session(
            self.engine
        )

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_registry_creates_internal_owner(
        self,
    ):
        result = (
            ensure_web_repliker_registry(
                self.db
            )
        )

        owner = self.db.scalar(
            select(User).where(
                User.email
                == ECOSYSTEM_OWNER_EMAIL
            )
        )

        self.assertIsNotNone(owner)

        self.assertEqual(
            owner.role,
            ECOSYSTEM_OWNER_ROLE,
        )

        self.assertFalse(
            owner.is_active
        )

        self.assertTrue(
            result.owner_created
        )

    def test_registry_creates_all_web_replikers(
        self,
    ):
        result = (
            ensure_web_repliker_registry(
                self.db
            )
        )

        owner = self.db.scalar(
            select(User).where(
                User.email
                == ECOSYSTEM_OWNER_EMAIL
            )
        )

        replikers = list(
            self.db.scalars(
                select(Repliker)
                .where(
                    Repliker.owner_id
                    == owner.id
                )
            ).all()
        )

        self.assertEqual(
            len(replikers),
            len(WEB_REPLIKERS),
        )

        self.assertEqual(
            result.total_replikers,
            15,
        )

    def test_registry_creates_skills(
        self,
    ):
        ensure_web_repliker_registry(
            self.db
        )

        iris = self.db.scalar(
            select(Repliker).where(
                Repliker.name == "Iris"
            )
        )

        self.assertIsNotNone(iris)

        skills = {
            item.name
            for item in iris.skills
        }

        self.assertIn(
            "Requirements Analysis",
            skills,
        )

        self.assertIn(
            "Specialist Selection",
            skills,
        )

    def test_registry_creates_final_reviewer(
        self,
    ):
        ensure_web_repliker_registry(
            self.db
        )

        vera = self.db.scalar(
            select(Repliker).where(
                Repliker.name == "Vera"
            )
        )

        self.assertIsNotNone(vera)

        self.assertEqual(
            vera.specialty,
            "Final Reviewer",
        )

        skill_names = {
            item.name
            for item in vera.skills
        }

        self.assertIn(
            "Delivery Readiness",
            skill_names,
        )

    def test_registry_is_idempotent(
        self,
    ):
        first = (
            ensure_web_repliker_registry(
                self.db
            )
        )

        second = (
            ensure_web_repliker_registry(
                self.db
            )
        )

        owner_count = len(
            list(
                self.db.scalars(
                    select(User).where(
                        User.email
                        == ECOSYSTEM_OWNER_EMAIL
                    )
                ).all()
            )
        )

        owner = self.db.scalar(
            select(User).where(
                User.email
                == ECOSYSTEM_OWNER_EMAIL
            )
        )

        repliker_count = len(
            list(
                self.db.scalars(
                    select(Repliker).where(
                        Repliker.owner_id
                        == owner.id
                    )
                ).all()
            )
        )

        self.assertEqual(
            owner_count,
            1,
        )

        self.assertEqual(
            repliker_count,
            15,
        )

        self.assertEqual(
            first.replikers_created,
            15,
        )

        self.assertEqual(
            second.replikers_created,
            0,
        )

        self.assertFalse(
            second.owner_created
        )


if __name__ == "__main__":
    unittest.main()
