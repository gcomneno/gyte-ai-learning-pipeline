"""Structural tests for maintained bilingual documentation."""

from __future__ import annotations

import os
import re
import unittest
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]

DOCUMENT_PAIRS = (
    (Path("README.md"), Path("README.it.md")),
    (
        Path("docs/documentation-policy.md"),
        Path("docs/it/documentation-policy.md"),
    ),
    (Path("docs/architecture.md"), Path("docs/it/architecture.md")),
)

MARKDOWN_LINK = re.compile(r"(?<!!)\[[^]]+]\(([^)]+)\)")


def _read(path: Path) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _relative_link(from_path: Path, to_path: Path) -> str:
    return Path(os.path.relpath(to_path, start=from_path.parent)).as_posix()


def _relative_targets(path: Path) -> list[Path]:
    targets: list[Path] = []

    for raw_target in MARKDOWN_LINK.findall(_read(path)):
        target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
        if (
            not target
            or target.startswith(("#", "http://", "https://", "mailto:"))
        ):
            continue

        target = unquote(target.split("#", 1)[0])
        if not target:
            continue

        targets.append((ROOT / path.parent / target).resolve())

    return targets


class DocumentationTests(unittest.TestCase):
    def test_required_bilingual_pairs_exist(self) -> None:
        for english, italian in DOCUMENT_PAIRS:
            with self.subTest(english=english, italian=italian):
                self.assertTrue((ROOT / english).is_file(), english)
                self.assertTrue((ROOT / italian).is_file(), italian)

    def test_language_selectors_are_reciprocal(self) -> None:
        for english, italian in DOCUMENT_PAIRS:
            english_head = "\n".join(_read(english).splitlines()[:8])
            italian_head = "\n".join(_read(italian).splitlines()[:8])

            with self.subTest(path=english):
                self.assertIn("English", english_head)
                self.assertIn("Italiano", english_head)
                self.assertIn(
                    _relative_link(english, italian),
                    english_head,
                )

            with self.subTest(path=italian):
                self.assertIn("English", italian_head)
                self.assertIn("Italiano", italian_head)
                self.assertIn(
                    _relative_link(italian, english),
                    italian_head,
                )

    def test_relative_links_in_bilingual_documents_exist(self) -> None:
        repository_root = ROOT.resolve()

        for pair in DOCUMENT_PAIRS:
            for path in pair:
                for target in _relative_targets(path):
                    with self.subTest(path=path, target=target):
                        is_in_repository = (
                            target == repository_root
                            or repository_root in target.parents
                        )
                        self.assertTrue(
                            is_in_repository,
                            f"{path}: target escapes repository: {target}",
                        )
                        self.assertTrue(
                            target.exists(),
                            f"{path}: missing relative target {target}",
                        )


if __name__ == "__main__":
    unittest.main()
