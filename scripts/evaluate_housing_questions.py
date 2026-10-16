"""Evaluate the bounded Housing harness; live model calls require explicit opt-in."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.connectors.llm_client import LLMConfigurationError, ask_llm, read_llm_settings
from app.services.housing_analysis import run_housing_analysis
from app.services.housing_question import (
    HousingDataCoverage,
    HousingDecision,
    HousingPlanningError,
    HousingPlanValidationError,
    HousingReadyPlan,
    ModelCall,
    run_housing_question,
)


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "evals/housing_question_cases.json"
FIXTURE_PATH = ROOT / "docs/housing-api-example.json"


class QuestionCase(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(pattern=r"^HQ-[0-9]{3}$")
    question: str = Field(min_length=1, max_length=2_000)
    expected_decision: HousingDecision
    offline_response: dict[str, Any]
    expected_observed_month_count: int | None = Field(default=None, ge=1)
    expected_matched_periods: list[str] | None = None

    @model_validator(mode="after")
    def require_ready_expectations(self) -> QuestionCase:
        if not self.question.strip():
            raise ValueError("Case question must not be blank.")
        has_analysis = isinstance(self.expected_decision, HousingReadyPlan)
        if has_analysis != (self.expected_observed_month_count is not None):
            raise ValueError("Only ready cases must specify observation counts.")
        if has_analysis != (self.expected_matched_periods is not None):
            raise ValueError("Only ready cases must specify matching periods.")
        return self


class QuestionSuite(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["1.0"]
    cases: list[QuestionCase] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def unique_ids(self) -> QuestionSuite:
        if len({case.id for case in self.cases}) != len(self.cases):
            raise ValueError("Case IDs must be unique.")
        return self


def load_cases(path: Path = CASES_PATH) -> list[QuestionCase]:
    return QuestionSuite.model_validate_json(path.read_text(encoding="utf-8")).cases


def select_cases(cases: list[QuestionCase], ids: list[str] | None) -> list[QuestionCase]:
    if ids is None:
        return cases
    lookup = {case.id: case for case in cases}
    if not ids or len(ids) != len(set(ids)) or any(key not in lookup for key in ids):
        raise ValueError("Case selection must contain known, unique IDs.")
    return [lookup[key] for key in ids]


def evaluate_cases(
    cases: list[QuestionCase],
    payload: dict[str, Any],
    *,
    live: bool = False,
    model_call: ModelCall | None = None,
    max_model_calls: int | None = None,
    model_name: str | None = None,
) -> dict[str, Any]:
    if not cases:
        raise ValueError("At least one case is required.")
    if live:
        if not callable(model_call) or type(max_model_calls) is not int or max_model_calls < len(cases):
            raise ValueError("Live mode needs a callable and a budget covering selected cases.")
    elif model_call is not None or max_model_calls is not None:
        raise ValueError("Offline mode must not receive a live callable/budget.")

    bddk, evds = pd.DataFrame(payload["bddk_monthly"]), pd.DataFrame(payload["evds_monthly"])
    coverage = HousingDataCoverage(
        start_period=payload["start_period"], end_period=payload["end_period"],
    )
    refs = {name: payload[name] for name in ("bddk_source_ref", "evds_source_refs")}
    # Validate the fixture and all reference outputs before making any live call.
    full_reference = run_housing_analysis(
        bddk, evds, start_period=coverage.start_period, end_period=coverage.end_period, **refs,
    )
    references = {(coverage.start_period, coverage.end_period): full_reference}
    for case in cases:
        expected = case.expected_decision
        if isinstance(expected, HousingReadyPlan):
            if expected.start_period < coverage.start_period or expected.end_period > coverage.end_period:
                raise ValueError("Expected ready period must fit the synthetic fixture.")
            key = (expected.start_period, expected.end_period)
            if key not in references:
                references[key] = run_housing_analysis(
                    bddk, evds, start_period=key[0], end_period=key[1], **refs,
                )
            evidence = references[key].evidence
            if (
                evidence.observed_month_count != case.expected_observed_month_count
                or list(evidence.matched_periods) != case.expected_matched_periods
            ):
                raise ValueError("Case evidence expectations disagree with the fixture.")

    live_calls = stub_calls = 0
    stopped = False
    rows = []
    for case in cases:
        row = {
            "id": case.id, "question": case.question,
            "expected_decision": case.expected_decision.model_dump(),
            "actual_decision": None, "outcome": "skipped", "reason": None,
        }
        if stopped:
            row["reason"] = "not_run_after_model_call_failure"
            rows.append(row)
            continue

        def call(prompt: str) -> str:
            nonlocal live_calls, stub_calls
            if live:
                if live_calls >= max_model_calls:
                    raise RuntimeError("Call budget exhausted.")
                live_calls += 1
                return model_call(prompt)
            stub_calls += 1
            return json.dumps(case.offline_response, ensure_ascii=False)

        row["outcome"] = "failed"
        try:
            result = run_housing_question(
                case.question, bddk, evds, coverage=coverage, model_call=call, **refs,
            )
            row["actual_decision"] = result.decision.model_dump()
            if row["actual_decision"] != row["expected_decision"]:
                row["reason"] = "decision_mismatch"
            elif isinstance(case.expected_decision, HousingReadyPlan):
                expected = case.expected_decision
                reference = references[(expected.start_period, expected.end_period)]
                if result.analysis is None:
                    row["reason"] = "missing_analysis"
                elif result.analysis.evidence.model_dump() != reference.evidence.model_dump():
                    row["reason"] = "evidence_mismatch"
                elif result.analysis.chart != reference.chart:
                    row["reason"] = "chart_mismatch"
                elif result.analysis.narration is not None:
                    row["reason"] = "unexpected_narration"
                else:
                    row["outcome"] = "passed"
                    row["evidence_summary"] = {
                        "observed_month_count": result.analysis.evidence.observed_month_count,
                        "matched_periods": list(result.analysis.evidence.matched_periods),
                    }
            elif result.analysis is not None:
                row["reason"] = "unexpected_analysis"
            else:
                row["outcome"] = "passed"
        except HousingPlanningError:
            row["reason"] = "model_call_failed"
            stopped = live
        except HousingPlanValidationError:
            row["reason"] = "invalid_plan"
        except Exception:
            row["reason"] = "evaluation_error"
            stopped = live
        rows.append(row)

    passed = sum(row["outcome"] == "passed" for row in rows)
    failed = sum(row["outcome"] == "failed" for row in rows)
    skipped = sum(row["outcome"] == "skipped" for row in rows)
    return {
        "schema_version": "1.0",
        "mode": "live_model" if live else "offline_stub",
        "measurement": "selected_live_cases" if live else "harness_behavior_only",
        "synthetic_data": True,
        "model": model_name if live else None,
        "selected_cases": len(rows), "executed_cases": passed + failed,
        "passed_cases": passed, "failed_cases": failed, "skipped_cases": skipped,
        "live_model_call_attempts": live_calls, "stub_calls": stub_calls,
        "all_selected_cases_passed": failed == 0 and skipped == 0,
        "results": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sınırlı Housing soru değerlendirmesi")
    parser.add_argument("--live", action="store_true", help="Yerel LLM ayarlarıyla canlı planlama")
    parser.add_argument("--case", action="append", dest="case_ids", help="Tekrarlanabilir vaka seçimi")
    parser.add_argument("--max-model-calls", type=int, help="Canlı çağrı denemesi bütçesi")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        case_bytes = CASES_PATH.read_bytes()
        cases = select_cases(QuestionSuite.model_validate_json(case_bytes).cases, args.case_ids)
        if args.live:
            if args.max_model_calls is None or args.max_model_calls < len(cases):
                parser.error("--live için --max-model-calls, seçilen vaka sayısını karşılamalıdır.")
        elif args.max_model_calls is not None:
            parser.error("--max-model-calls yalnızca --live ile kullanılır.")
        output = args.output or ROOT / "out" / f"housing-question-eval-{'live' if args.live else 'offline'}.json"
        if output.resolve() in {CASES_PATH.resolve(), FIXTURE_PATH.resolve()}:
            parser.error("Rapor, vaka veya veri girdisinin üzerine yazılamaz.")
        if output.exists() and not output.is_file():
            parser.error("Rapor yolu bir dosya olmalıdır.")
        output.parent.mkdir(parents=True, exist_ok=True)
        fixture_bytes = FIXTURE_PATH.read_bytes()
        payload = json.loads(fixture_bytes)
        model_name = None
        if args.live:
            settings = read_llm_settings()
            model_name = settings.chat_model.replace(settings.api_key, "[REDACTED]")
        report = evaluate_cases(
            cases, payload, live=args.live, model_call=ask_llm if args.live else None,
            max_model_calls=args.max_model_calls, model_name=model_name,
        )
        report["case_set_sha256"] = hashlib.sha256(case_bytes).hexdigest()
        report["fixture_sha256"] = hashlib.sha256(fixture_bytes).hexdigest()
    except LLMConfigurationError as exc:
        print(f"Yapılandırma hatası: {exc}")
        return 2
    except (OSError, ValueError, KeyError):
        print("Değerlendirme girdileri veya rapor konumu geçersiz.")
        return 2

    print(f"Mod: {report['mode']} / {report['measurement']}")
    for row in report["results"]:
        print(f"{row['id']}: {row['outcome']} ({row['reason'] or 'ok'})")
    print(
        f"Seçilen={report['selected_cases']}, çalıştırılan={report['executed_cases']}, "
        f"geçen={report['passed_cases']}, başarısız={report['failed_cases']}, "
        f"atlanan={report['skipped_cases']}, canlı çağrı denemesi={report['live_model_call_attempts']}"
    )
    try:
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError:
        print("Değerlendirme tamamlandı ancak rapor yazılamadı.")
        return 1
    print(f"Rapor: {output}")
    return 0 if report["all_selected_cases_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
