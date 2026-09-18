from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.5.0"
ARCHIVE_NAME = f"gyte-ai-learning-pipeline-{VERSION}.tar.gz"
ROOT_NAME = f"gyte-ai-learning-pipeline-{VERSION}"

REQUIRED_MEMBERS = {
    f"{ROOT_NAME}/README.md",
    f"{ROOT_NAME}/CHANGELOG.md",
    f"{ROOT_NAME}/docs/installation.md",
    f"{ROOT_NAME}/docs/release-notes-v0.5.0.md",
    f"{ROOT_NAME}/scripts/install-local.sh",
    f"{ROOT_NAME}/bin/gyte-lesson-kindle",
    f"{ROOT_NAME}/bin/gyte-editorial-candidate",
    f"{ROOT_NAME}/bin/gyte-fact-check",
    f"{ROOT_NAME}/bin/gyte-publication-reproducibility",
    f"{ROOT_NAME}/bin/gyte-public-candidate",
    f"{ROOT_NAME}/bin/gyte-repository-handoff",
    f"{ROOT_NAME}/src/gyte_study_tools/__init__.py",
}

FORBIDDEN_PARTS = {
    ".git",
    "__pycache__",
    "tests",
    "dist",
}


class DownloadableReleaseTests(unittest.TestCase):
    def _build(self, output_dir: Path) -> None:
        completed = subprocess.run(
            ["bash", "scripts/build-release.sh", str(output_dir)],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\\n{completed.stdout}\\nstderr:\\n{completed.stderr}",
        )

    def test_release_archive_has_expected_identity_and_surface(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "dist"
            self._build(output_dir)

            archive = output_dir / ARCHIVE_NAME
            checksums = output_dir / "SHA256SUMS"

            self.assertTrue(archive.is_file())
            self.assertTrue(checksums.is_file())

            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            self.assertEqual(
                checksums.read_text(),
                f"{digest}  {ARCHIVE_NAME}\n",
            )

            with tarfile.open(archive, "r:gz") as bundle:
                names = set(bundle.getnames())

            self.assertTrue(REQUIRED_MEMBERS.issubset(names))

            for name in names:
                parts = set(Path(name).parts)
                self.assertTrue(
                    FORBIDDEN_PARTS.isdisjoint(parts),
                    msg=f"forbidden release member: {name}",
                )

    def test_release_build_fails_closed_when_required_input_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            source_root = temp / "source"
            output_dir = temp / "dist"

            shutil.copytree(
                PROJECT_ROOT,
                source_root,
                ignore=shutil.ignore_patterns(".git", "dist", "__pycache__", "*.pyc"),
            )
            (source_root / "README.md").unlink()

            completed = subprocess.run(
                ["bash", "scripts/build-release.sh", str(output_dir)],
                cwd=source_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(completed.returncode, 0)

            archive = output_dir / ARCHIVE_NAME
            checksums = output_dir / "SHA256SUMS"

            self.assertFalse(archive.exists())
            self.assertFalse(checksums.exists())


    def test_release_build_is_byte_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            first = temp / "first"
            second = temp / "second"

            self._build(first)
            self._build(second)

            self.assertEqual(
                (first / ARCHIVE_NAME).read_bytes(),
                (second / ARCHIVE_NAME).read_bytes(),
            )
            self.assertEqual(
                (first / "SHA256SUMS").read_bytes(),
                (second / "SHA256SUMS").read_bytes(),
            )

    def test_extracted_release_installs_without_repository_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            output_dir = temp / "dist"
            extract_root = temp / "extract"
            home = temp / "home"

            self._build(output_dir)
            extract_root.mkdir()
            home.mkdir()

            with tarfile.open(output_dir / ARCHIVE_NAME, "r:gz") as bundle:
                bundle.extractall(extract_root, filter="data")

            release_root = extract_root / ROOT_NAME

            self.assertFalse((release_root / ".git").exists())

            env = os.environ.copy()
            env["HOME"] = str(home)

            installed = subprocess.run(
                ["bash", "scripts/install-local.sh"],
                cwd=release_root,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(
                installed.returncode,
                0,
                msg=f"stdout:\\n{installed.stdout}\\nstderr:\\n{installed.stderr}",
            )

            shutil.rmtree(extract_root)

            version = subprocess.run(
                [str(home / ".local" / "bin" / "gyte-lesson-kindle"), "--version"],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(version.returncode, 0)
            self.assertIn(VERSION, version.stdout)


if __name__ == "__main__":
    unittest.main()
