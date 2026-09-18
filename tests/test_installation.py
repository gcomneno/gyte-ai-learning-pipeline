from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COMMANDS = (
    "gyte-editorial-candidate",
    "gyte-fact-check",
    "gyte-lesson-kindle",
    "gyte-publication-reproducibility",
    "gyte-public-candidate",
    "gyte-repository-handoff",
)


class StandaloneInstallationTests(unittest.TestCase):
    def test_installer_creates_checkout_independent_user_installation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            release_root = temp / "release"
            home = temp / "home"

            shutil.copytree(
                PROJECT_ROOT,
                release_root,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            home.mkdir()

            env = os.environ.copy()
            env["HOME"] = str(home)

            completed = subprocess.run(
                ["bash", "scripts/install-local.sh"],
                cwd=release_root,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(
                completed.returncode,
                0,
                msg=f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
            )

            install_root = (
                home
                / ".local"
                / "share"
                / "gyte-ai-learning-pipeline"
                / "0.5.0"
            )
            self.assertTrue((install_root / "src" / "gyte_study_tools").is_dir())

            for command in COMMANDS:
                installed_command = home / ".local" / "bin" / command
                self.assertTrue(
                    installed_command.exists() or installed_command.is_symlink(),
                    command,
                )
                self.assertEqual(
                    installed_command.resolve().parent,
                    install_root / "bin",
                )

            shutil.rmtree(release_root)

            version = subprocess.run(
                [str(home / ".local" / "bin" / "gyte-lesson-kindle"), "--version"],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(
                version.returncode,
                0,
                msg=f"stdout:\n{version.stdout}\nstderr:\n{version.stderr}",
            )
            self.assertIn("0.5.0", version.stdout)


    def test_installer_refuses_unrelated_command_collision(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            release_root = temp / "release"
            home = temp / "home"
            bin_root = home / ".local" / "bin"

            shutil.copytree(
                PROJECT_ROOT,
                release_root,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            bin_root.mkdir(parents=True)

            collision = bin_root / "gyte-fact-check"
            collision.write_text("#!/usr/bin/env bash\\necho unrelated\\n")
            collision.chmod(0o755)

            env = os.environ.copy()
            env["HOME"] = str(home)

            completed = subprocess.run(
                ["bash", "scripts/install-local.sh"],
                cwd=release_root,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(
                collision.read_text(),
                "#!/usr/bin/env bash\\necho unrelated\\n",
            )

            install_root = (
                home
                / ".local"
                / "share"
                / "gyte-ai-learning-pipeline"
                / "0.5.0"
            )
            self.assertFalse(install_root.exists())

    def test_installer_failure_does_not_publish_partial_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            release_root = temp / "release"
            home = temp / "home"

            shutil.copytree(
                PROJECT_ROOT,
                release_root,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            home.mkdir()

            broken_command = release_root / "bin" / "gyte-public-candidate"
            broken_command.unlink()

            env = os.environ.copy()
            env["HOME"] = str(home)

            completed = subprocess.run(
                ["bash", "scripts/install-local.sh"],
                cwd=release_root,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(completed.returncode, 0)

            install_root = (
                home
                / ".local"
                / "share"
                / "gyte-ai-learning-pipeline"
                / "0.5.0"
            )
            self.assertFalse(install_root.exists())


if __name__ == "__main__":
    unittest.main()
