from __future__ import annotations

import hashlib
import shutil
import unittest

import app.models  # noqa: F401

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.base import Base
from app.models.execution import (
    ExecutionArtifactBlob,
    ExecutionWorkspace,
)
from app.services.workspace_service import (
    read_durable_artifact_bytes,
    workspace_root,
    write_text_file,
)


class Phase23DurableArtifactTests(
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

        self.workspace = ExecutionWorkspace(
            contract_id=1001,
            project_id=1002,
            task_id=1003,
            repliker_id=1004,
            status="ready",
            storage_driver="local",
            root_ref=(
                "phase23-test-"
                + str(id(self))
            ),
            max_files=20,
            max_file_bytes=2_000_000,
            max_total_bytes=5_000_000,
        )

        self.db.add(
            self.workspace
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

    def test_write_creates_durable_blob(
        self,
    ):
        artifact = write_text_file(
            db=self.db,
            workspace=self.workspace,
            relative_path=
                "entrega/resultado.txt",
            content=
                "Archivo durable.",
        )

        self.db.commit()

        blob = self.db.get(
            ExecutionArtifactBlob,
            artifact.id,
        )

        self.assertIsNotNone(
            blob
        )

        self.assertEqual(
            bytes(blob.content),
            b"Archivo durable.",
        )

        self.assertEqual(
            blob.sha256,
            hashlib.sha256(
                b"Archivo durable."
            ).hexdigest(),
        )

        self.assertEqual(
            self.workspace.storage_driver,
            "hybrid-db",
        )

    def test_durable_read_survives_local_deletion(
        self,
    ):
        artifact = write_text_file(
            db=self.db,
            workspace=self.workspace,
            relative_path=
                "entrega/final.txt",
            content=
                "Sobrevive al reinicio.",
        )

        self.db.commit()

        root = workspace_root(
            self.workspace
        )

        target = (
            root
            / "entrega"
            / "final.txt"
        )

        self.assertTrue(
            target.exists()
        )

        target.unlink()

        payload = (
            read_durable_artifact_bytes(
                db=self.db,
                workspace=self.workspace,
                artifact=artifact,
            )
        )

        self.assertEqual(
            payload,
            b"Sobrevive al reinicio.",
        )

    def test_old_local_artifact_can_be_backfilled(
        self,
    ):
        artifact = write_text_file(
            db=self.db,
            workspace=self.workspace,
            relative_path=
                "legacy.txt",
            content=
                "Contenido antiguo.",
        )

        self.db.commit()

        self.db.query(
            ExecutionArtifactBlob
        ).filter(
            ExecutionArtifactBlob.artifact_id
            == artifact.id
        ).delete()

        self.db.commit()

        self.assertIsNone(
            self.db.get(
                ExecutionArtifactBlob,
                artifact.id,
            )
        )

        payload = (
            read_durable_artifact_bytes(
                db=self.db,
                workspace=self.workspace,
                artifact=artifact,
            )
        )

        self.assertEqual(
            payload,
            b"Contenido antiguo.",
        )

        self.assertIsNotNone(
            self.db.get(
                ExecutionArtifactBlob,
                artifact.id,
            )
        )


if __name__ == "__main__":
    unittest.main()
