"""Optional live Housing narration check using a small synthetic fixture."""

import json
from pathlib import Path

import pandas as pd

from app.connectors.llm_client import LLMConfigurationError, LLMRequestError
from app.services.housing_analysis import HousingNarrationError, run_housing_analysis
from app.tools.housing_narrator import narrate_housing_evidence_with_llm


def main() -> None:
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
    main()
