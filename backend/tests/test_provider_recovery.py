from types import SimpleNamespace
import unittest

from app.agentic.provider_retry import (
    invoke_with_transient_retry,
    is_quota_exhausted_error,
    provider_retry_after_seconds,
)
from app.services.qa_workflow_service import (
    _can_resume_existing_retry,
)


class ProviderRecoveryTests(
    unittest.TestCase
):

    def test_short_free_tier_limit_is_transient(
        self,
    ):
        error = RuntimeError(
            "429 RESOURCE_EXHAUSTED. "
            "You exceeded your current quota. "
            "free_tier_requests. "
            "Please retry in 53.92s."
        )

        self.assertFalse(
            is_quota_exhausted_error(
                error
            )
        )

        self.assertAlmostEqual(
            provider_retry_after_seconds(
                error
            ),
            53.92,
            places=2,
        )

    def test_provider_retry_hint_is_respected(
        self,
    ):
        calls = []
        sleeps = []

        def operation():
            calls.append(True)

            if len(calls) == 1:
                raise RuntimeError(
                    "429 RESOURCE_EXHAUSTED "
                    "free_tier_requests "
                    "Please retry in 53.5s."
                )

            return "ok"

        result = (
            invoke_with_transient_retry(
                operation,
                max_attempts=2,
                sleep_fn=sleeps.append,
            )
        )

        self.assertEqual(
            result,
            "ok",
        )

        self.assertEqual(
            len(calls),
            2,
        )

        self.assertEqual(
            len(sleeps),
            1,
        )

        self.assertGreaterEqual(
            sleeps[0],
            54.5,
        )

    def test_long_quota_without_retry_hint_stops(
        self,
    ):
        error = RuntimeError(
            "quota exceeded for "
            "free_tier_requests"
        )

        self.assertTrue(
            is_quota_exhausted_error(
                error
            )
        )


class QARetryRecoveryTests(
    unittest.TestCase
):

    def test_transient_failed_retry_can_resume(
        self,
    ):
        retry = SimpleNamespace(
            status="execution_failed",
            execution_status="failed",
            next_review_id=None,
            error_summary=(
                "503 UNAVAILABLE high demand"
            ),
        )

        self.assertTrue(
            _can_resume_existing_retry(
                retry
            )
        )

    def test_stale_running_retry_can_resume(
        self,
    ):
        retry = SimpleNamespace(
            status="running",
            execution_status="pending",
            next_review_id=None,
            error_summary="",
        )

        self.assertTrue(
            _can_resume_existing_retry(
                retry
            )
        )

    def test_completed_retry_is_not_reopened(
        self,
    ):
        retry = SimpleNamespace(
            status="completed",
            execution_status="completed",
            next_review_id=123,
            error_summary="",
        )

        self.assertFalse(
            _can_resume_existing_retry(
                retry
            )
        )


if __name__ == "__main__":
    unittest.main()
