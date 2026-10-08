import unittest

from app.agentic.provider_retry import (
    invoke_with_transient_retry,
    is_quota_exhausted_error,
    is_transient_provider_error,
)


class ProviderRetryTests(
    unittest.TestCase
):
    def test_503_is_transient(
        self,
    ):
        self.assertTrue(
            is_transient_provider_error(
                RuntimeError(
                    "503 UNAVAILABLE "
                    "high demand"
                )
            )
        )

    def test_429_is_provider_interruption(
        self,
    ):
        self.assertTrue(
            is_transient_provider_error(
                RuntimeError(
                    "429 Too Many Requests"
                )
            )
        )

    def test_daily_quota_detected(
        self,
    ):
        error = RuntimeError(
            "429 RESOURCE_EXHAUSTED. "
            "You exceeded your current quota. "
            "generate_content_free_tier_requests"
        )

        self.assertTrue(
            is_quota_exhausted_error(
                error
            )
        )

    def test_daily_quota_is_not_retried(
        self,
    ):
        attempts = []

        def operation():
            attempts.append(1)

            raise RuntimeError(
                "429 RESOURCE_EXHAUSTED. "
                "You exceeded your current quota. "
                "free_tier_requests"
            )

        with self.assertRaises(
            RuntimeError
        ):
            invoke_with_transient_retry(
                operation,
                max_attempts=3,
                base_delay_seconds=0,
                sleep_fn=lambda _: None,
            )

        self.assertEqual(
            len(attempts),
            1,
        )

    def test_docker_error_is_not_provider_error(
        self,
    ):
        self.assertFalse(
            is_transient_provider_error(
                RuntimeError(
                    "Docker CLI no esta disponible."
                )
            )
        )

    def test_retries_short_transient_error(
        self,
    ):
        attempts = []

        def operation():
            attempts.append(
                len(attempts) + 1
            )

            if len(attempts) < 3:
                raise RuntimeError(
                    "503 UNAVAILABLE "
                    "high demand"
                )

            return "OK"

        result = (
            invoke_with_transient_retry(
                operation,
                max_attempts=3,
                base_delay_seconds=0,
                sleep_fn=lambda _: None,
            )
        )

        self.assertEqual(
            result,
            "OK",
        )

        self.assertEqual(
            len(attempts),
            3,
        )

    def test_permanent_error_not_retried(
        self,
    ):
        attempts = []

        def operation():
            attempts.append(1)

            raise RuntimeError(
                "401 invalid API key"
            )

        with self.assertRaises(
            RuntimeError
        ):
            invoke_with_transient_retry(
                operation,
                max_attempts=3,
                base_delay_seconds=0,
                sleep_fn=lambda _: None,
            )

        self.assertEqual(
            len(attempts),
            1,
        )


if __name__ == "__main__":
    unittest.main()
