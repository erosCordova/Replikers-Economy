from __future__ import annotations

import hashlib
import io
import shutil
import unittest
import zipfile

import app.models  # noqa: F401

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.base import Base
from app.models.execution import (
    ExecutionWorkspace,
)
from app.models.project import Project
from app.models.project_specialist import (
    ProjectFinalReview,
)
from app.services.project_delivery_snapshot_service import (
    build_snapshot_zip,
    ensure_delivery_snapshot,
    list_snapshot_files,
)
from app.services.workspace_service import (
    workspace_root,
    write_text_file,
)


class Phase23DeliverySnapshotTests(
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

        self.project = Project(
            client_id=1,
            title="Proyecto snapshot",
            description=(
                "Proyecto para validar "
                "versiones inmutables."
            ),
            status="completed",
            currency="PEN",
            payment_status="settled",
        )

        self.db.add(
            self.project
        )

        self.db.flush()

        self.workspace = ExecutionWorkspace(
            contract_id=5001,
            project_id=self.project.id,
            task_id=5002,
            repliker_id=5003,
            status="ready",
            storage_driver="local",
            root_ref=(
                "phase23-snapshot-"
                + str(id(self))
            ),
            max_files=20,
            max_file_bytes=2_000_000,
            max_total_bytes=5_000_000,
        )

        self.db.add(
            self.workspace
        )

        self.review = ProjectFinalReview(
            project_id=self.project.id,
            requirement_id=6001,
            reviewer_repliker_id=6002,
            attempt_number=1,
            status="approved",
            score=98,
            summary="Aprobado.",
            corrections_json="[]",
            reasoning="Correcto.",
        )

        self.db.add(
            self.review
        )

        self.db.commit()

    def tearDown(self):
        try:
            root = workspace_root(
                self.workspace
            )

            if root.exists():
                shutil.rmtree(
                    root
                )

        finally:
            self.db.close()
            self.engine.dispose()

    def test_snapshot_is_immutable(
        self,
    ):
        artifact = write_text_file(
            db=self.db,
            workspace=self.workspace,
            relative_path="resultado.txt",
            content="VERSION UNO",
        )

        self.db.commit()

        snapshot = (
            ensure_delivery_snapshot(
                db=self.db,
                project_id=self.project.id,
                final_review_id=
                    self.review.id,
            )
        )

        self.db.commit()

        files = list_snapshot_files(
            db=self.db,
            snapshot_id=snapshot.id,
        )

        self.assertEqual(
            len(files),
            1,
        )

        self.assertEqual(
            bytes(files[0].content),
            b"VERSION UNO",
        )

        write_text_file(
            db=self.db,
            workspace=self.workspace,
            relative_path="resultado.txt",
            content="VERSION DOS",
        )

        self.db.commit()

        historical = (
            list_snapshot_files(
                db=self.db,
                snapshot_id=
                    snapshot.id,
            )[0]
        )

        self.assertEqual(
            bytes(historical.content),
            b"VERSION UNO",
        )

        self.assertNotEqual(
            historical.sha256,
            artifact.sha256,
        )

    def test_zip_contains_manifest_and_files(
        self,
    ):
        write_text_file(
            db=self.db,
            workspace=self.workspace,
            relative_path=
                "entrega/final.txt",
            content=
                "ENTREGA FINAL",
        )

        self.db.commit()

        snapshot = (
            ensure_delivery_snapshot(
                db=self.db,
                project_id=self.project.id,
                final_review_id=
                    self.review.id,
            )
        )

        self.db.commit()

        package = build_snapshot_zip(
            db=self.db,
            snapshot=snapshot,
        )

        digest = (
            hashlib.sha256(
                package
            )
            .hexdigest()
        )

        self.assertEqual(
            digest,
            snapshot.package_sha256,
        )

        with zipfile.ZipFile(
            io.BytesIO(package),
            "r",
        ) as archive:
            names = (
                archive.namelist()
            )

            self.assertIn(
                "MANIFIESTO.json",
                names,
            )

            self.assertIn(
                "tarea-5002/"
                "entrega/final.txt",
                names,
            )

            self.assertEqual(
                archive.read(
                    "tarea-5002/"
                    "entrega/final.txt"
                ),
                b"ENTREGA FINAL",
            )

    def test_same_review_does_not_duplicate_snapshot(
        self,
    ):
        write_text_file(
            db=self.db,
            workspace=self.workspace,
            relative_path="a.txt",
            content="A",
        )

        first = (
            ensure_delivery_snapshot(
                db=self.db,
                project_id=self.project.id,
                final_review_id=
                    self.review.id,
            )
        )

        second = (
            ensure_delivery_snapshot(
                db=self.db,
                project_id=self.project.id,
                final_review_id=
                    self.review.id,
            )
        )

        self.assertEqual(
            first.id,
            second.id,
        )

        self.assertEqual(
            first.version_label,
            "v1.0",
        )


if __name__ == "__main__":
    unittest.main()
