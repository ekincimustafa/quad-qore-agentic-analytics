"""Explicit single-request probe or the existing live Housing narration check."""

import argparse
from dataclasses import replace
import json
import os
from pathlib import Path
import sys
import time

import httpx

from app.connectors import llm_client
from app.connectors.llm_client import LLMConfigurationError, LLMRequestError


_SAFE_ERROR_CODES = frozenset({
    "timeout", "authentication_failed", "access_denied", "rate_limited",
    "connection_failed", "invalid_response", "provider_unavailable",
    "request_rejected", "provider_error",
})


def _timeout_phase(error: BaseException) -> str | None:
    """Inspect exception types only; never serialize messages, URLs or requests."""
    phases = (
        (httpx.ConnectTimeout, "connect"), (httpx.ReadTimeout, "read"),
        (httpx.WriteTimeout, "write"), (httpx.PoolTimeout, "pool"),
    )
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        for exception_type, phase in phases:
            if isinstance(current, exception_type):
                return phase
        current = current.__cause__ or current.__context__
    return None


def _probe(args: argparse.Namespace) -> None:
    snapshot = os.environ.copy()
    attempts = 0
    started: float | None = None
    try:
        settings = llm_client.read_llm_settings()
        overrides = {}
        if args.reasoning_effort is not None:
            overrides["reasoning_effort"] = args.reasoning_effort
        if args.timeout_seconds is not None:
            overrides["timeout_seconds"] = args.timeout_seconds
        settings = replace(settings, **overrides)
        print("Tek kısa canlı üretim isteği; ekonomik analiz çalıştırılmaz.")
        print(f"Düşünme seviyesi: {settings.reasoning_effort or 'provider_default'}")
        print(f"SDK timeout: {settings.timeout_seconds:g} sn; retry: 0")
        started = time.perf_counter()
        attempts = 1
        answer = llm_client.ask_llm("Reply with exactly OK.", settings=settings)
        if answer != "OK":
            print("Yanıt tam OK değil; yanıt içeriği yazdırılmadı.")
            raise SystemExit(1)
        print("Kısa üretim isteği doğrulandı; bu, analiz/plan doğruluğu kabulü değildir.")
    except LLMConfigurationError:
        print("Yerel LLM yapılandırması geçersiz; sağlayıcı isteği başlatılmadı.")
        raise SystemExit(1) from None
    except LLMRequestError as error:
        code = error.code if isinstance(error.code, str) and error.code in _SAFE_ERROR_CODES else "unknown"
        print(f"LLM hatası: {code}")
        if code == "timeout":
            print(f"Timeout aşaması: {_timeout_phase(error) or 'unknown'}")
        raise SystemExit(1) from None
    except Exception:
        print("İstemci kontrolü tamamlanamadı; hata ayrıntıları yazdırılmadı.")
        raise SystemExit(1) from None
    finally:
        if started is not None:
            print(f"İstemci çağrısı süresi: {time.perf_counter() - started:.3f} sn (saf model süresi değil)")
        print(f"İstemci çağrı denemesi: {attempts}; otomatik tekrar: 0")
        os.environ.clear()
        os.environ.update(snapshot)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", action="store_true", help="Analiz olmadan tek kısa canlı üretim isteği")
    parser.add_argument("--reasoning-effort", choices=("low", "medium", "high"))
    parser.add_argument("--timeout-seconds", type=float)
    args = parser.parse_args([] if argv is None else argv)
    if not args.probe and (args.reasoning_effort is not None or args.timeout_seconds is not None):
        parser.error("Geçici ayar seçenekleri yalnız --probe ile kullanılabilir.")
    if args.probe:
        _probe(args)
        return

    import pandas as pd

    from app.services.housing_analysis import HousingNarrationError, run_housing_analysis
    from app.tools.housing_narrator import narrate_housing_evidence_with_llm

    fixture = Path(__file__).resolve().parents[1] / "docs/housing-api-example.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    print("Sentetik Housing evidence ile canlı LLM JSON sözleşmesi kontrol ediliyor...")
    try:
        result = run_housing_analysis(
            pd.DataFrame(payload["bddk_monthly"]),
            pd.DataFrame(payload["evds_monthly"]),
            start_period=payload["start_period"],
            end_period=payload["end_period"],
            bddk_source_ref=payload["bddk_source_ref"],
            evds_source_refs=payload["evds_source_refs"],
            narrator=narrate_housing_evidence_with_llm,
        )
    except HousingNarrationError as error:
        cause = error.__cause__
        if isinstance(cause, LLMConfigurationError):
            print(f"Yapılandırma hatası: {cause}")
        elif isinstance(cause, LLMRequestError):
            print(f"LLM hatası ({cause.code}): {cause}")
        else:
            print("Housing anlatımı doğrulanamadı; model JSON sözleşmesini karşılamadı.")
        raise SystemExit(1) from None
    print("Housing JSON sözleşmesi doğrulandı; bu bir başarı oranı ölçümü değildir.")
    print(f"İncelenen ay: {result.evidence.observed_month_count}")
    print(f"Eşleşen aylar: {', '.join(result.evidence.matched_periods)}")
    print(result.narration)


if __name__ == "__main__":
    main(sys.argv[1:])
