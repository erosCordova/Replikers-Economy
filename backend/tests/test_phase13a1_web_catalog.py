import unittest

from app.replikers.catalogo_web import (
    WEB_REPLIKERS,
    get_web_repliker,
    validate_web_catalog,
)


class Phase13A1WebCatalogTests(unittest.TestCase):
    def test_catalog_is_valid(self):
        validate_web_catalog()

    def test_catalog_contains_fifteen_independent_specialists(self):
        self.assertEqual(
            len(WEB_REPLIKERS),
            15,
        )

    def test_codes_are_unique(self):
        codes = [
            repliker.code
            for repliker in WEB_REPLIKERS
        ]

        self.assertEqual(
            len(codes),
            len(set(codes)),
        )

    def test_product_requirements_exists(self):
        repliker = get_web_repliker(
            "product_requirements"
        )

        self.assertIsNotNone(repliker)

        self.assertEqual(
            repliker.specialty,
            "Product / Requirements",
        )

        skill_names = {
            item.name
            for item in repliker.skills
        }

        self.assertIn(
            "Specialist Selection",
            skill_names,
        )

    def test_final_reviewer_exists(self):
        repliker = get_web_repliker(
            "final_reviewer"
        )

        self.assertIsNotNone(repliker)

        self.assertEqual(
            repliker.specialty,
            "Final Reviewer",
        )

        skill_names = {
            item.name
            for item in repliker.skills
        }

        self.assertIn(
            "Final Project Review",
            skill_names,
        )

    def test_each_repliker_has_personality_and_zone(self):
        for repliker in WEB_REPLIKERS:
            with self.subTest(
                repliker=repliker.code
            ):
                self.assertTrue(
                    repliker.communication_style.strip()
                )
                self.assertTrue(
                    repliker.ecosystem_zone.strip()
                )
                self.assertGreaterEqual(
                    len(repliker.skills),
                    5,
                )

    def test_skill_levels_are_valid(self):
        for repliker in WEB_REPLIKERS:
            for repliker_skill in repliker.skills:
                with self.subTest(
                    repliker=repliker.code,
                    skill=repliker_skill.name,
                ):
                    self.assertGreaterEqual(
                        repliker_skill.level,
                        0,
                    )
                    self.assertLessEqual(
                        repliker_skill.level,
                        100,
                    )


if __name__ == "__main__":
    unittest.main()
