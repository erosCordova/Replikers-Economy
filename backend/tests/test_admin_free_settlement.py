from pathlib import Path
import unittest


class AdminFreeSettlementTests(
    unittest.TestCase
):
    @staticmethod
    def _settlement_source() -> str:
        source = Path(
            "app/services/"
            "economy_service.py"
        ).read_text(
            encoding="utf-8"
        )

        start = source.find(
            "def settle_contract_earnings("
        )

        end = source.find(
            "\ndef ",
            start + 1,
        )

        if end < 0:
            end = len(source)

        return source[start:end]

    def test_admin_free_uses_system_clearing(
        self,
    ):
        source = (
            self._settlement_source()
        )

        self.assertIn(
            "is_admin_free = bool(",
            source,
        )

        self.assertIn(
            "ensure_system_clearing_account(",
            source,
        )

        self.assertIn(
            "settlement_source",
            source,
        )

        self.assertIn(
            "ensure_project_custody_account(",
            source,
        )

    def test_admin_free_does_not_require_custody_balance(
        self,
    ):
        source = (
            self._settlement_source()
        )

        self.assertIn(
            "not is_admin_free",
            source,
        )

        self.assertIn(
            "account_id=\n"
            "                settlement_source.id",
            source,
        )

        self.assertIn(
            "from_account_id=\n"
            "                    settlement_source.id",
            source,
        )

        self.assertNotIn(
            "from_account_id=\n"
            "                    custody.id",
            source,
        )


if __name__ == "__main__":
    unittest.main()
