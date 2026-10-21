import unittest

from app.agentic.model import (
    candidate_chat_model_names,
)


class AgenticModelFallbackTests(
    unittest.TestCase
):

    def test_36_falls_back_to_35(
        self,
    ):
        models = (
            candidate_chat_model_names(
                "gemini-3.6-flash"
            )
        )

        self.assertEqual(
            models[0],
            "gemini-3.6-flash",
        )

        self.assertIn(
            "gemini-3.5-flash-lite",
            models,
        )

        self.assertEqual(
            len(models),
            len(set(models)),
        )

    def test_35_falls_back_to_36(
        self,
    ):
        models = (
            candidate_chat_model_names(
                "gemini-3.5-flash-lite"
            )
        )

        self.assertEqual(
            models[0],
            "gemini-3.5-flash-lite",
        )

        self.assertIn(
            "gemini-3.6-flash",
            models,
        )

        self.assertEqual(
            len(models),
            len(set(models)),
        )


if __name__ == "__main__":
    unittest.main()
