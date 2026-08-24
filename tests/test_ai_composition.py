"""Tests for the GiadaWare AI production composition boundary."""

from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gyte_study_tools.ai_advisory import AIAdvisoryFailure  # noqa: E402
from gyte_study_tools.ai_composition import (  # noqa: E402
    create_learning_source_analyzer,
)


class AIConfigurationError(Exception):
    pass


class AIUnavailableError(Exception):
    pass


class AITimeoutError(Exception):
    pass


class AIInvalidResponseError(Exception):
    pass


class AIUnsupportedCapabilityError(Exception):
    pass


class LookalikeAIUnavailableError(Exception):
    pass


class AICompositionTests(unittest.TestCase):
    def fake_modules(self, raised: BaseException | None = None):
        giadaware_ai = types.ModuleType("giadaware_ai")
        backends = types.ModuleType("giadaware_ai.backends")
        ollama = types.ModuleType("giadaware_ai.backends.ollama")

        class OllamaBackend:
            def __init__(self, *, model, base_url, timeout):
                self.model = model
                self.base_url = base_url
                self.timeout = timeout

        class AICapabilities:
            def __init__(self, backend):
                self.backend = backend

            def analyze_learning_source(self, text):
                if raised is not None:
                    raise raised
                return object()

        giadaware_ai.AICapabilities = AICapabilities
        giadaware_ai.AIConfigurationError = AIConfigurationError
        giadaware_ai.AIUnavailableError = AIUnavailableError
        giadaware_ai.AITimeoutError = AITimeoutError
        giadaware_ai.AIInvalidResponseError = AIInvalidResponseError
        giadaware_ai.AIUnsupportedCapabilityError = AIUnsupportedCapabilityError
        giadaware_ai.backends = backends

        backends.ollama = ollama
        ollama.OllamaBackend = OllamaBackend

        return {
            "giadaware_ai": giadaware_ai,
            "giadaware_ai.backends": backends,
            "giadaware_ai.backends.ollama": ollama,
        }

    def test_all_five_real_imported_exception_types_are_mapped(self) -> None:
        cases = (
            (AIConfigurationError("bad config"), "configuration"),
            (AIUnavailableError("offline"), "unavailable"),
            (AITimeoutError("slow"), "timeout"),
            (AIInvalidResponseError("bad response"), "invalid-response"),
            (AIUnsupportedCapabilityError("unsupported"), "unsupported"),
        )

        for error, expected_kind in cases:
            with self.subTest(expected_kind=expected_kind):
                with patch.dict(
                    sys.modules,
                    self.fake_modules(error),
                    clear=False,
                ):
                    analyzer = create_learning_source_analyzer(
                        {"GYTE_AI_MODEL": "fixture-model"}
                    )
                    with self.assertRaises(AIAdvisoryFailure) as context:
                        analyzer("prepared analysis")

                self.assertEqual(context.exception.kind, expected_kind)

    def test_same_name_lookalike_exception_is_not_mapped(self) -> None:
        lookalike = type(
            "AIUnavailableError",
            (Exception,),
            {"__module__": "synthetic"},
        )("programming error")

        with patch.dict(
            sys.modules,
            self.fake_modules(lookalike),
            clear=False,
        ):
            analyzer = create_learning_source_analyzer(
                {"GYTE_AI_MODEL": "fixture-model"}
            )
            with self.assertRaisesRegex(Exception, "programming error") as context:
                analyzer("prepared analysis")

        self.assertNotIsInstance(context.exception, AIAdvisoryFailure)

    def test_missing_model_is_configuration(self) -> None:
        with self.assertRaises(AIAdvisoryFailure) as context:
            create_learning_source_analyzer({})

        self.assertEqual(context.exception.kind, "configuration")

    def test_invalid_timeout_is_configuration(self) -> None:
        for raw in ("invalid", "0", "-1"):
            with self.subTest(raw=raw):
                with self.assertRaises(AIAdvisoryFailure) as context:
                    create_learning_source_analyzer(
                        {
                            "GYTE_AI_MODEL": "fixture-model",
                            "GYTE_AI_TIMEOUT": raw,
                        }
                    )

                self.assertEqual(context.exception.kind, "configuration")

    def test_composition_uses_configured_backend_values(self) -> None:
        modules = self.fake_modules()

        with patch.dict(sys.modules, modules, clear=False):
            analyzer = create_learning_source_analyzer(
                {
                    "GYTE_AI_MODEL": "fixture-model",
                    "GYTE_AI_BASE_URL": "http://fixture:11434",
                    "GYTE_AI_TIMEOUT": "9.5",
                }
            )

            capabilities = analyzer.__closure__[0].cell_contents
            backend = capabilities.backend

        self.assertEqual(backend.model, "fixture-model")
        self.assertEqual(backend.base_url, "http://fixture:11434")
        self.assertEqual(backend.timeout, 9.5)


if __name__ == "__main__":
    unittest.main()
