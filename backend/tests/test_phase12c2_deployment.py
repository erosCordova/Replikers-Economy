from __future__ import annotations

import json
from pathlib import Path
import unittest

import yaml


class Phase12CDeploymentTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(
        cls,
    ):
        cls.backend_root = (
            Path(__file__)
            .resolve()
            .parents[1]
        )

        cls.repo_root = (
            cls.backend_root
            .parent
        )

        cls.frontend_root = (
            cls.repo_root
            / "frontend"
        )

    def load_render_blueprint(
        self,
    ) -> dict:
        path = (
            self.repo_root
            / "render.yaml"
        )

        self.assertTrue(
            path.exists(),
            "render.yaml debe existir.",
        )

        return yaml.safe_load(
            path.read_text(
                encoding="utf-8"
            )
        )

    def render_service(
        self,
    ) -> dict:
        blueprint = (
            self.load_render_blueprint()
        )

        services = (
            blueprint.get(
                "services",
                [],
            )
        )

        self.assertEqual(
            len(services),
            1,
        )

        return services[0]

    def test_render_service_contract(
        self,
    ):
        service = self.render_service()

        self.assertEqual(
            service.get("type"),
            "web",
        )

        self.assertEqual(
            service.get("runtime"),
            "python",
        )

        self.assertEqual(
            service.get("rootDir"),
            "backend",
        )

        self.assertEqual(
            service.get(
                "healthCheckPath"
            ),
            "/api/v1/health/ready",
        )

    def test_render_build_installs_requirements(
        self,
    ):
        service = self.render_service()

        build_command = str(
            service.get(
                "buildCommand",
                "",
            )
        )

        self.assertIn(
            "pip install",
            build_command,
        )

        self.assertIn(
            "requirements.txt",
            build_command,
        )

    def test_render_start_runs_migrations_and_checks(
        self,
    ):
        service = self.render_service()

        start_command = str(
            service.get(
                "startCommand",
                "",
            )
        )

        self.assertIn(
            "alembic upgrade head",
            start_command,
        )

        self.assertIn(
            "app.scripts.production_check",
            start_command,
        )

        self.assertIn(
            "uvicorn app.main:app",
            start_command,
        )

        self.assertIn(
            "--port $PORT",
            start_command,
        )

    def test_render_production_environment(
        self,
    ):
        service = self.render_service()

        env_vars = {
            item["key"]: item
            for item
            in service.get(
                "envVars",
                [],
            )
            if "key" in item
        }

        self.assertEqual(
            env_vars[
                "ENVIRONMENT"
            ].get("value"),
            "production",
        )

        self.assertEqual(
            env_vars[
                "ECONOMY_MODE"
            ].get("value"),
            "simulation",
        )

        self.assertEqual(
            env_vars[
                "REAL_PAYMENTS_ENABLED"
            ].get("value"),
            "false",
        )

        self.assertEqual(
            env_vars[
                "REFRESH_COOKIE_SAMESITE"
            ].get("value"),
            "none",
        )

        self.assertEqual(
            env_vars[
                "REFRESH_COOKIE_SECURE"
            ].get("value"),
            "true",
        )

    def test_render_secrets_are_not_committed(
        self,
    ):
        service = self.render_service()

        env_vars = {
            item["key"]: item
            for item
            in service.get(
                "envVars",
                [],
            )
            if "key" in item
        }

        protected = [
            "DATABASE_URL",
            "SECRET_KEY",
            "FRONTEND_URL",
            "GEMINI_API_KEY",
        ]

        for key in protected:
            self.assertIn(
                key,
                env_vars,
            )

            self.assertIs(
                env_vars[
                    key
                ].get("sync"),
                False,
            )

            self.assertNotIn(
                "value",
                env_vars[key],
            )

    def test_python_version_is_pinned(
        self,
    ):
        version_file = (
            self.backend_root
            / ".python-version"
        )

        self.assertTrue(
            version_file.exists()
        )

        self.assertEqual(
            version_file
            .read_text(
                encoding="utf-8"
            )
            .strip(),
            "3.13.15",
        )

    def test_vercel_contract(
        self,
    ):
        path = (
            self.frontend_root
            / "vercel.json"
        )

        self.assertTrue(
            path.exists()
        )

        config = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(
            config.get("framework"),
            "vite",
        )

        self.assertEqual(
            config.get(
                "outputDirectory"
            ),
            "dist",
        )

        build_command = str(
            config.get(
                "buildCommand",
                "",
            )
        )

        self.assertIn(
            "npm run production:check",
            build_command,
        )

        self.assertIn(
            "npm run build",
            build_command,
        )

        rewrites = config.get(
            "rewrites",
            [],
        )

        self.assertTrue(
            any(
                item.get("source")
                == "/(.*)"
                and item.get(
                    "destination"
                )
                == "/index.html"
                for item in rewrites
            )
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
