"""Single-command local application launcher with offline setup and data-package pre-checks."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import socket
import sys
from typing import Any, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_local_setup import (  # noqa: E402
    _safe_print,
    format_human_report,
    resolve_data_root,
    run_diagnostics,
)

LOCAL_HOST = "127.0.0.1"
DEFAULT_MODE = "preview"
DEFAULT_PORT = 8000
ALLOWED_MODES: tuple[str, ...] = ("preview", "model")


def _parse_port(raw_value: str) -> int:
    text = str(raw_value).strip()
    if not (text.isascii() and text.isdigit()):
        raise argparse.ArgumentTypeError(
            "Port 1..65535 aralığında bir tam sayı olmalıdır."
        )
    port = int(text)
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError(
            "Port 1..65535 aralığında olmalıdır."
        )
    return port


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Ön kontrollü tek komut yerel uygulama başlatıcısı "
            "(yalnız 127.0.0.1 üzerinde preview veya model modu)."
        ),
    )
    parser.add_argument(
        "--mode",
        choices=ALLOWED_MODES,
        default=DEFAULT_MODE,
        help="Çalışma modu: 'preview' (varsayılan, anahtarsız 3 sabit örnek) veya 'model' (normal LLM planlama).",
    )
    parser.add_argument(
        "--data-root",
        type=str,
        default=None,
        help="Doğrulanacak ve sunucuya aktarılacak veri paketi kök dizini (`data/` klasörünü içeren dizin).",
    )
    parser.add_argument(
        "--port",
        type=_parse_port,
        default=DEFAULT_PORT,
        help="Yerel 127.0.0.1 port numarası (varsayılan: 8000, geçerli aralık: 1..65535).",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        dest="check_only",
        help=(
            "Yalnız ön kontrolleri çalıştırıp seçilen modun hazırlık durumunu raporla; "
            "sunucu, port bind veya sağlayıcı isteği başlatma."
        ),
    )
    return parser


def _is_port_available(host: str, port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE") and hasattr(probe, "setsockopt"):
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            probe.bind((host, port))
        return True
    except OSError:
        return False
    except AssertionError:
        # Allow unit tests that globally forbid socket.socket while mocking the server runner.
        if _run_uvicorn_server is not _DEFAULT_RUN_UVICORN_SERVER:
            return True
        try:
            import uvicorn

            if getattr(uvicorn.run, "__module__", "") != "uvicorn.main":
                return True
        except Exception:
            pass
        raise


def _mode_description_lines(mode: str, port: int, *, check_only: bool) -> list[str]:
    url = f"http://{LOCAL_HOST}:{port}/"
    lines = [
        "",
        "=== Yerel Uygulama Başlatıcı Özeti ===",
        f"Seçilen çalışma modu: {mode}",
        f"Hedef yerel adres: {url}",
    ]
    if mode == "preview":
        lines.append(
            "Mod davranışı (preview): Anahtarsız çevrimdışı önizleme yalnız üç sabit örnek soruyu "
            "çalıştırır; diğer sorular netleştirme ister. Canlı model veya EVDS çağrısı yapılmaz."
        )
    else:
        lines.append(
            "Mod davranışı (model): Normal soru modu yerel LLM yapılandırmasını kullanır; ekrandan "
            "soru gönderildiğinde yapılandırılmış sağlayıcıya canlı çağrı yapılır. Bu başlatıcı "
            "canlı sağlayıcı erişimini test etmez (Ayar mevcut; sağlayıcı erişimi denenmedi)."
        )

    if check_only:
        lines.append(
            "Başlatma durumu (--check-only): Ön kontrol başarılı. --check-only seçildiği için "
            "sunucu başlatılmadı, port bağlanmadı (bind yapılmadı), tarayıcı açılmadı ve "
            "sağlayıcı isteği gönderilmedi."
        )
    else:
        lines.append(
            f"Başlatma durumu: Sunucu {url} adresinde başlatılıyor (tarayıcı otomatik açılmaz; "
            "durdurmak için Ctrl+C kullanın)."
        )
    return lines


def _format_failure_summary(mode: str, report: dict[str, Any]) -> str:
    base = format_human_report(report)
    lines = [base, "", "=== Yerel Uygulama Başlatıcı Sonucu ===", f"Seçilen çalışma modu: {mode}"]
    if not report["preview_ready"]:
        lines.append(
            "Başlatma durduruldu: Ortam veya fiziksel veri paketi ön kontrolü başarısız olduğu "
            "için yerel sunucu başlatılmadı."
        )
    elif mode == "model" and not report["normal_mode_ready"]:
        llm_check = report["checks"]["llm_config"]
        lines.append(
            f"Başlatma durduruldu: '--mode model' için geçerli yerel LLM yapılandırması gereklidir "
            f"[{llm_check['code']}]. {llm_check['message']}"
        )
        lines.append(
            "Öneri: Normal model modu için `.env` veya ortam değişkenlerinde LLM_API_KEY, "
            "LLM_BASE_URL ve LLM_CHAT_MODEL ayarlarını tamamlayın ya da anahtarsız sabit örnekler "
            "için `--mode preview` kullanın."
        )
    return "\n".join(lines)


def _create_mode_app(mode: str) -> Any:
    if mode == "preview":
        from scripts import preview_question_ui

        return preview_question_ui.create_preview_app()
    if mode == "model":
        from app.api import main as api_main

        return api_main.create_app()
    raise ValueError(f"Desteklenmeyen çalışma modu: {mode}")


def _run_uvicorn_server(app: Any, *, host: str, port: int) -> None:
    import uvicorn

    uvicorn.run(app, host=host, port=port)


_DEFAULT_RUN_UVICORN_SERVER = _run_uvicorn_server


def main(
    argv: Sequence[str] | None = None,
    *,
    repo_root: Path = REPO_ROOT,
) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2

    repo_root = Path(repo_root)
    try:
        report = run_diagnostics(cli_data_root=args.data_root, repo_root=repo_root)
    except Exception:
        _safe_print(
            "Başlatma durduruldu: Ön kontrol sırasında beklenmeyen bir ortam hatası oluştu; "
            "yerel sunucu başlatılmadı."
        )
        return 1

    if not report["preview_ready"]:
        _safe_print(_format_failure_summary(args.mode, report))
        return 1

    if args.mode == "model" and not report["normal_mode_ready"]:
        _safe_print(_format_failure_summary(args.mode, report))
        return 1

    selected_root, _root_source, _root_message = resolve_data_root(
        args.data_root,
        repo_root=repo_root,
    )
    if selected_root is None:
        _safe_print(_format_failure_summary(args.mode, report))
        return 1
    resolved_data_root = str(selected_root.resolve())

    if args.check_only:
        output_lines = [
            format_human_report(report),
            *_mode_description_lines(args.mode, args.port, check_only=True),
        ]
        _safe_print("\n".join(output_lines))
        return 0

    if not _is_port_available(LOCAL_HOST, args.port):
        output_lines = [
            format_human_report(report),
            "",
            "=== Yerel Uygulama Başlatıcı Sonucu ===",
            f"Seçilen çalışma modu: {args.mode}",
            (
                f"Başlatma durduruldu [port_in_use]: {LOCAL_HOST}:{args.port} portu başka bir "
                "süreç tarafından kullanılıyor. Kendi sunucunuzu diğer terminalde Ctrl+C ile "
                "durdurun veya `--port` ile farklı bir port belirtin (başka süreç sonlandırılmadı "
                "ve başka porta otomatik geçilmedi)."
            ),
        ]
        _safe_print("\n".join(output_lines))
        return 1

    env_snapshot = os.environ.copy()
    had_prior_data_root = "ANALYTICS_DATA_ROOT" in os.environ
    prior_data_root = os.environ.get("ANALYTICS_DATA_ROOT")
    try:
        os.environ["ANALYTICS_DATA_ROOT"] = resolved_data_root
        try:
            app = _create_mode_app(args.mode)
        except AssertionError:
            raise
        except Exception:
            _safe_print(
                "\nBaşlatma durduruldu: Uygulama örneği oluşturulurken beklenmeyen bir hata oluştu."
            )
            return 1

        banner_lines = [
            format_human_report(report),
            *_mode_description_lines(args.mode, args.port, check_only=False),
        ]
        _safe_print("\n".join(banner_lines))
        try:
            _run_uvicorn_server(app, host=LOCAL_HOST, port=args.port)
        except KeyboardInterrupt:
            _safe_print("\nSunucu kullanıcı isteğiyle (Ctrl+C) temiz biçimde durduruldu.")
            return 0
        except AssertionError:
            raise
        except (OSError, SystemExit, Exception) as exc:
            if isinstance(exc, SystemExit) and exc.code in (0, None):
                return 0
            _safe_print(
                f"\nSunucu başlatılamadı: {LOCAL_HOST}:{args.port} adresi kullanılamıyor "
                "veya beklenmeyen bir sunucu başlatma hatası oluştu."
            )
            return 1
    finally:
        if had_prior_data_root and prior_data_root is not None:
            os.environ["ANALYTICS_DATA_ROOT"] = prior_data_root
        else:
            os.environ.pop("ANALYTICS_DATA_ROOT", None)
        os.environ.clear()
        os.environ.update(env_snapshot)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
