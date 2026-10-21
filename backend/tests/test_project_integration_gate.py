import unittest

from app.services.project_integration_service import (
    DELIVERY_PREFIX,
    INTEGRATION_MARKER_PATH,
    ProjectIntegrationError,
    validate_delivery_paths,
)


class ProjectIntegrationGateTests(
    unittest.TestCase
):
    def test_valid_integrated_delivery(
        self,
    ):
        paths = [
            (
                DELIVERY_PREFIX
                + "README.md"
            ),
            (
                DELIVERY_PREFIX
                + "backend/main.py"
            ),
            (
                DELIVERY_PREFIX
                + "frontend/index.html"
            ),
            INTEGRATION_MARKER_PATH,
        ]

        result = (
            validate_delivery_paths(
                paths
            )
        )

        self.assertEqual(
            len(result),
            4,
        )

    def test_missing_readme_is_rejected(
        self,
    ):
        with self.assertRaises(
            ProjectIntegrationError
        ):
            validate_delivery_paths(
                [
                    (
                        DELIVERY_PREFIX
                        + "backend/main.py"
                    ),
                    (
                        DELIVERY_PREFIX
                        + "frontend/index.html"
                    ),
                    INTEGRATION_MARKER_PATH,
                ]
            )

    def test_task_folders_are_rejected(
        self,
    ):
        with self.assertRaises(
            ProjectIntegrationError
        ):
            validate_delivery_paths(
                [
                    (
                        DELIVERY_PREFIX
                        + "README.md"
                    ),
                    (
                        DELIVERY_PREFIX
                        + "tarea-10/main.py"
                    ),
                    INTEGRATION_MARKER_PATH,
                ]
            )


if __name__ == "__main__":
    unittest.main()
