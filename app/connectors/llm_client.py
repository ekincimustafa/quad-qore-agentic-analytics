"""Configured Chat Completions client with a controlled error boundary."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from dotenv import load_dotenv
from openai import (
    APIConnectionError,
    APIResponseValidationError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    OpenAIError,
    PermissionDeniedError,
    RateLimitError,
)


class LLMConfigurationError(RuntimeError):
    """Missing/invalid local settings; messages never contain their values."""


class LLMRequestError(RuntimeError):
    """Safe application error; raw provider response is intentionally omitted."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class LLMSettings:
    api_key: str = field(repr=False)
    base_url: str
    chat_model: str
    timeout_seconds: float = 30.0
    reasoning_effort: Literal["low", "medium", "high"] | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("LLM_API_KEY", self.api_key),
            ("LLM_BASE_URL", self.base_url),
            ("LLM_CHAT_MODEL", self.chat_model),
        ):
            if not isinstance(value, str) or not value.strip():
                raise LLMConfigurationError(f"{name} boş bırakılamaz.")
        try:
            url = urlsplit(self.base_url)
            valid_url = (
                url.scheme == "https"
                and bool(url.hostname)
                and url.username is None
                and url.password is None
                and not url.query
                and not url.fragment
                and not any(char.isspace() for char in self.base_url)
            )
            url.port  # Validate malformed/out-of-range ports as well.
        except ValueError:
            valid_url = False
        if not valid_url:
            raise LLMConfigurationError(
                "LLM_BASE_URL, credential/query/fragment içermeyen bir HTTPS adresi olmalıdır."
            )
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or not math.isfinite(self.timeout_seconds)
            or not 0 < self.timeout_seconds <= 120
        ):
            raise LLMConfigurationError(
                "LLM_TIMEOUT_SECONDS, 0'dan büyük ve en fazla 120 olmalıdır."
            )
        if self.reasoning_effort is not None and (
            not isinstance(self.reasoning_effort, str)
            or self.reasoning_effort not in ("low", "medium", "high")
        ):
            raise LLMConfigurationError(
                "LLM_REASONING_EFFORT boş, low, medium veya high olmalıdır."
            )


def read_llm_settings() -> LLMSettings:
    """Read repo-local .env lazily; process environment takes precedence."""
    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
    try:
        timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "30").strip())
    except ValueError:
        raise LLMConfigurationError("LLM_TIMEOUT_SECONDS sayısal olmalıdır.") from None
    return LLMSettings(
        api_key=os.getenv("LLM_API_KEY", "").strip(),
        base_url=os.getenv("LLM_BASE_URL", "").strip(),
        chat_model=os.getenv("LLM_CHAT_MODEL", "").strip(),
        timeout_seconds=timeout,
        reasoning_effort=os.getenv("LLM_REASONING_EFFORT", "").strip() or None,
    )


def create_llm_client(settings: LLMSettings) -> OpenAI:
    """One SDK request attempt; no default provider, model or hidden retries."""
    return OpenAI(
        api_key=settings.api_key,
        base_url=settings.base_url,
        timeout=settings.timeout_seconds,
        max_retries=0,
    )


def _safe_provider_error(exc: OpenAIError) -> LLMRequestError:
    if isinstance(exc, APITimeoutError):
        return LLMRequestError("timeout", "LLM isteği zaman aşımına uğradı.")
    if isinstance(exc, AuthenticationError):
        return LLMRequestError("authentication_failed", "LLM kimlik doğrulaması başarısız.")
    if isinstance(exc, PermissionDeniedError):
        return LLMRequestError("access_denied", "Seçilen LLM modeline erişim izni yok.")
    if isinstance(exc, RateLimitError):
        return LLMRequestError("rate_limited", "LLM kullanım sınırına ulaşıldı.")
    if isinstance(exc, APIConnectionError):
        return LLMRequestError("connection_failed", "LLM sağlayıcısına bağlanılamadı.")
    if isinstance(exc, APIResponseValidationError):
        return LLMRequestError("invalid_response", "LLM yanıtı beklenen biçimde değil.")
    if isinstance(exc, APIStatusError):
        if exc.status_code >= 500:
            return LLMRequestError("provider_unavailable", "LLM sağlayıcısı geçici olarak kullanılamıyor.")
        return LLMRequestError("request_rejected", "LLM sağlayıcısı isteği reddetti.")
    return LLMRequestError("provider_error", "LLM isteği tamamlanamadı.")


def ask_llm(prompt: str, *, settings: LLMSettings | None = None) -> str:
    """Return one complete text response, without exposing provider errors."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("LLM modeline gönderilecek mesaj boş olmayan metin olmalıdır.")
    settings = settings if settings is not None else read_llm_settings()
    request: dict[str, Any] = {
        "model": settings.chat_model,
        "messages": [{"role": "user", "content": prompt.strip()}],
    }
    # Omit the option entirely for existing configurations/providers.
    if settings.reasoning_effort is not None:
        request["reasoning_effort"] = settings.reasoning_effort
    try:
        with create_llm_client(settings) as client:
            response = client.chat.completions.create(**request)
    except OpenAIError as exc:
        raise _safe_provider_error(exc) from None

    choices = getattr(response, "choices", None)
    if not isinstance(choices, list) or len(choices) != 1:
        raise LLMRequestError("invalid_response", "LLM yanıtı tek bir sonuç içermelidir.")
    choice = choices[0]
    content = getattr(getattr(choice, "message", None), "content", None)
    if (
        getattr(choice, "finish_reason", None) != "stop"
        or not isinstance(content, str)
        or not content.strip()
    ):
        raise LLMRequestError("invalid_response", "LLM tam ve boş olmayan metin döndürmedi.")
    return content.strip()
