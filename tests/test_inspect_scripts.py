from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from scripts.bddk.inspect_bronze import generate_expected_months as gen_bronze_months, main as bronze_main
from scripts.bddk.inspect_weekly_daily import (
    generate_expected_months as gen_weekly_months,
    inspect_haftalik,
)


def _make_bronze_raw_content() -> bytes:
    return json.dumps({
        "Json": {
            "caption": "Krediler (milyon TL)",
            "colModels": [
                {"name": "ad"},
                {"name": "tp"},
                {"name": "yp"},
                {"name": "toplam"},
            ],
            "data": {
                "rows": [
                    {"cell": ["Tüketici Kredileri - Konut", 1000.0, 0.0, 1000.0]}
                ]
            },
        }
    }, ensure_ascii=False).encode("utf-8")


class InspectScriptsTests(unittest.TestCase):
    def test_inspect_bronze_deduplicates_refreshed_receipts(self):
        """Test that refreshed/duplicate receipts are deduplicated taking latest downloaded_at."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            receipts_dir = base / "receipts"
            raw_dir = base / "raw"
            receipts_dir.mkdir()
            raw_dir.mkdir()

            raw_bytes = _make_bronze_raw_content()
            raw_file = raw_dir / "valid_raw.json"
            raw_file.write_bytes(raw_bytes)

            expected_months = gen_bronze_months(2021, 1, 2026, 7)

            for y, m in expected_months:
                rec = {
                    "request_key": f"tablo4_10001_TL_{y}_{m}",
                    "downloaded_at": "2026-09-11T12:00:00",
                    "parameters": {
                        "tabloNo": "4",
                        "taraf": ["10001"],
                        "paraBirimi": "TL",
                        "yil": y,
                        "ay": m,
                    },
                    "validation": {
                        "rows": 41,
                        "period_confirmation": "response_caption",
                    },
                    "path": "valid_raw.json",
                    "size_bytes": len(raw_bytes),
                }
                (receipts_dir / f"receipt_{y}_{m:02d}.json").write_text(
                    json.dumps(rec), encoding="utf-8"
                )

            # Add older duplicate receipt for 2021-01 pointing to a broken raw file
            # If deduplication fails, this would cause verification failure.
            dup_rec = {
                "request_key": "tablo4_10001_TL_2021_1",
                "downloaded_at": "2026-01-01T00:00:00",  # Older timestamp
                "parameters": {
                    "tabloNo": "4",
                    "taraf": ["10001"],
                    "paraBirimi": "TL",
                    "yil": 2021,
                    "ay": 1,
                },
                "validation": {
                    "rows": 41,
                    "period_confirmation": "response_caption",
                },
                "path": "non_existent.json",
                "size_bytes": 99999,
            }
            (receipts_dir / "receipt_2021_01_old_refresh.json").write_text(
                json.dumps(dup_rec), encoding="utf-8"
            )

            # Total receipt files = 68, but unique periods = 67
            self.assertEqual(len(list(receipts_dir.glob("*.json"))), 68)

            buf = io.StringIO()
            with redirect_stdout(buf):
                exit_code = bronze_main(receipts_dir=receipts_dir, raw_dir=raw_dir)

            self.assertEqual(exit_code, 0)
            output = buf.getvalue()
            self.assertIn("1 eski/refresh makbuz elendi", output)
            self.assertIn("[BASARILI] Tum 67 donem eksiksiz", output)

    def test_inspect_bronze_fails_on_corrupt_receipt(self):
        """Test that corrupt JSON in receipt directory causes inspect_bronze to fail."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            receipts_dir = base / "receipts"
            raw_dir = base / "raw"
            receipts_dir.mkdir()
            raw_dir.mkdir()

            (receipts_dir / "corrupt.json").write_text("{corrupt: true", encoding="utf-8")

            buf = io.StringIO()
            with redirect_stdout(buf):
                exit_code = bronze_main(receipts_dir=receipts_dir, raw_dir=raw_dir)

            self.assertEqual(exit_code, 1)
            self.assertIn("bozuk JSON iceriyor", buf.getvalue())

    def test_inspect_bronze_fails_on_missing_month(self):
        """Test that missing period in expected range causes inspect_bronze to fail."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            receipts_dir = base / "receipts"
            raw_dir = base / "raw"
            receipts_dir.mkdir()
            raw_dir.mkdir()

            raw_bytes = _make_bronze_raw_content()
            raw_file = raw_dir / "valid_raw.json"
            raw_file.write_bytes(raw_bytes)

            expected_months = gen_bronze_months(2021, 1, 2026, 7)

            # Skip 2023-06
            for y, m in expected_months:
                if y == 2023 and m == 6:
                    continue
                rec = {
                    "request_key": f"tablo4_10001_TL_{y}_{m}",
                    "downloaded_at": "2026-09-11T12:00:00",
                    "parameters": {
                        "tabloNo": "4",
                        "taraf": ["10001"],
                        "paraBirimi": "TL",
                        "yil": y,
                        "ay": m,
                    },
                    "validation": {
                        "rows": 41,
                        "period_confirmation": "response_caption",
                    },
                    "path": "valid_raw.json",
                    "size_bytes": len(raw_bytes),
                }
                (receipts_dir / f"receipt_{y}_{m:02d}.json").write_text(
                    json.dumps(rec), encoding="utf-8"
                )

            buf = io.StringIO()
            with redirect_stdout(buf):
                exit_code = bronze_main(receipts_dir=receipts_dir, raw_dir=raw_dir)

            self.assertEqual(exit_code, 1)
            self.assertIn("EKSIK DONEMLER (1 adet): [(2023, 6)]", buf.getvalue())

    def test_inspect_bronze_fails_on_missing_raw_file_or_size_mismatch(self):
        """Test that missing physical file or size mismatch causes inspect_bronze to fail."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            receipts_dir = base / "receipts"
            raw_dir = base / "raw"
            receipts_dir.mkdir()
            raw_dir.mkdir()

            raw_bytes = _make_bronze_raw_content()
            raw_file = raw_dir / "valid_raw.json"
            raw_file.write_bytes(raw_bytes)

            expected_months = gen_bronze_months(2021, 1, 2026, 7)

            for y, m in expected_months:
                # Deliberate size mismatch on 2022-04
                size = len(raw_bytes) + 100 if (y == 2022 and m == 4) else len(raw_bytes)
                rec = {
                    "request_key": f"tablo4_10001_TL_{y}_{m}",
                    "downloaded_at": "2026-09-11T12:00:00",
                    "parameters": {
                        "tabloNo": "4",
                        "taraf": ["10001"],
                        "paraBirimi": "TL",
                        "yil": y,
                        "ay": m,
                    },
                    "validation": {
                        "rows": 41,
                        "period_confirmation": "response_caption",
                    },
                    "path": "valid_raw.json",
                    "size_bytes": size,
                }
                (receipts_dir / f"receipt_{y}_{m:02d}.json").write_text(
                    json.dumps(rec), encoding="utf-8"
                )

            buf = io.StringIO()
            with redirect_stdout(buf):
                exit_code = bronze_main(receipts_dir=receipts_dir, raw_dir=raw_dir)

            self.assertEqual(exit_code, 1)
            self.assertIn("Boyut uyusmazligi", buf.getvalue())

    def test_inspect_weekly_fails_when_kalem_5690_missing_months(self):
        """Test that inspect_haftalik fails when Kalem 5690 is missing from specific months."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            receipts_dir = base / "receipts"
            raw_dir = base / "raw"
            receipts_dir.mkdir()
            raw_dir.mkdir()

            html_content = b"<html><table><tr><td>01.01.2021</td><td>100</td></tr></table></html>"
            html_file = raw_dir / "sample.html"
            html_file.write_bytes(html_content)

            expected_months = gen_weekly_months(2021, 1, 2026, 7)

            for month_str in expected_months:
                y, m = map(int, month_str.split("-"))
                # Omit Kalem 5690 in 2023-05 and 2024-08
                kalemler = ["1234"] if month_str in {"2023-05", "2024-08"} else ["5690"]
                rec = {
                    "request_key": f"haftalik_{y}_{m}",
                    "downloaded_at": "2026-09-11T12:00:00",
                    "parameters": {
                        "BaslangicTarihi": f"01.{m:02d}.{y}",
                        "Kalemler": kalemler,
                        "SeciliParalar": "TL",
                        "Taraflar": ["10001"],
                    },
                    "validation": {"data_rows": 5},
                    "path": "sample.html",
                    "size_bytes": len(html_content),
                }
                (receipts_dir / f"receipt_{month_str}.json").write_text(
                    json.dumps(rec), encoding="utf-8"
                )

            buf = io.StringIO()
            with redirect_stdout(buf):
                res = inspect_haftalik(receipts_dir=receipts_dir, raw_dir=raw_dir)

            self.assertFalse(res["is_valid"])
            self.assertEqual(res["covered_months_5690"], 65)
            self.assertIn("2023-05", res["eksik_5690_aylar"])
            self.assertIn("2024-08", res["eksik_5690_aylar"])

    def test_inspect_weekly_fails_on_missing_raw_file_or_size_mismatch(self):
        """Test that inspect_haftalik fails when physical HTML file is missing or size differs."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            receipts_dir = base / "receipts"
            raw_dir = base / "raw"
            receipts_dir.mkdir()
            raw_dir.mkdir()

            html_content = b"<html><table><tr><td>01.01.2021</td><td>100</td></tr></table></html>"
            html_file = raw_dir / "sample.html"
            html_file.write_bytes(html_content)

            expected_months = gen_weekly_months(2021, 1, 2026, 7)

            for month_str in expected_months:
                y, m = map(int, month_str.split("-"))
                rec = {
                    "request_key": f"haftalik_{y}_{m}",
                    "downloaded_at": "2026-09-11T12:00:00",
                    "parameters": {
                        "BaslangicTarihi": f"01.{m:02d}.{y}",
                        "Kalemler": ["5690"],
                        "SeciliParalar": "TL",
                        "Taraflar": ["10001"],
                    },
                    "validation": {"data_rows": 5},
                    # Month 2022-01 points to missing file
                    "path": "missing.html" if month_str == "2022-01" else "sample.html",
                    "size_bytes": len(html_content),
                }
                (receipts_dir / f"receipt_{month_str}.json").write_text(
                    json.dumps(rec), encoding="utf-8"
                )

            buf = io.StringIO()
            with redirect_stdout(buf):
                res = inspect_haftalik(receipts_dir=receipts_dir, raw_dir=raw_dir)

            self.assertFalse(res["is_valid"])
            self.assertEqual(res["missing_files_count"], 1)

    def test_inspect_weekly_fails_on_corrupt_receipt(self):
        """Test that corrupt JSON file causes inspect_haftalik to fail."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            receipts_dir = base / "receipts"
            raw_dir = base / "raw"
            receipts_dir.mkdir()
            raw_dir.mkdir()

            (receipts_dir / "broken.json").write_text("{not: valid", encoding="utf-8")

            buf = io.StringIO()
            with redirect_stdout(buf):
                res = inspect_haftalik(receipts_dir=receipts_dir, raw_dir=raw_dir)

            self.assertFalse(res["is_valid"])


if __name__ == "__main__":
    unittest.main()
