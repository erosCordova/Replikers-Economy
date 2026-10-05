from __future__ import annotations

import hashlib
import unittest

from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app.api.routes.projects import (
    download_project_artifact,
    download_project_version_file,
    download_project_version_package,
)
from app.models.execution import (
    ExecutionArtifact,
    ExecutionWorkspace,
    ProjectDeliverySnapshotFile,
)


class FakeDatabase:
    def __init__(
        self,
        *,
        artifact=None,
        workspace=None,
        snapshot_file=None,
    ):
        self.artifact = artifact
        self.workspace = workspace
        self.snapshot_file = (
            snapshot_file
        )

        self.commits = 0
        self.rollbacks = 0

    def get(
        self,
        model,
        identifier,
    ):
        del identifier

        if model is ExecutionArtifact:
            return self.artifact

        if model is ExecutionWorkspace:
            return self.workspace

        if (
            model
            is ProjectDeliverySnapshotFile
        ):
            return self.snapshot_file

        return None

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class Phase23DownloadSecurityTests(
    unittest.TestCase
):
    def setUp(self):
        self.user = SimpleNamespace(
            id=10,
            role="client",
        )

        self.project = SimpleNamespace(
            id=20,
            client_id=10,
        )

    def test_artifact_download_returns_exact_bytes(
        self,
    ):
        payload = (
            b"archivo-durable-real"
        )

        digest = hashlib.sha256(
            payload
        ).hexdigest()

        artifact = SimpleNamespace(
            id=30,
            workspace_id=40,
            relative_path=
                "entrega/resultado.txt",
            media_type=
                "text/plain",
            size_bytes=len(
                payload
            ),
            sha256=digest,
        )

        workspace = SimpleNamespace(
            id=40,
            project_id=
                self.project.id,
        )

        db = FakeDatabase(
            artifact=artifact,
            workspace=workspace,
        )

        with (
            patch(
                "app.api.routes.projects."
                "_get_accessible_project",
                return_value=
                    self.project,
            ) as access,
            patch(
                "app.api.routes.projects."
                "read_durable_artifact_bytes",
                return_value=
                    payload,
            ),
        ):
            response = (
                download_project_artifact(
                    project_id=
                        self.project.id,
                    artifact_id=
                        artifact.id,
                    db=db,
                    current_user=
                        self.user,
                )
            )

        access.assert_called_once()

        self.assertEqual(
            response.body,
            payload,
        )

        self.assertEqual(
            response.headers[
                "x-content-sha256"
            ],
            digest,
        )

        self.assertIn(
            "resultado.txt",
            response.headers[
                "content-disposition"
            ],
        )

        self.assertEqual(
            db.commits,
            1,
        )

    def test_artifact_from_other_project_is_hidden(
        self,
    ):
        artifact = SimpleNamespace(
            id=30,
            workspace_id=40,
            relative_path=
                "privado.txt",
            media_type=
                "text/plain",
            size_bytes=1,
            sha256="0" * 64,
        )

        workspace = SimpleNamespace(
            id=40,
            project_id=999,
        )

        db = FakeDatabase(
            artifact=artifact,
            workspace=workspace,
        )

        with patch(
            "app.api.routes.projects."
            "_get_accessible_project",
            return_value=
                self.project,
        ):
            with self.assertRaises(
                HTTPException
            ) as context:
                download_project_artifact(
                    project_id=
                        self.project.id,
                    artifact_id=
                        artifact.id,
                    db=db,
                    current_user=
                        self.user,
                )

        self.assertEqual(
            context.exception.status_code,
            404,
        )

    def test_unauthorized_user_cannot_download_artifact(
        self,
    ):
        db = FakeDatabase()

        with patch(
            "app.api.routes.projects."
            "_get_accessible_project",
            side_effect=HTTPException(
                status_code=403,
                detail=(
                    "No tienes acceso "
                    "a este proyecto."
                ),
            ),
        ):
            with self.assertRaises(
                HTTPException
            ) as context:
                download_project_artifact(
                    project_id=20,
                    artifact_id=30,
                    db=db,
                    current_user=
                        SimpleNamespace(
                            id=999,
                            role="client",
                        ),
                )

        self.assertEqual(
            context.exception.status_code,
            403,
        )

    def test_version_zip_returns_integrity_hash(
        self,
    ):
        payload = (
            b"PK\x03\x04"
            b"paquete-version"
        )

        digest = hashlib.sha256(
            payload
        ).hexdigest()

        snapshot = SimpleNamespace(
            id=50,
            project_id=
                self.project.id,
            version_label=
                "v1.0",
            package_sha256=
                digest,
        )

        db = FakeDatabase()

        with (
            patch(
                "app.api.routes.projects."
                "_get_accessible_project",
                return_value=
                    self.project,
            ),
            patch(
                "app.api.routes.projects."
                "get_delivery_snapshot",
                return_value=
                    snapshot,
            ),
            patch(
                "app.api.routes.projects."
                "build_snapshot_zip",
                return_value=
                    payload,
            ),
        ):
            response = (
                download_project_version_package(
                    project_id=
                        self.project.id,
                    final_review_id=60,
                    db=db,
                    current_user=
                        self.user,
                )
            )

        self.assertEqual(
            response.body,
            payload,
        )

        self.assertEqual(
            response.headers[
                "x-content-sha256"
            ],
            digest,
        )

        self.assertEqual(
            response.media_type,
            "application/zip",
        )

        self.assertIn(
            "v1.0.zip",
            response.headers[
                "content-disposition"
            ],
        )

    def test_corrupted_zip_is_rejected(
        self,
    ):
        snapshot = SimpleNamespace(
            id=50,
            project_id=
                self.project.id,
            version_label=
                "v1.0",
            package_sha256=
                "0" * 64,
        )

        db = FakeDatabase()

        with (
            patch(
                "app.api.routes.projects."
                "_get_accessible_project",
                return_value=
                    self.project,
            ),
            patch(
                "app.api.routes.projects."
                "get_delivery_snapshot",
                return_value=
                    snapshot,
            ),
            patch(
                "app.api.routes.projects."
                "build_snapshot_zip",
                return_value=
                    b"contenido-diferente",
            ),
        ):
            with self.assertRaises(
                HTTPException
            ) as context:
                download_project_version_package(
                    project_id=
                        self.project.id,
                    final_review_id=60,
                    db=db,
                    current_user=
                        self.user,
                )

        self.assertEqual(
            context.exception.status_code,
            409,
        )

        self.assertEqual(
            db.rollbacks,
            1,
        )

    def test_historical_file_is_immutable_and_downloadable(
        self,
    ):
        payload = (
            b"contenido-v1.0"
        )

        digest = hashlib.sha256(
            payload
        ).hexdigest()

        snapshot = SimpleNamespace(
            id=50,
            project_id=
                self.project.id,
        )

        item = SimpleNamespace(
            id=70,
            snapshot_id=
                snapshot.id,
            relative_path=
                "docs/manual.txt",
            media_type=
                "text/plain",
            sha256=digest,
            content=payload,
        )

        db = FakeDatabase(
            snapshot_file=item,
        )

        with (
            patch(
                "app.api.routes.projects."
                "_get_accessible_project",
                return_value=
                    self.project,
            ),
            patch(
                "app.api.routes.projects."
                "get_delivery_snapshot",
                return_value=
                    snapshot,
            ),
        ):
            response = (
                download_project_version_file(
                    project_id=
                        self.project.id,
                    final_review_id=60,
                    snapshot_file_id=
                        item.id,
                    db=db,
                    current_user=
                        self.user,
                )
            )

        self.assertEqual(
            response.body,
            payload,
        )

        self.assertEqual(
            response.headers[
                "x-content-sha256"
            ],
            digest,
        )

        self.assertIn(
            "manual.txt",
            response.headers[
                "content-disposition"
            ],
        )


if __name__ == "__main__":
    unittest.main()
