from __future__ import annotations

import base64
import unittest

import app.models  # noqa: F401

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.base import Base
from app.models.repliker import Repliker
from app.services.repliker_photo_service import (
    ReplikerPhotoError,
    get_repliker_photo,
    remove_repliker_photo,
    save_repliker_photo,
)


VALID_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB"
    "CAQAAAC1HAwCAAAAC0lEQVR42mNk+A8A"
    "AQUBAScY42YAAAAASUVORK5CYII="
)


class Phase23ReplikerPhotoTests(
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

        self.repliker = Repliker(
            owner_id=1,
            name="Repliker Foto",
            specialty="Generalist",
            description="Prueba",
            base_price_credits=100,
            is_system=False,
            is_published=False,
        )

        self.db.add(
            self.repliker
        )

        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_photo_can_be_saved(
        self,
    ):
        data_url = (
            "data:image/png;base64,"
            + VALID_PNG
        )

        result = save_repliker_photo(
            db=self.db,
            repliker=self.repliker,
            image_data_url=data_url,
        )

        self.db.commit()

        self.assertEqual(
            result["repliker_id"],
            self.repliker.id,
        )

        self.assertTrue(
            result["avatar_url"]
            .startswith(
                "data:image/png;base64,"
            )
        )

        self.assertEqual(
            get_repliker_photo(
                db=self.db,
                repliker_id=
                    self.repliker.id,
            ),
            result["avatar_url"],
        )

    def test_photo_can_be_removed(
        self,
    ):
        data_url = (
            "data:image/png;base64,"
            + VALID_PNG
        )

        save_repliker_photo(
            db=self.db,
            repliker=self.repliker,
            image_data_url=data_url,
        )

        result = (
            remove_repliker_photo(
                db=self.db,
                repliker=
                    self.repliker,
            )
        )

        self.db.commit()

        self.assertIsNone(
            result["avatar_url"]
        )

        self.assertIsNone(
            get_repliker_photo(
                db=self.db,
                repliker_id=
                    self.repliker.id,
            )
        )

    def test_svg_is_rejected(
        self,
    ):
        content = base64.b64encode(
            b"<svg></svg>"
        ).decode("ascii")

        with self.assertRaises(
            ReplikerPhotoError
        ):
            save_repliker_photo(
                db=self.db,
                repliker=
                    self.repliker,
                image_data_url=(
                    "data:image/svg+xml;"
                    "base64,"
                    + content
                ),
            )

    def test_fake_png_is_rejected(
        self,
    ):
        content = base64.b64encode(
            b"not-an-image"
        ).decode("ascii")

        with self.assertRaises(
            ReplikerPhotoError
        ):
            save_repliker_photo(
                db=self.db,
                repliker=
                    self.repliker,
                image_data_url=(
                    "data:image/png;"
                    "base64,"
                    + content
                ),
            )

    def test_large_photo_is_rejected(
        self,
    ):
        raw = (
            b"\x89PNG\r\n\x1a\n"
            + b"x" * 600_001
        )

        content = base64.b64encode(
            raw
        ).decode("ascii")

        with self.assertRaises(
            ReplikerPhotoError
        ):
            save_repliker_photo(
                db=self.db,
                repliker=
                    self.repliker,
                image_data_url=(
                    "data:image/png;"
                    "base64,"
                    + content
                ),
            )


if __name__ == "__main__":
    unittest.main()
