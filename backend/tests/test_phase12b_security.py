from __future__ import annotations

import unittest

from jwt import InvalidTokenError

from app.auth.password_policy import (
    PasswordPolicyError,
    validate_new_password,
)
from app.auth.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password_constant_time,
)
from app.core.config import settings


class Phase12BSecurityTests(
    unittest.TestCase
):
    def test_password_policy(
        self,
    ):
        with self.assertRaises(
            PasswordPolicyError
        ):
            validate_new_password(
                "12345678"
            )

        value = (
            "correct horse battery staple"
        )

        self.assertEqual(
            validate_new_password(
                value
            ),
            value,
        )

    def test_password_hashing(
        self,
    ):
        hashed = hash_password(
            "correct horse battery staple"
        )

        self.assertTrue(
            verify_password_constant_time(
                "correct horse battery staple",
                hashed,
            )
        )

        self.assertFalse(
            verify_password_constant_time(
                "incorrect-password",
                hashed,
            )
        )

        self.assertFalse(
            verify_password_constant_time(
                "anything-at-all",
                None,
            )
        )

    def test_jwt_required_claims(
        self,
    ):
        token = create_access_token(
            user_id=123,
            role="user",
        )

        payload = decode_access_token(
            token
        )

        self.assertEqual(
            payload["sub"],
            "123",
        )

        self.assertEqual(
            payload["iss"],
            settings.JWT_ISSUER,
        )

        self.assertEqual(
            payload["aud"],
            settings.JWT_AUDIENCE,
        )

        self.assertIn(
            "jti",
            payload,
        )

        self.assertIn(
            "iat",
            payload,
        )

        self.assertIn(
            "nbf",
            payload,
        )

        self.assertIn(
            "exp",
            payload,
        )

    def test_invalid_token_rejected(
        self,
    ):
        with self.assertRaises(
            InvalidTokenError
        ):
            decode_access_token(
                "not-a-valid-jwt"
            )

    def test_cors_has_no_wildcard(
        self,
    ):
        self.assertNotIn(
            "*",
            settings.cors_origins,
        )

    def test_simulated_economy_remains_locked(
        self,
    ):
        self.assertEqual(
            settings.ECONOMY_MODE,
            "simulation",
        )

        self.assertFalse(
            settings.REAL_PAYMENTS_ENABLED
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )


class Phase12BSecurityHeadersTests(
    unittest.TestCase
):
    def test_security_headers_present(
        self,
    ):
        from fastapi.testclient import (
            TestClient,
        )

        from app.main import app

        with TestClient(app) as client:
            response = client.get(
                "/api/v1/health"
            )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            response.headers.get(
                "x-content-type-options"
            ),
            "nosniff",
        )

        self.assertEqual(
            response.headers.get(
                "x-frame-options"
            ),
            "DENY",
        )

        self.assertEqual(
            response.headers.get(
                "referrer-policy"
            ),
            "no-referrer",
        )

        self.assertEqual(
            response.headers.get(
                "cache-control"
            ),
            "no-store",
        )

    def test_create_admin_uses_password_policy(
        self,
    ):
        from pathlib import Path

        backend_root = (
            Path(__file__)
            .resolve()
            .parents[1]
        )

        source = (
            backend_root
            / "app"
            / "scripts"
            / "create_admin.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "validate_new_password",
            source,
        )

        self.assertNotIn(
            "len(password) < 8",
            source,
        )
