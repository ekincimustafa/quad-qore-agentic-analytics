from __future__ import annotations

import hashlib
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
    inspect_gunluk,
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
                    "sha256": hashlib.sha256(raw_bytes).hexdigest(),
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
                    "sha256": hashlib.sha256(raw_bytes).hexdigest(),
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
                    "sha256": hashlib.sha256(raw_bytes).hexdigest(),
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

            expected_months = gen_weekly_months(2021, 1, 2026, 7)

            for month_str in expected_months:
                y, m = map(int, month_str.split("-"))
                html_content = _make_weekly_html_with_konut(f"01.{m:02d}.{y}")
                html_file = raw_dir / f"sample_{month_str}.html"
                html_file.write_bytes(html_content)
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
                    "path": f"sample_{month_str}.html",
                    "size_bytes": len(html_content),
                    "sha256": hashlib.sha256(html_content).hexdigest(),
                }
                (receipts_dir / f"receipt_{month_str}.json").write_text(
                    json.dumps(rec), encoding="utf-8"
                )

            buf = io.StringIO()
            with redirect_stdout(buf):
                res = inspect_haftalik(receipts_dir=receipts_dir, raw_dir=raw_dir)

            self.assertFalse(res["is_valid"])
            self.assertEqual(res["covered_months_5690_request"], 65)
            self.assertEqual(res["covered_months_5690_html"], 65)
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

            expected_months = gen_weekly_months(2021, 1, 2026, 7)

            for month_str in expected_months:
                y, m = map(int, month_str.split("-"))
                html_content = _make_weekly_html_with_konut(f"01.{m:02d}.{y}")
                html_file = raw_dir / f"sample_{month_str}.html"
                html_file.write_bytes(html_content)
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
                    "path": "missing.html" if month_str == "2022-01" else f"sample_{month_str}.html",
                    "size_bytes": len(html_content),
                    "sha256": hashlib.sha256(html_content).hexdigest(),
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


# ---------------------------------------------------------------------------
# HTML helper'lari — haftalik SHA-256 ve 5690 HTML icerik testleri icin
# ---------------------------------------------------------------------------

def _make_weekly_html_with_konut(date_str: str = "01.01.2021") -> bytes:
    """Minimal gecerli haftalik HTML: TabloExcelGelismis tablosunda Konut sutunu + sayisal deger."""
    return (
        "<html><body>"
        '<table id="TabloExcelGelismis">'
        "<tr></tr>"
        "<tr>"
        "<td></td>"
        "<td>Krediler / a) Konut</td>"
        "<td></td>"
        "<td></td>"
        "</tr>"
        "<tr><td></td><td>TP</td><td>YP</td><td>TOPLAM</td></tr>"
        "<tr><td>Sektor</td></tr>"
        f"<tr><td>{date_str}</td><td>100,00</td><td>5,00</td><td>105,00</td></tr>"
        "</table>"
        "</body></html>"
    ).encode("utf-8")


def _make_weekly_html_without_konut(date_str: str = "01.01.2021") -> bytes:
    """Minimal haftalik HTML: TabloExcelGelismis var ama Konut sutunu YOK."""
    return (
        "<html><body>"
        '<table id="TabloExcelGelismis">'
        "<tr></tr>"
        "<tr>"
        "<td></td>"
        "<td>Krediler / Toplam Krediler</td>"
        "<td></td>"
        "<td></td>"
        "</tr>"
        "<tr><td></td><td>TP</td><td>YP</td><td>TOPLAM</td></tr>"
        "<tr><td>Sektor</td></tr>"
        f"<tr><td>{date_str}</td><td>999,00</td><td>0,00</td><td>999,00</td></tr>"
        "</table>"
        "</body></html>"
    ).encode("utf-8")


class SHA256AndHtmlTests(unittest.TestCase):
    # -------------------------------------------------------------------
    # Aylik SHA-256 testleri
    # -------------------------------------------------------------------

    def test_inspect_bronze_fails_on_sha256_mismatch(self):
        """inspect_bronze exit 1 vermeli: makbuzdaki sha256 gercek dosya hash'inden farkli."""
        import hashlib

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
                is_bad = y == 2024 and m == 3
                # Dogru hash veya kasitli bozuk hash
                sha = (
                    "0" * 64 if is_bad
                    else hashlib.sha256(raw_bytes).hexdigest()
                )
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
                    "sha256": sha,
                }
                (receipts_dir / f"receipt_{y}_{m:02d}.json").write_text(
                    json.dumps(rec), encoding="utf-8"
                )

            buf = io.StringIO()
            with redirect_stdout(buf):
                exit_code = bronze_main(receipts_dir=receipts_dir, raw_dir=raw_dir)

            self.assertEqual(exit_code, 1)
            self.assertIn("SHA-256 uyusmazligi", buf.getvalue())

    def test_inspect_bronze_passes_with_correct_sha256(self):
        """inspect_bronze exit 0 vermeli: tum 67 ay icin SHA-256 dogru."""
        import hashlib

        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            receipts_dir = base / "receipts"
            raw_dir = base / "raw"
            receipts_dir.mkdir()
            raw_dir.mkdir()

            raw_bytes = _make_bronze_raw_content()
            raw_file = raw_dir / "valid_raw.json"
            raw_file.write_bytes(raw_bytes)
            correct_sha = hashlib.sha256(raw_bytes).hexdigest()

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
                    "sha256": correct_sha,
                }
                (receipts_dir / f"receipt_{y}_{m:02d}.json").write_text(
                    json.dumps(rec), encoding="utf-8"
                )

            buf = io.StringIO()
            with redirect_stdout(buf):
                exit_code = bronze_main(receipts_dir=receipts_dir, raw_dir=raw_dir)

            self.assertEqual(exit_code, 0)
            self.assertIn("[BASARILI] Tum 67 donem eksiksiz", buf.getvalue())

    # -------------------------------------------------------------------
    # Haftalik SHA-256 testi
    # -------------------------------------------------------------------

    def test_inspect_weekly_fails_on_sha256_mismatch(self):
        """inspect_haftalik is_valid=False olmali: makbuzdaki sha256 yanlis."""
        import hashlib

        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            receipts_dir = base / "receipts"
            raw_dir = base / "raw"
            receipts_dir.mkdir()
            raw_dir.mkdir()

            expected_months = gen_weekly_months(2021, 1, 2026, 7)

            for month_str in expected_months:
                y, m = map(int, month_str.split("-"))
                html_content = _make_weekly_html_with_konut(f"01.{m:02d}.{y}")
                html_file = raw_dir / f"sample_{month_str}.html"
                html_file.write_bytes(html_content)
                correct_sha = hashlib.sha256(html_content).hexdigest()
                is_bad = month_str == "2025-06"
                rec = {
                    "request_key": f"haftalik_{y}_{m}",
                    "downloaded_at": "2026-09-11T12:00:00",
                    "parameters": {
                        "BaslangicTarihi": f"01.{m:02d}.{y}",
                        "Kalemler": ["5690"],
                        "SeciliParalar": "TL",
                        "Taraflar": ["10001"],
                    },
                    "validation": {"data_rows": 1},
                    "path": f"sample_{month_str}.html",
                    "size_bytes": len(html_content),
                    "sha256": "0" * 64 if is_bad else correct_sha,
                }
                (receipts_dir / f"receipt_{month_str}.json").write_text(
                    json.dumps(rec), encoding="utf-8"
                )

            buf = io.StringIO()
            with redirect_stdout(buf):
                res = inspect_haftalik(receipts_dir=receipts_dir, raw_dir=raw_dir)

            self.assertFalse(res["is_valid"])
            self.assertEqual(res["hash_mismatches_count"], 1)
            self.assertEqual(res["covered_months_5690_request"], 67)
            self.assertEqual(res["covered_months_5690_html"], 66)
            self.assertIn("2025-06", res["eksik_5690_aylar"])
            self.assertIn("SHA-256 uyusmazligi", buf.getvalue())

    # -------------------------------------------------------------------
    # 5690 istek vs HTML icerik ayrimi testi
    # -------------------------------------------------------------------

    def test_inspect_weekly_fails_when_5690_in_request_but_not_in_html(self):
        """5690 istekte var ama HTML'de Konut sutunu yoksa HTML seti bos -> is_valid=False."""
        import hashlib

        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            receipts_dir = base / "receipts"
            raw_dir = base / "raw"
            receipts_dir.mkdir()
            raw_dir.mkdir()

            # Tum aylar icin: 5690 istekte var, ama HTML'de Konut sutunu yok
            html_no_konut = _make_weekly_html_without_konut()
            html_file = raw_dir / "no_konut.html"
            html_file.write_bytes(html_no_konut)
            sha_no_konut = hashlib.sha256(html_no_konut).hexdigest()

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
                    "validation": {"data_rows": 1},
                    "path": "no_konut.html",
                    "size_bytes": len(html_no_konut),
                    "sha256": sha_no_konut,
                }
                (receipts_dir / f"receipt_{month_str}.json").write_text(
                    json.dumps(rec), encoding="utf-8"
                )

            buf = io.StringIO()
            with redirect_stdout(buf):
                res = inspect_haftalik(receipts_dir=receipts_dir, raw_dir=raw_dir)

            # 5690 tum aylarda istekte mevcut, ama HTML'de sifir ay dogrulandi
            self.assertEqual(res["covered_months_5690_request"], 67)
            self.assertEqual(res["covered_months_5690_html"], 0)
            # HTML dogrulama baskisi nedeniyle is_valid=False
            self.assertFalse(res["is_valid"])
            output = buf.getvalue()
            self.assertIn("[OK] Kalem 5690 istekte tum 67 ay icin mevcut.", output)
            self.assertIn("HTML icerigi dogrulanamayan", output)

    def test_inspect_weekly_passes_when_all_valid(self):
        """inspect_haftalik is_valid=True olmali: tum 67 ay icin SHA-256 ve donemle eslesen Konut HTML icerigi dogru."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            receipts_dir = base / "receipts"
            raw_dir = base / "raw"
            receipts_dir.mkdir()
            raw_dir.mkdir()

            expected_months = gen_weekly_months(2021, 1, 2026, 7)

            for month_str in expected_months:
                y, m = map(int, month_str.split("-"))
                html_content = _make_weekly_html_with_konut(f"01.{m:02d}.{y}")
                html_file = raw_dir / f"sample_{month_str}.html"
                html_file.write_bytes(html_content)
                correct_sha = hashlib.sha256(html_content).hexdigest()

                rec = {
                    "request_key": f"haftalik_{y}_{m}",
                    "downloaded_at": "2026-09-11T12:00:00",
                    "parameters": {
                        "BaslangicTarihi": f"01.{m:02d}.{y}",
                        "Kalemler": ["5690"],
                        "SeciliParalar": "TL",
                        "Taraflar": ["10001"],
                    },
                    "validation": {"data_rows": 1},
                    "path": f"sample_{month_str}.html",
                    "size_bytes": len(html_content),
                    "sha256": correct_sha,
                }
                (receipts_dir / f"receipt_{month_str}.json").write_text(
                    json.dumps(rec), encoding="utf-8"
                )

            buf = io.StringIO()
            with redirect_stdout(buf):
                res = inspect_haftalik(receipts_dir=receipts_dir, raw_dir=raw_dir)

            self.assertTrue(res["is_valid"])
            self.assertEqual(res["hash_mismatches_count"], 0)
            self.assertEqual(res["missing_files_count"], 0)
            self.assertEqual(res["size_mismatches_count"], 0)
            self.assertEqual(res["covered_months_5690_request"], 67)
            self.assertEqual(res["covered_months_5690_html"], 67)
            self.assertEqual(len(res["eksik_5690_aylar"]), 0)
            self.assertIn("[OK] Kalem 5690 tum 67 ay icin HTML'de kullanilabilir veri dogrulandi.", buf.getvalue())

    def test_inspect_weekly_fails_when_html_date_mismatches_request_period(self):
        """Istek donemi ile HTML icindeki tarih uyusmazsa o ay HTML kumesine eklenmemeli ve fail olmali."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            receipts_dir = base / "receipts"
            raw_dir = base / "raw"
            receipts_dir.mkdir()
            raw_dir.mkdir()

            expected_months = gen_weekly_months(2021, 1, 2026, 7)

            for month_str in expected_months:
                y, m = map(int, month_str.split("-"))
                # 2023-05 icin HTML dosyasina bilerek yanlis ay (01.01.2021) veriyoruz
                if month_str == "2023-05":
                    html_content = _make_weekly_html_with_konut("01.01.2021")
                else:
                    html_content = _make_weekly_html_with_konut(f"01.{m:02d}.{y}")
                html_file = raw_dir / f"sample_{month_str}.html"
                html_file.write_bytes(html_content)
                correct_sha = hashlib.sha256(html_content).hexdigest()

                rec = {
                    "request_key": f"haftalik_{y}_{m}",
                    "downloaded_at": "2026-09-11T12:00:00",
                    "parameters": {
                        "BaslangicTarihi": f"01.{m:02d}.{y}",
                        "Kalemler": ["5690"],
                        "SeciliParalar": "TL",
                        "Taraflar": ["10001"],
                    },
                    "validation": {"data_rows": 1},
                    "path": f"sample_{month_str}.html",
                    "size_bytes": len(html_content),
                    "sha256": correct_sha,
                }
                (receipts_dir / f"receipt_{month_str}.json").write_text(
                    json.dumps(rec), encoding="utf-8"
                )

            buf = io.StringIO()
            with redirect_stdout(buf):
                res = inspect_haftalik(receipts_dir=receipts_dir, raw_dir=raw_dir)

            self.assertFalse(res["is_valid"])
            self.assertEqual(res["covered_months_5690_request"], 67)
            self.assertEqual(res["covered_months_5690_html"], 66)
            self.assertIn("2023-05", res["eksik_5690_aylar"])
            self.assertIn("HTML icerigi dogrulanamayan aylar (1 adet)", buf.getvalue())

    def test_inspect_bronze_skips_corrupted_file_on_sha256_mismatch(self):
        """Bozuk dosyada SHA-256 uyusmazligi tespit edilince continue ile parse atlanmali."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            receipts_dir = base / "receipts"
            raw_dir = base / "raw"
            receipts_dir.mkdir()
            raw_dir.mkdir()

            valid_bytes = _make_bronze_raw_content()
            (raw_dir / "valid_raw.json").write_bytes(valid_bytes)
            valid_sha = hashlib.sha256(valid_bytes).hexdigest()

            # Bozuk dosya: JSON bile degil
            corrupt_bytes = b"CORRUPTED_NON_JSON_CONTENT"
            (raw_dir / "corrupt_raw.json").write_bytes(corrupt_bytes)

            expected_months = gen_bronze_months(2021, 1, 2026, 7)

            for y, m in expected_months:
                is_bad = (y == 2023 and m == 5)
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
                    "path": "corrupt_raw.json" if is_bad else "valid_raw.json",
                    "size_bytes": len(corrupt_bytes) if is_bad else len(valid_bytes),
                    # Makbuzda gecerli sha bekleniyor ama diskteki dosya bozuk
                    "sha256": valid_sha,
                }
                (receipts_dir / f"receipt_{y}_{m:02d}.json").write_text(
                    json.dumps(rec), encoding="utf-8"
                )

            buf = io.StringIO()
            with redirect_stdout(buf):
                exit_code = bronze_main(receipts_dir=receipts_dir, raw_dir=raw_dir)

            self.assertEqual(exit_code, 1)
            output = buf.getvalue()
            # SHA-256 hatasi yakalanmali
            self.assertIn("SHA-256 uyusmazligi", output)
            # Bozuk dosya parse'a sokulmadigi icin JSONDecodeError veya extract hatasi olmamali
            self.assertNotIn("JSONDecodeError", output)
            self.assertNotIn("Expecting value", output)

    def test_inspect_weekly_fails_on_html_parse_error(self):
        """inspect_haftalik is_valid=False olmali: Page parser exception firlatirsa."""
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            receipts_dir = base / "receipts"
            raw_dir = base / "raw"
            receipts_dir.mkdir()
            raw_dir.mkdir()

            expected_months = gen_weekly_months(2021, 1, 2026, 7)

            for month_str in expected_months:
                y, m = map(int, month_str.split("-"))
                html_content = _make_weekly_html_with_konut(f"01.{m:02d}.{y}")
                html_file = raw_dir / f"sample_{month_str}.html"
                html_file.write_bytes(html_content)
                correct_sha = hashlib.sha256(html_content).hexdigest()

                rec = {
                    "request_key": f"haftalik_{y}_{m}",
                    "downloaded_at": "2026-09-11T12:00:00",
                    "parameters": {
                        "BaslangicTarihi": f"01.{m:02d}.{y}",
                        "Kalemler": ["5690"],
                        "SeciliParalar": "TL",
                        "Taraflar": ["10001"],
                    },
                    "validation": {"data_rows": 1},
                    "path": f"sample_{month_str}.html",
                    "size_bytes": len(html_content),
                    "sha256": correct_sha,
                }
                (receipts_dir / f"receipt_{month_str}.json").write_text(
                    json.dumps(rec), encoding="utf-8"
                )

            buf = io.StringIO()
            with patch("scripts.bddk.inspect_weekly_daily.Page", side_effect=RuntimeError("Bozuk HTML DOM")):
                with redirect_stdout(buf):
                    res = inspect_haftalik(receipts_dir=receipts_dir, raw_dir=raw_dir)

            self.assertFalse(res["is_valid"])
            self.assertGreater(res["html_parse_hatalari_count"], 0)
            self.assertIn("HTML parse hatasi olan", buf.getvalue())

    def test_inspect_bronze_fails_on_missing_sha256_metadata(self):
        """Makbuzda sha256 alani yoksa fail-closed: parse edilmemeli ve exit 1 vermeli."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            receipts_dir = base / "receipts"
            raw_dir = base / "raw"
            receipts_dir.mkdir()
            raw_dir.mkdir()

            raw_bytes = _make_bronze_raw_content()
            (raw_dir / "valid_raw.json").write_bytes(raw_bytes)

            expected_months = gen_bronze_months(2021, 1, 2026, 7)
            for y, m in expected_months:
                rec = {
                    "request_key": f"tablo4_10001_TL_{y}_{m}",
                    "downloaded_at": "2026-09-11T12:00:00",
                    "parameters": {"tabloNo": "4", "taraf": ["10001"], "paraBirimi": "TL", "yil": y, "ay": m},
                    "validation": {"rows": 41, "period_confirmation": "response_caption"},
                    "path": "valid_raw.json",
                    "size_bytes": len(raw_bytes),
                    # sha256 alani kasitli olarak yok
                }
                (receipts_dir / f"receipt_{y}_{m:02d}.json").write_text(json.dumps(rec), encoding="utf-8")

            buf = io.StringIO()
            with redirect_stdout(buf):
                exit_code = bronze_main(receipts_dir=receipts_dir, raw_dir=raw_dir)

            self.assertEqual(exit_code, 1)
            self.assertIn("Gecersiz veya eksik SHA-256 metadata", buf.getvalue())

    def test_inspect_bronze_fails_on_empty_or_malformed_sha256_metadata(self):
        """Makbuzda sha256 bos veya bicimi bozuksa fail-closed: exit 1 vermeli."""
        for bad_sha in ["", "not_a_valid_hex", "1234", "z" * 64]:
            with tempfile.TemporaryDirectory() as td:
                base = Path(td)
                receipts_dir = base / "receipts"
                raw_dir = base / "raw"
                receipts_dir.mkdir()
                raw_dir.mkdir()

                raw_bytes = _make_bronze_raw_content()
                (raw_dir / "valid_raw.json").write_bytes(raw_bytes)

                expected_months = gen_bronze_months(2021, 1, 2026, 7)
                for y, m in expected_months:
                    rec = {
                        "request_key": f"tablo4_10001_TL_{y}_{m}",
                        "downloaded_at": "2026-09-11T12:00:00",
                        "parameters": {"tabloNo": "4", "taraf": ["10001"], "paraBirimi": "TL", "yil": y, "ay": m},
                        "validation": {"rows": 41, "period_confirmation": "response_caption"},
                        "path": "valid_raw.json",
                        "size_bytes": len(raw_bytes),
                        "sha256": bad_sha,
                    }
                    (receipts_dir / f"receipt_{y}_{m:02d}.json").write_text(json.dumps(rec), encoding="utf-8")

                buf = io.StringIO()
                with redirect_stdout(buf):
                    exit_code = bronze_main(receipts_dir=receipts_dir, raw_dir=raw_dir)

                self.assertEqual(exit_code, 1)
                self.assertIn("Gecersiz veya eksik SHA-256 metadata", buf.getvalue())

    def test_inspect_weekly_fails_on_missing_or_malformed_sha256_metadata(self):
        """Haftalik makbuzda sha256 eksik, bos veya bicimi bozuksa is_valid=False olmali."""
        for bad_sha in [None, "", "bad_hex_123", "0" * 63]:
            with tempfile.TemporaryDirectory() as td:
                base = Path(td)
                receipts_dir = base / "receipts"
                raw_dir = base / "raw"
                receipts_dir.mkdir()
                raw_dir.mkdir()

                expected_months = gen_weekly_months(2021, 1, 2026, 7)
                for month_str in expected_months:
                    y, m = map(int, month_str.split("-"))
                    html_content = _make_weekly_html_with_konut(f"01.{m:02d}.{y}")
                    html_file = raw_dir / f"sample_{month_str}.html"
                    html_file.write_bytes(html_content)

                    rec = {
                        "request_key": f"haftalik_{y}_{m}",
                        "downloaded_at": "2026-09-11T12:00:00",
                        "parameters": {
                            "BaslangicTarihi": f"01.{m:02d}.{y}",
                            "Kalemler": ["5690"],
                            "SeciliParalar": "TL",
                            "Taraflar": ["10001"],
                        },
                        "validation": {"data_rows": 1},
                        "path": f"sample_{month_str}.html",
                        "size_bytes": len(html_content),
                    }
                    if bad_sha is not None:
                        rec["sha256"] = bad_sha
                    (receipts_dir / f"receipt_{month_str}.json").write_text(json.dumps(rec), encoding="utf-8")

                buf = io.StringIO()
                with redirect_stdout(buf):
                    res = inspect_haftalik(receipts_dir=receipts_dir, raw_dir=raw_dir)

                self.assertFalse(res["is_valid"])
                self.assertIn("gecersiz veya eksik SHA-256 metadata", buf.getvalue())

    def test_inspect_bronze_fails_on_file_read_error(self):
        """Fiziksel dosya okumasinda OSError olusursa kontrollu sekilde exit 1 vermeli."""
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            receipts_dir = base / "receipts"
            raw_dir = base / "raw"
            receipts_dir.mkdir()
            raw_dir.mkdir()

            raw_bytes = _make_bronze_raw_content()
            (raw_dir / "valid_raw.json").write_bytes(raw_bytes)
            valid_sha = hashlib.sha256(raw_bytes).hexdigest()

            expected_months = gen_bronze_months(2021, 1, 2026, 7)
            for y, m in expected_months:
                rec = {
                    "request_key": f"tablo4_10001_TL_{y}_{m}",
                    "downloaded_at": "2026-09-11T12:00:00",
                    "parameters": {"tabloNo": "4", "taraf": ["10001"], "paraBirimi": "TL", "yil": y, "ay": m},
                    "validation": {"rows": 41, "period_confirmation": "response_caption"},
                    "path": "valid_raw.json",
                    "size_bytes": len(raw_bytes),
                    "sha256": valid_sha,
                }
                (receipts_dir / f"receipt_{y}_{m:02d}.json").write_text(json.dumps(rec), encoding="utf-8")

            buf = io.StringIO()
            with patch("pathlib.Path.read_bytes", side_effect=PermissionError("Izin reddedildi")):
                with redirect_stdout(buf):
                    exit_code = bronze_main(receipts_dir=receipts_dir, raw_dir=raw_dir)

            self.assertEqual(exit_code, 1)
            self.assertIn("Fiziksel dosya okuma hatasi", buf.getvalue())

    def test_inspect_weekly_fails_on_file_read_error(self):
        """Haftalik dosya okumasinda OSError olusursa kontrollu sekilde is_valid=False olmali."""
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            receipts_dir = base / "receipts"
            raw_dir = base / "raw"
            receipts_dir.mkdir()
            raw_dir.mkdir()

            expected_months = gen_weekly_months(2021, 1, 2026, 7)
            for month_str in expected_months:
                y, m = map(int, month_str.split("-"))
                html_content = _make_weekly_html_with_konut(f"01.{m:02d}.{y}")
                html_file = raw_dir / f"sample_{month_str}.html"
                html_file.write_bytes(html_content)
                correct_sha = hashlib.sha256(html_content).hexdigest()

                rec = {
                    "request_key": f"haftalik_{y}_{m}",
                    "downloaded_at": "2026-09-11T12:00:00",
                    "parameters": {
                        "BaslangicTarihi": f"01.{m:02d}.{y}",
                        "Kalemler": ["5690"],
                        "SeciliParalar": "TL",
                        "Taraflar": ["10001"],
                    },
                    "validation": {"data_rows": 1},
                    "path": f"sample_{month_str}.html",
                    "size_bytes": len(html_content),
                    "sha256": correct_sha,
                }
                (receipts_dir / f"receipt_{month_str}.json").write_text(json.dumps(rec), encoding="utf-8")

            buf = io.StringIO()
            with patch("pathlib.Path.read_bytes", side_effect=OSError("Disk okuma hatasi")):
                with redirect_stdout(buf):
                    res = inspect_haftalik(receipts_dir=receipts_dir, raw_dir=raw_dir)

            self.assertFalse(res["is_valid"])
            self.assertGreater(res["io_errors_count"], 0)
            self.assertIn("Dosya okuma hatasi", buf.getvalue())

    def test_inspect_weekly_deduplicates_refreshed_receipts(self):
        """Haftalik denetimde duplicate makbuzlar en son downloaded_at ile tekillestirilmeli."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            receipts_dir = base / "receipts"
            raw_dir = base / "raw"
            receipts_dir.mkdir()
            raw_dir.mkdir()

            expected_months = gen_weekly_months(2021, 1, 2026, 7)
            for month_str in expected_months:
                y, m = map(int, month_str.split("-"))
                html_content = _make_weekly_html_with_konut(f"01.{m:02d}.{y}")
                html_file = raw_dir / f"sample_{month_str}.html"
                html_file.write_bytes(html_content)
                correct_sha = hashlib.sha256(html_content).hexdigest()

                rec = {
                    "request_key": f"haftalik_{y}_{m}",
                    "downloaded_at": "2026-09-11T12:00:00",
                    "parameters": {
                        "BaslangicTarihi": f"01.{m:02d}.{y}",
                        "Kalemler": ["5690"],
                        "SeciliParalar": "TL",
                        "Taraflar": ["10001"],
                    },
                    "validation": {"data_rows": 1},
                    "path": f"sample_{month_str}.html",
                    "size_bytes": len(html_content),
                    "sha256": correct_sha,
                }
                (receipts_dir / f"receipt_{month_str}.json").write_text(json.dumps(rec), encoding="utf-8")

            # 2021-01 icin eski, bozuk dosyayi gosteren bir duplicate makbuz ekle
            dup_rec = {
                "request_key": "haftalik_2021_1",
                "downloaded_at": "2026-01-01T00:00:00",  # Eski zaman damgasi
                "parameters": {
                    "BaslangicTarihi": "01.01.2021",
                    "Kalemler": ["5690"],
                    "SeciliParalar": "TL",
                    "Taraflar": ["10001"],
                },
                "validation": {"data_rows": 1},
                "path": "non_existent.html",
                "size_bytes": 99999,
                "sha256": "0" * 64,
            }
            (receipts_dir / "receipt_2021_01_old_refresh.json").write_text(json.dumps(dup_rec), encoding="utf-8")

            buf = io.StringIO()
            with redirect_stdout(buf):
                res = inspect_haftalik(receipts_dir=receipts_dir, raw_dir=raw_dir)

            self.assertTrue(res["is_valid"])
            self.assertEqual(res["duplicate_count"], 1)
            self.assertIn("1 eski/refresh makbuz elendi", buf.getvalue())

    def test_inspect_weekly_resolves_konut_column_dynamically_across_header_rows(self):
        """Konut basligi table_rows[1] yerine table_rows[0] veya baska satirda olsa bile dinamik bulunmali."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            receipts_dir = base / "receipts"
            raw_dir = base / "raw"
            receipts_dir.mkdir()
            raw_dir.mkdir()

            expected_months = gen_weekly_months(2021, 1, 2026, 7)
            for month_str in expected_months:
                y, m = map(int, month_str.split("-"))
                html_custom = (
                    "<html><body>"
                    '<table id="TabloExcelGelismis">'
                    "<tr><td>Birim: TL</td><td>Krediler / a) Konut</td><td></td><td></td></tr>"
                    "<tr><td></td><td>TP</td><td>YP</td><td>TOPLAM</td></tr>"
                    f"<tr><td>01.{m:02d}.{y}</td><td>150,00</td><td>0,00</td><td>150,00</td></tr>"
                    "</table></body></html>"
                ).encode("utf-8")
                html_file = raw_dir / f"sample_{month_str}.html"
                html_file.write_bytes(html_custom)
                correct_sha = hashlib.sha256(html_custom).hexdigest()

                rec = {
                    "request_key": f"haftalik_{y}_{m}",
                    "downloaded_at": "2026-09-11T12:00:00",
                    "parameters": {
                        "BaslangicTarihi": f"01.{m:02d}.{y}",
                        "Kalemler": ["5690"],
                        "SeciliParalar": "TL",
                        "Taraflar": ["10001"],
                    },
                    "validation": {"data_rows": 1},
                    "path": f"sample_{month_str}.html",
                    "size_bytes": len(html_custom),
                    "sha256": correct_sha,
                }
                (receipts_dir / f"receipt_{month_str}.json").write_text(json.dumps(rec), encoding="utf-8")

            buf = io.StringIO()
            with redirect_stdout(buf):
                res = inspect_haftalik(receipts_dir=receipts_dir, raw_dir=raw_dir)

            self.assertTrue(res["is_valid"])
            self.assertEqual(res["covered_months_5690_html"], 67)

    def test_inspect_weekly_handles_single_digit_month_in_start_date(self):
        """BaslangicTarihi '01.1.2021' gibi tek haneli ay icerse bile zfill ile 2021-01 standartlasmali."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            receipts_dir = base / "receipts"
            raw_dir = base / "raw"
            receipts_dir.mkdir()
            raw_dir.mkdir()

            expected_months = gen_weekly_months(2021, 1, 2026, 7)
            for month_str in expected_months:
                y, m = map(int, month_str.split("-"))
                html_content = _make_weekly_html_with_konut(f"01.{m:02d}.{y}")
                html_file = raw_dir / f"sample_{month_str}.html"
                html_file.write_bytes(html_content)
                correct_sha = hashlib.sha256(html_content).hexdigest()

                # Tek haneli ay formatı: '01.1.2021'
                start_date_str = f"01.{m}.{y}"
                rec = {
                    "request_key": f"haftalik_{y}_{m}",
                    "downloaded_at": "2026-09-11T12:00:00",
                    "parameters": {
                        "BaslangicTarihi": start_date_str,
                        "Kalemler": ["5690"],
                        "SeciliParalar": "TL",
                        "Taraflar": ["10001"],
                    },
                    "validation": {"data_rows": 1},
                    "path": f"sample_{month_str}.html",
                    "size_bytes": len(html_content),
                    "sha256": correct_sha,
                }
                (receipts_dir / f"receipt_{month_str}.json").write_text(json.dumps(rec), encoding="utf-8")

            buf = io.StringIO()
            with redirect_stdout(buf):
                res = inspect_haftalik(receipts_dir=receipts_dir, raw_dir=raw_dir)

            self.assertTrue(res["is_valid"])
            self.assertEqual(res["covered_months_5690_request"], 67)
            self.assertEqual(res["covered_months_5690_html"], 67)

    def test_inspect_scripts_fail_on_missing_or_invalid_size_bytes(self):
        """Makbuzda size_bytes eksik, None, negatif veya non-int oldugunda fail-closed olmali."""
        for bad_size in [None, -1, 0, "not_int"]:
            with tempfile.TemporaryDirectory() as td:
                base = Path(td)
                receipts_dir = base / "receipts"
                raw_dir = base / "raw"
                receipts_dir.mkdir()
                raw_dir.mkdir()

                raw_bytes = _make_bronze_raw_content()
                (raw_dir / "valid_raw.json").write_bytes(raw_bytes)
                valid_sha = hashlib.sha256(raw_bytes).hexdigest()

                expected_months = gen_bronze_months(2021, 1, 2026, 7)
                for y, m in expected_months:
                    rec = {
                        "request_key": f"tablo4_10001_TL_{y}_{m}",
                        "downloaded_at": "2026-09-11T12:00:00",
                        "parameters": {"tabloNo": "4", "taraf": ["10001"], "paraBirimi": "TL", "yil": y, "ay": m},
                        "validation": {"rows": 41, "period_confirmation": "response_caption"},
                        "path": "valid_raw.json",
                        "sha256": valid_sha,
                    }
                    if bad_size is not None:
                        rec["size_bytes"] = bad_size
                    (receipts_dir / f"receipt_{y}_{m:02d}.json").write_text(json.dumps(rec), encoding="utf-8")

                buf = io.StringIO()
                with redirect_stdout(buf):
                    exit_code = bronze_main(receipts_dir=receipts_dir, raw_dir=raw_dir)

                self.assertEqual(exit_code, 1)
                self.assertIn("gecersiz size_bytes", buf.getvalue())

    def test_inspect_gunluk_validates_physical_files_and_fails_on_hash_or_missing(self):
        """inspect_gunluk fiziksel dosya varligini, boyutunu ve SHA-256'sini dogrulamali."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            receipts_dir = base / "receipts"
            raw_dir = base / "raw"
            receipts_dir.mkdir()
            raw_dir.mkdir()

            html_data = b"<html><body>Tarih: 07.09.2026</body></html>"
            raw_file = raw_dir / "gunluk_2026_09_07.html"
            raw_file.write_bytes(html_data)
            valid_sha = hashlib.sha256(html_data).hexdigest()

            rec = {
                "request_key": "gunluk_snapshot_1",
                "source_url": "https://www.bddk.gov.tr/BultenGunluk",
                "downloaded_at": "2026-09-10T20:32:12",
                "path": "gunluk_2026_09_07.html",
                "size_bytes": len(html_data),
                "sha256": valid_sha,
                "validation": {"dates": ["2026-09-07"], "historical_coverage": "unverified"},
            }
            (receipts_dir / "gunluk_rec.json").write_text(json.dumps(rec), encoding="utf-8")

            # Happy path
            res = inspect_gunluk(receipts_dir=receipts_dir, raw_dir=raw_dir)
            self.assertTrue(res["is_valid"])
            self.assertEqual(res["dosya_hatalari_count"], 0)

            # Negative path 1: SHA-256 uyusmazligi
            rec_bad_sha = dict(rec, sha256="0" * 64)
            (receipts_dir / "gunluk_rec.json").write_text(json.dumps(rec_bad_sha), encoding="utf-8")
            res_bad_sha = inspect_gunluk(receipts_dir=receipts_dir, raw_dir=raw_dir)
            self.assertFalse(res_bad_sha["is_valid"])
            self.assertGreater(res_bad_sha["dosya_hatalari_count"], 0)

            # Negative path 2: Eksik fiziksel dosya
            raw_file.unlink()
            res_missing = inspect_gunluk(receipts_dir=receipts_dir, raw_dir=raw_dir)
            self.assertFalse(res_missing["is_valid"])
            self.assertGreater(res_missing["dosya_hatalari_count"], 0)


if __name__ == "__main__":
    unittest.main()
