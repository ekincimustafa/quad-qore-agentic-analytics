import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from app.connectors.bddk import extract_housing_loan_data


def verify_samples(silver_path: Path, periods: List[str], receipts_dir: Path, raw_dir: Path) -> int:
    if len(periods) < 3:
        print(f"[FAIL] En az 3 donem belirtilmelidir. Verilen: {len(periods)}")
        return 1

    if not silver_path.exists():
        print(f"[FAIL] Silver dosyasi bulunamadi: {silver_path}")
        return 1

    try:
        df = pd.read_parquet(silver_path)
    except Exception as e:
        print(f"[FAIL] Silver dosyasi okunamadi: {e}")
        return 1

    # Load all receipts to map request_key -> receipt
    receipts_map: Dict[str, Dict[str, Any]] = {}
    if receipts_dir.exists():
        for r_path in receipts_dir.glob("*.json"):
            try:
                data = json.loads(r_path.read_text(encoding="utf-8"))
                rk = data.get("request_key")
                if rk:
                    # In case of duplicate request_keys, take the latest downloaded_at
                    ts = data.get("downloaded_at", "")
                    if rk not in receipts_map or ts > receipts_map[rk].get("downloaded_at", ""):
                        receipts_map[rk] = data
            except Exception:
                pass

    all_passed = True
    print(f"{'Donem':<10} {'Silver mn TL':>15} {'Raw mn TL':>15} {'Durum':>15}")
    print("-" * 58)

    for p in periods:
        row = df[df["period"] == p]
        if row.empty:
            print(f"{p:<10} {'-':>15} {'-':>15} {'Eksik/Silver':>15}")
            all_passed = False
            continue

        if len(row) > 1:
            print(f"{p:<10} {'-':>15} {'-':>15} {'Tekrar/Silver':>15}")
            all_passed = False
            continue

        row_dict = row.iloc[0].to_dict()
        silver_val = row_dict["nominal_housing_loan_mn_try"]
        source_ref = row_dict["bddk_source_ref"]

        receipt = receipts_map.get(source_ref)
        if not receipt:
            print(f"{p:<10} {silver_val:>15,.0f} {'-':>15} {'Eksik/Makbuz':>15}")
            all_passed = False
            continue

        rel_path = receipt.get("path")
        if not rel_path:
            print(f"{p:<10} {silver_val:>15,.0f} {'-':>15} {'Eksik/Yol':>15}")
            all_passed = False
            continue

        raw_file_path = (raw_dir.parent.parent / rel_path).resolve()

        if not raw_file_path.exists():
            print(f"{p:<10} {silver_val:>15,.0f} {'-':>15} {'Eksik/Raw':>15}")
            all_passed = False
            continue

        raw_bytes = raw_file_path.read_bytes()
        actual_sha = hashlib.sha256(raw_bytes).hexdigest()
        expected_sha = receipt.get("sha256", "").lower()
        if actual_sha != expected_sha:
            print(f"{p:<10} {silver_val:>15,.0f} {'-':>15} {'Hash Uyumsuz':>15}")
            all_passed = False
            continue

        # Donem uyuşmazligi (receipt parameters.ay/yil ile p eslesmiyor)
        params = receipt.get("parameters")
        if params:
            y, m = int(params.get("yil", 0)), int(params.get("ay", 0))
            if f"{y:04d}-{m:02d}" != p:
                print(f"{p:<10} {silver_val:>15,.0f} {'-':>15} {'Donem Uyumsuz':>15}")
                all_passed = False
                continue

        # Unit check on Silver row
        silver_unit = row_dict.get("housing_loan_unit")
        if silver_unit != "Milyon TL":
            print(f"{p:<10} {silver_val:>15,.0f} {'-':>15} {'Silver Birim Hata':>15}")
            all_passed = False
            continue

        try:
            raw_payload = json.loads(raw_bytes.decode("utf-8"))
            parsed = extract_housing_loan_data(raw_payload)
            raw_val = parsed["toplam"]
            caption = parsed.get("caption", "")
        except Exception:
            print(f"{p:<10} {silver_val:>15,.0f} {'-':>15} {'Parse Hata':>15}")
            all_passed = False
            continue

        # Unit check on raw payload caption
        if "milyon tl" not in caption.lower():
            print(f"{p:<10} {silver_val:>15,.0f} {'-':>15} {'Ham Birim Hata':>15}")
            all_passed = False
            continue

        # Period check on raw payload caption (e.g. 'Dönem:2023/6')
        caption_match = re.search(r"Dönem:\s*(\d{4})/(\d{1,2})(?!\d)", caption, re.IGNORECASE)
        if not caption_match:
            print(f"{p:<10} {silver_val:>15,.0f} {'-':>15} {'Baslik Donem Yok':>15}")
            all_passed = False
            continue

        c_y, c_m = int(caption_match.group(1)), int(caption_match.group(2))
        caption_period = f"{c_y:04d}-{c_m:02d}"
        if caption_period != p:
            print(f"{p:<10} {silver_val:>15,.0f} {'-':>15} {'Baslik Uyumsuz':>15}")
            all_passed = False
            continue

        # Check numeric equality
        if not math.isclose(silver_val, raw_val):
            print(f"{p:<10} {silver_val:>15,.0f} {raw_val:>15,.0f} {'Farkli':>15}")
            all_passed = False
            continue

        print(f"{p:<10} {silver_val:>15,.0f} {raw_val:>15,.0f} {'TAM Eşleşme':>15}")

    print("-" * 58)
    if all_passed:
        print("[SUCCESS] Tum ornek aylar Silver ve Bronze ham verisiyle tam eslesti.")
        return 0
    else:
        print("[FAIL] Bazi aylar eslesmedi veya bulunamadi.")
        return 1

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--silver", type=str, required=True, help="Silver parquet path")
    parser.add_argument("--periods", nargs="+", required=True, help="Periods to check, e.g., 2021-01 2023-06 2025-12")
    args = parser.parse_args()

    sys.exit(verify_samples(
        silver_path=Path(args.silver),
        periods=args.periods,
        receipts_dir=Path("data/bronze/bddk/aylik/receipts"),
        raw_dir=Path("data/bronze/bddk/aylik/raw")
    ))

if __name__ == "__main__":
    main()
