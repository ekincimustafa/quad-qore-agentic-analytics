"""Offline local setup, dependency, data-package, and LLM config diagnostics."""

from __future__ import annotations

import argparse
from importlib import metadata
import json
import os
from pathlib import Path
import sys
from typing import Any, Sequence

from dotenv import load_dotenv

from app.connectors import llm_client
from app.connectors.llm_client import LLMConfigurationError
from app.services.economic_question import (
    EconomicInputError,
    HousingQuestionData,
    InflationQuestionData,
    derive_economic_coverage,
)
from app.services.housing_demo import DEFAULT_BDDK_SOURCE_REF
from app.services.housing_question_files import (
    VerifiedHousingQuestionDataError,
    VerifiedHousingQuestionPaths,
    load_verified_question_inputs,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PYTHON_MINOR = (3, 12)
REQUIRED_RUNTIME_PACKAGES: tuple[str, ...] = (
    "fastapi",
    "uvicorn",
    "pydantic",
    "pydantic-settings",
    "pandas",
    "duckdb",
    "pyarrow",
    "openpyxl",
    "pypdf",
    "httpx",
    "openai",
    "python-dotenv",
    "plotly",
)

KNOWN_DIAGNOSTIC_CODES: dict[str, str] = {
    "python_version_mismatch": "Python sürümü 3.12 değil.",
    "missing_dependencies": "Zorunlu çalışma zamanı paketlerinden biri veya birkaçı eksik.",
    "data_root_missing": "Seçilen veri kökü dizini bulunamadı veya bir klasör değil.",
    "data_files_missing": "Veri kökünde beklenen BDDK/EVDS Silver, Bronze veya manifest dosyaları eksik.",
    "data_integrity_failed": "BDDK/EVDS fiziksel veri paketi (Bronze/makbuz/hash/Silver/kapsam) doğrulamasını geçemedi.",
    "llm_not_configured": "Yerel model ayarları tanımlı değil; yalnız offline preview kullanılabilir.",
    "llm_config_invalid": "Yerel model ayarları eksik veya sözdizimi/aralık kuralına uymuyor; yalnız offline preview kullanılabilir.",
    "llm_configured_untested": "Yerel model ayarları mevcut; sağlayıcıya canlı bağlantı veya model erişimi denenmedi.",
}


def _check_python_version(version_info: Sequence[int] | None = None) -> dict[str, Any]:
    info = version_info if version_info is not None else sys.version_info
    major, minor, micro = int(info[0]), int(info[1]), int(info[2])
    detected = f"{major}.{minor}.{micro}"
    required = f"{REQUIRED_PYTHON_MINOR[0]}.{REQUIRED_PYTHON_MINOR[1]}"
    if (major, minor) == REQUIRED_PYTHON_MINOR:
        return {
            "status": "ok",
            "code": "ok",
            "detected_version": detected,
            "required_minor": required,
            "message": f"Python {detected} doğrulandı (beklenen: {required}).",
            "recommendation": None,
        }
    return {
        "status": "error",
        "code": "python_version_mismatch",
        "detected_version": detected,
        "required_minor": required,
        "message": f"Uyumsuz Python sürümü ({detected}); bu proje Python {required} gerektirir.",
        "recommendation": (
            "Python 3.12 ile sanal ortam oluşturup komutu .venv yorumlayıcısıyla çalıştırın "
            "(Windows: py -3.12 -m venv .venv; Linux: python3.12 -m venv .venv)."
        ),
    }


def _check_dependencies(
    packages: Sequence[str] = REQUIRED_RUNTIME_PACKAGES,
    version_lookup: Any = None,
) -> dict[str, Any]:
    lookup = version_lookup if version_lookup is not None else metadata.version
    missing: list[str] = []
    for pkg in packages:
        try:
            resolved = lookup(pkg)
            if not isinstance(resolved, str) or not resolved.strip():
                missing.append(pkg)
        except metadata.PackageNotFoundError:
            missing.append(pkg)
        except Exception:
            missing.append(pkg)

    if not missing:
        return {
            "status": "ok",
            "code": "ok",
            "required_count": len(packages),
            "missing_packages": [],
            "message": f"Gerekli {len(packages)} çalışma zamanı paketi kurulu.",
            "recommendation": None,
        }
    missing_list = ", ".join(missing)
    return {
        "status": "error",
        "code": "missing_dependencies",
        "required_count": len(packages),
        "missing_packages": missing,
        "message": f"Eksik çalışma zamanı paketleri tespit edildi: {missing_list}.",
        "recommendation": (
            "Python 3.12 sanal ortamında `python -m pip install -r requirements.txt` "
            "komutunu çalıştırarak bağımlılıkları kurun."
        ),
    }


def resolve_data_root(
    cli_data_root: str | Path | None = None,
    *,
    repo_root: Path = REPO_ROOT,
) -> tuple[Path | None, str, str]:
    """Select data root with priority: --data-root > process ANALYTICS_DATA_ROOT > local .env > repo root."""
    repo_root = Path(repo_root)
    if cli_data_root is not None:
        raw_cli = str(cli_data_root).strip()
        if not raw_cli:
            return None, "cli", "Veri kökü --data-root argümanında boş verildi."
        return Path(raw_cli), "cli", "Veri kökü --data-root argümanından seçildi."

    env_snapshot = os.environ.copy()
    try:
        had_process_var = "ANALYTICS_DATA_ROOT" in os.environ
        process_val = os.environ.get("ANALYTICS_DATA_ROOT", "").strip()
        if had_process_var and process_val:
            return Path(process_val), "env", "Veri kökü süreç ANALYTICS_DATA_ROOT ortam değişkeninden seçildi."

        dotenv_file = repo_root / ".env"
        if not had_process_var and dotenv_file.is_file():
            load_dotenv(dotenv_file, override=False)
            dotenv_val = os.environ.get("ANALYTICS_DATA_ROOT", "").strip()
            if dotenv_val:
                return (
                    Path(dotenv_val),
                    "dotenv",
                    "Veri kökü yerel .env dosyasındaki ANALYTICS_DATA_ROOT ayarından seçildi.",
                )
    finally:
        os.environ.clear()
        os.environ.update(env_snapshot)

    return repo_root, "repo_default", "Veri kökü varsayılan depo kök dizininden seçildi."


def _has_missing_package_files(data_root: Path, paths: VerifiedHousingQuestionPaths) -> bool:
    bddk_silver = data_root / paths.bddk_silver
    bddk_receipts = data_root / paths.bddk_bronze / "aylik" / "receipts"
    bddk_raw = data_root / paths.bddk_bronze / "aylik" / "raw"
    manifest_file = data_root / paths.evds_manifest

    if (
        not bddk_silver.is_file()
        or not bddk_receipts.is_dir()
        or not bddk_raw.is_dir()
        or not manifest_file.is_file()
    ):
        return True

    try:
        if not any(bddk_receipts.glob("*.json")) or not any(bddk_raw.iterdir()):
            return True
    except OSError:
        return True

    try:
        manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
    except Exception:
        return False

    if not isinstance(manifest_data, dict):
        return False

    silver_info = manifest_data.get("silver")
    if isinstance(silver_info, dict):
        silver_rel = silver_info.get("path")
        if (
            isinstance(silver_rel, str)
            and silver_rel.strip()
            and ".." not in silver_rel
            and not silver_rel.strip().startswith(("/", "\\"))
        ):
            if not (data_root / silver_rel.strip()).is_file():
                return True

    series_list = manifest_data.get("series")
    if isinstance(series_list, list):
        for series in series_list:
            if not isinstance(series, dict):
                continue
            bronze_list = series.get("bronze")
            if not isinstance(bronze_list, list):
                continue
            for bronze in bronze_list:
                if not isinstance(bronze, dict):
                    continue
                for key in ("receipt_path", "raw_path"):
                    rel_val = bronze.get(key)
                    if (
                        isinstance(rel_val, str)
                        and rel_val.strip()
                        and ".." not in rel_val
                        and not rel_val.strip().startswith(("/", "\\"))
                    ):
                        if not (data_root / rel_val.strip()).is_file():
                            return True
    return False


def _check_data_package(
    data_root: Path | None,
    source: str,
    source_message: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root_exists = bool(data_root is not None and data_root.exists() and data_root.is_dir())
    data_root_info = {
        "source": source,
        "exists": root_exists,
        "message": source_message,
    }

    target_root = data_root if data_root is not None else REPO_ROOT / "__missing_data_root__"
    paths = VerifiedHousingQuestionPaths(project_root=target_root)
    missing_files = True if not root_exists else _has_missing_package_files(target_root, paths)

    try:
        if data_root is None:
            raise VerifiedHousingQuestionDataError("Veri kökü boş.")
        inputs = load_verified_question_inputs(paths)
        coverage = derive_economic_coverage(
            housing=HousingQuestionData(
                bddk_monthly=inputs.bddk_monthly,
                evds_monthly=inputs.evds_monthly,
                bddk_source_ref=DEFAULT_BDDK_SOURCE_REF,
                evds_source_refs=inputs.evds_source_refs,
            ),
            inflation=InflationQuestionData(
                cpi_monthly=inputs.evds_monthly.loc[:, ["period", "cpi_index"]].copy(),
                source_ref=inputs.cpi_source_ref,
            ),
        )
        if coverage.housing is None or coverage.inflation is None:
            raise EconomicInputError("Ortak konut veya TÜFE kapsamı oluşturulamadı.")
    except (VerifiedHousingQuestionDataError, EconomicInputError, ValueError, TypeError, RuntimeError, OSError):
        if not root_exists:
            return data_root_info, {
                "status": "error",
                "code": "data_root_missing",
                "verified": False,
                "bddk": None,
                "cpi": None,
                "housing_coverage": None,
                "message": "Seçilen veri kökü dizini bulunamadı veya erişilebilir bir klasör değil.",
                "recommendation": (
                    "--data-root veya ANALYTICS_DATA_ROOT değerini `data/` dizinini doğrudan "
                    "içeren geçerli paket klasörüne (`inputs`) yönlendirin."
                ),
            }
        if missing_files:
            nested_inputs_hint = (
                " Seçilen klasörün altında `inputs/data` bulundu; doğrudan `inputs` dizinini seçin."
                if (target_root / "inputs" / "data").is_dir()
                else ""
            )
            return data_root_info, {
                "status": "error",
                "code": "data_files_missing",
                "verified": False,
                "bddk": None,
                "cpi": None,
                "housing_coverage": None,
                "message": (
                    "Seçilen veri kökünde beklenen BDDK/EVDS Silver, Bronze veya manifest "
                    "dosyaları eksik." + nested_inputs_hint
                ),
                "recommendation": (
                    "Gerçek veri paketi Git'te yer almaz; teslim paketini (`Housing_tam_teslim_20261018.zip`) "
                    "çıkarıp `data/` klasörünü içeren `inputs` dizinini `--data-root` veya "
                    "`ANALYTICS_DATA_ROOT` ile gösterin. Anahtarsız sentetik örnek için "
                    "`python -m scripts.render_housing_sample` komutunu kullanabilirsiniz."
                ),
            }
        return data_root_info, {
            "status": "error",
            "code": "data_integrity_failed",
            "verified": False,
            "bddk": None,
            "cpi": None,
            "housing_coverage": None,
            "message": (
                "BDDK/EVDS fiziksel veri paketi (Bronze/makbuz/hash/Silver veya dönem sürekliliği) "
                "bütünlük doğrulamasını geçemedi."
            ),
            "recommendation": (
                "Veri dosyalarını elle onarmaya veya yeniden indirmeye çalışmayın; "
                "doğrulanmış teslim arşivini temiz bir dizine yeniden çıkarın."
            ),
        }

    bddk_periods = sorted(inputs.bddk_monthly["period"].astype(str).tolist())
    cpi_periods = sorted(inputs.evds_monthly["period"].astype(str).tolist())
    shared_periods = sorted(set(bddk_periods) & set(cpi_periods))

    return data_root_info, {
        "status": "ok",
        "code": "ok",
        "verified": True,
        "bddk": {
            "row_count": len(bddk_periods),
            "start_period": bddk_periods[0],
            "end_period": bddk_periods[-1],
        },
        "cpi": {
            "row_count": len(cpi_periods),
            "start_period": coverage.inflation.start_period,
            "end_period": coverage.inflation.end_period,
        },
        "housing_coverage": {
            "row_count": len(shared_periods),
            "start_period": coverage.housing.start_period,
            "end_period": coverage.housing.end_period,
        },
        "message": (
            f"Fiziksel veri paketi doğrulandı: BDDK {len(bddk_periods)} ay "
            f"({bddk_periods[0]}–{bddk_periods[-1]}), TÜFE {len(cpi_periods)} ay "
            f"({coverage.inflation.start_period}–{coverage.inflation.end_period}), "
            f"ortak konut kapsamı {len(shared_periods)} ay "
            f"({coverage.housing.start_period}–{coverage.housing.end_period})."
        ),
        "recommendation": None,
    }


def _check_llm_configuration(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Validate local LLM configuration syntax without making any network or provider call."""
    env_snapshot = os.environ.copy()
    original_llm_load_dotenv = llm_client.load_dotenv
    try:
        dotenv_file = Path(repo_root) / ".env"
        if Path(repo_root).resolve() != REPO_ROOT.resolve():
            llm_client.load_dotenv = (
                lambda _path, *, override=False: load_dotenv(dotenv_file, override=override)
                if dotenv_file.is_file()
                else False
            )

        try:
            llm_client.read_llm_settings()
        except LLMConfigurationError as exc:
            any_llm_var_set = any(
                os.environ.get(name, "").strip()
                for name in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_CHAT_MODEL")
            ) or (
                "LLM_TIMEOUT_SECONDS" in os.environ
                and os.environ.get("LLM_TIMEOUT_SECONDS", "").strip() != "30"
            )
            if not any_llm_var_set:
                return {
                    "status": "warning",
                    "code": "llm_not_configured",
                    "configured": False,
                    "provider_access_tested": False,
                    "live_access_verified": False,
                    "message": (
                        "Model ayarı tanımlı değil; anahtarsız offline preview kullanılabilir, "
                        "normal soru modu için LLM ayarları gereklidir."
                    ),
                    "recommendation": (
                        "Offline preview (`python -m scripts.preview_question_ui`) için işlem gerekmez. "
                        "Normal mod (`uvicorn app.api.main:app`) için `.env` veya ortam değişkenlerinde "
                        "LLM_API_KEY, LLM_BASE_URL ve LLM_CHAT_MODEL tanımlayın."
                    ),
                }
            return {
                "status": "warning",
                "code": "llm_config_invalid",
                "configured": False,
                "provider_access_tested": False,
                "live_access_verified": False,
                "message": (
                    f"Yerel model ayarı geçersiz ({exc}) Offline preview kullanılabilir, "
                    "normal soru modu başlatılamaz."
                ),
                "recommendation": (
                    "LLM_API_KEY, LLM_BASE_URL (kimlik bilgisi/sorgu/fragment içermeyen HTTPS) "
                    "ve LLM_CHAT_MODEL ile LLM_TIMEOUT_SECONDS (0–120 sn) değerlerini kontrol edin."
                ),
            }

        return {
            "status": "ok",
            "code": "llm_configured_untested",
            "configured": True,
            "provider_access_tested": False,
            "live_access_verified": False,
            "message": "Ayar mevcut; sağlayıcı erişimi denenmedi (canlı erişim doğrulanmadı).",
            "recommendation": None,
        }
    finally:
        llm_client.load_dotenv = original_llm_load_dotenv
        os.environ.clear()
        os.environ.update(env_snapshot)


def run_diagnostics(
    *,
    cli_data_root: str | Path | None = None,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Run all offline checks without modifying environment, files, or network state."""
    env_snapshot = os.environ.copy()
    try:
        python_check = _check_python_version()
        deps_check = _check_dependencies()
        selected_root, root_source, root_message = resolve_data_root(
            cli_data_root, repo_root=repo_root,
        )
        data_root_check, data_package_check = _check_data_package(
            selected_root, root_source, root_message,
        )
        llm_check = _check_llm_configuration(repo_root=repo_root)
    finally:
        os.environ.clear()
        os.environ.update(env_snapshot)

    error_codes: list[str] = []
    warning_codes: list[str] = []
    for check in (python_check, deps_check, data_package_check, llm_check):
        if check["status"] == "error":
            error_codes.append(check["code"])
        elif check["status"] == "warning":
            warning_codes.append(check["code"])

    preview_ready = (
        python_check["status"] == "ok"
        and deps_check["status"] == "ok"
        and data_package_check["status"] == "ok"
    )
    normal_mode_configured = bool(llm_check["configured"])
    exit_code = 0 if preview_ready else 1
    overall_status = "ok" if exit_code == 0 else "error"

    return {
        "status": overall_status,
        "exit_code": exit_code,
        "preview_ready": preview_ready,
        "normal_mode_configured": normal_mode_configured,
        "normal_mode_ready": preview_ready and normal_mode_configured,
        "live_model_access_verified": False,
        "error_codes": error_codes,
        "warning_codes": warning_codes,
        "checks": {
            "python": python_check,
            "dependencies": deps_check,
            "data_root": data_root_check,
            "data_package": data_package_check,
            "llm_config": llm_check,
        },
    }


def format_human_report(report: dict[str, Any]) -> str:
    checks = report["checks"]
    lines = [
        "=== Yerel Kurulum ve Veri Paketi Teşhisi (Çevrimdışı) ===",
        f"1. Python ortamı [{checks['python']['code']}]: {checks['python']['message']}",
        f"2. Çalışma zamanı paketleri [{checks['dependencies']['code']}]: {checks['dependencies']['message']}",
        f"3. Veri kökü seçimi [{checks['data_root']['source']}]: {checks['data_root']['message']}",
        f"4. Fiziksel veri paketi [{checks['data_package']['code']}]: {checks['data_package']['message']}",
        f"5. Model (LLM) yapılandırması [{checks['llm_config']['code']}]: {checks['llm_config']['message']}",
        "",
        f"Offline preview hazır (preview_ready): {'Evet' if report['preview_ready'] else 'Hayır'}",
        (
            "Normal soru modu yapılandırıldı (normal_mode_configured): "
            f"{'Evet (Ayar mevcut; sağlayıcı erişimi denenmedi)' if report['normal_mode_configured'] else 'Hayır'}"
        ),
        "Canlı model erişimi doğrulandı (live_model_access_verified): Hayır (bu komut ağ çağrısı yapmaz)",
    ]

    recommendations = [
        check["recommendation"]
        for check in (
            checks["python"],
            checks["dependencies"],
            checks["data_package"],
            checks["llm_config"],
        )
        if check.get("recommendation")
    ]
    if recommendations:
        lines.append("")
        lines.append("Önerilen eylemler:")
        for rec in recommendations:
            lines.append(f"- {rec}")

    return "\n".join(lines)


def main(
    argv: Sequence[str] | None = None,
    *,
    repo_root: Path = REPO_ROOT,
) -> int:
    parser = argparse.ArgumentParser(
        description="Çevrimdışı yerel kurulum, bağımlılık, veri paketi ve model ayarı teşhis komutu.",
    )
    parser.add_argument(
        "--data-root",
        type=str,
        default=None,
        help="Doğrulanacak veri paketi kök dizini (`data/` klasörünü içeren dizin).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Teşhis sonucunu JSON nesnesi olarak yazdır.",
    )
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2

    report = run_diagnostics(cli_data_root=args.data_root, repo_root=repo_root)
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_human_report(report))
    return int(report["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
