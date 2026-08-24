"""Production composition for the optional GiadaWare AI advisory."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from typing import Any

from gyte_study_tools.ai_advisory import AIAdvisoryFailure


Analyzer = Callable[[str], object]


def create_learning_source_analyzer(
    env: Mapping[str, str] | None = None,
) -> Analyzer:
    """Compose the public GiadaWare AI learning-source capability lazily."""

    environment = os.environ if env is None else env
    model = environment.get("GYTE_AI_MODEL", "").strip()

    if not model:
        raise AIAdvisoryFailure(
            "configuration",
            "GYTE_AI_MODEL è richiesto per --ai-advisory.",
        )

    timeout_raw = environment.get("GYTE_AI_TIMEOUT", "").strip()
    try:
        timeout = float(timeout_raw) if timeout_raw else 120.0
    except ValueError as error:
        raise AIAdvisoryFailure(
            "configuration",
            "GYTE_AI_TIMEOUT deve essere un numero positivo.",
        ) from error

    if timeout <= 0:
        raise AIAdvisoryFailure(
            "configuration",
            "GYTE_AI_TIMEOUT deve essere un numero positivo.",
        )

    try:
        from giadaware_ai import (
            AICapabilities,
            AIConfigurationError,
            AIInvalidResponseError,
            AITimeoutError,
            AIUnavailableError,
            AIUnsupportedCapabilityError,
        )
        from giadaware_ai.backends.ollama import OllamaBackend
    except ImportError as error:
        raise AIAdvisoryFailure(
            "configuration",
            "giadaware_ai con composizione Ollama non è importabile.",
        ) from error

    expected_types = (
        AIConfigurationError,
        AITimeoutError,
        AIUnavailableError,
        AIInvalidResponseError,
        AIUnsupportedCapabilityError,
    )

    def map_expected(error: BaseException) -> AIAdvisoryFailure:
        if isinstance(error, AIConfigurationError):
            kind = "configuration"
        elif isinstance(error, AITimeoutError):
            kind = "timeout"
        elif isinstance(error, AIUnavailableError):
            kind = "unavailable"
        elif isinstance(error, AIInvalidResponseError):
            kind = "invalid-response"
        elif isinstance(error, AIUnsupportedCapabilityError):
            kind = "unsupported"
        else:
            raise AssertionError("unexpected AI error type")

        return AIAdvisoryFailure(
            kind,
            str(error).strip() or type(error).__name__,
        )

    try:
        backend = OllamaBackend(
            model=model,
            base_url=environment.get(
                "GYTE_AI_BASE_URL",
                "http://ollama:11434",
            ),
            timeout=timeout,
        )
        capabilities = AICapabilities(backend)
    except expected_types as error:
        raise map_expected(error) from error

    def analyze(text: str) -> Any:
        try:
            return capabilities.analyze_learning_source(text)
        except expected_types as error:
            raise map_expected(error) from error

    return analyze
