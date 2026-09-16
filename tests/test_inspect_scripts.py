from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from scripts.bddk.inspect_bronze import (
    generate_expected_months as gen_bronze_months,
    main as bronze_main,
    resolve_secure_raw_path as bronze_resolve_secure_raw_path,
)
from scripts.bddk.inspect_weekly_daily import (
    generate_expected_months as gen_weekly_months,
    inspect_haftalik,
    inspect_gunluk,
    main as weekly_daily_main,
    resolve_secure_raw_path as weekly_resolve_secure_raw_path,
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

    def test_resolve_secure_raw_path_rejects_traversals_and_escapes(self):
        """resolve_secure_raw_path path traversal ve guvensiz yollari guvenli sekilde reddetmeli."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            for resolver in (bronze_resolve_secure_raw_path, weekly_resolve_secure_raw_path):
                # Invalid inputs
                self.assertIsNone(resolver(base, None))
                self.assertIsNone(resolver(base, 12345))
                self.assertIsNone(resolver(base, ""))
                self.assertIsNone(resolver(base, True))

                # Path traversal attempts
                self.assertIsNone(resolver(base, "../../secret.txt"))
                self.assertIsNone(resolver(base, "..\\..\\secret.txt"))
                self.assertIsNone(resolver(base, "sub/../../secret.txt"))
                self.assertIsNone(resolver(base, "C:\\Windows\\System32\\cmd.exe"))
                self.assertIsNone(resolver(base, "D:\\data\\file.json"))

                # Valid paths
                valid_res = resolver(base, "data.json")
                self.assertIsNotNone(valid_res)
                self.assertEqual(valid_res, (base / "data.json").resolve())

                valid_nested = resolver(base, "nested/data.json")
                self.assertIsNotNone(valid_nested)
                self.assertEqual(valid_nested, (base / "nested" / "data.json").resolve())

                # Filename only mode
                fn_res = resolver(base, "anything/deep/file.html", use_filename_only=True)
                self.assertIsNotNone(fn_res)
                self.assertEqual(fn_res, (base / "file.html").resolve())

                # Filename only invalid edge cases
                self.assertIsNone(resolver(base, ".", use_filename_only=True))
                self.assertIsNone(resolver(base, "..", use_filename_only=True))

    def test_inspect_weekly_parses_turkish_thousand_separated_numbers(self):
        """inspect_haftalik Turkce binlik noktali sayilari ('29.921,60') basariyla float'a cevirebilmeli."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            receipts_dir = base / "receipts"
            raw_dir = base / "raw"
            receipts_dir.mkdir()
            raw_dir.mkdir()

            expected_months = gen_weekly_months(2021, 1, 2026, 7)
            for ym in expected_months:
                y, m = ym.split("-")
                # HTML with Turkish formatted thousand-separated numbers: '277.054,48'
                html_content = (
                    "<html><body><table id='TabloExcelGelismis'>"
                    "<tr><td>Birim: Milyon TL</td><td>Krediler / a) Konut</td></tr>"
                    f"<tr><td>15.{m}.{y}</td><td>277.054,48</td></tr>"
                    "</table></body></html>"
                ).encode("utf-8")

                raw_file = raw_dir / f"weekly_{y}_{m}.html"
                raw_file.write_bytes(html_content)
                raw_sha = hashlib.sha256(html_content).hexdigest()

                rec = {
                    "request_key": f"weekly_{y}_{m}",
                    "downloaded_at": "2026-09-11T12:00:00",
                    "parameters": {
                        "BaslangicTarihi": f"01.{m}.{y} 00:00:00",
                        "BitisTarihi": f"28.{m}.{y} 00:00:00",
                        "Kalemler": ["5690"],
                        "SeciliParalar": "TL",
                        "Taraflar": ["10"],
                    },
                    "validation": {"data_rows": 40},
                    "path": f"weekly_{y}_{m}.html",
                    "size_bytes": len(html_content),
                    "sha256": raw_sha,
                }
                (receipts_dir / f"rec_{y}_{m}.json").write_text(json.dumps(rec), encoding="utf-8")

            res = inspect_haftalik(receipts_dir=receipts_dir, raw_dir=raw_dir)
            self.assertTrue(res["is_valid"])
            self.assertEqual(res["covered_months_5690_html"], 67)
            self.assertEqual(res["eksik_5690_html"], [])

    def test_inspect_scripts_fail_closed_on_path_traversal_in_receipts(self):
        """Makbuzda path traversal iceren yollar ('../../...') fail-closed olarak reddedilmeli."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            receipts_dir = base / "receipts"
            raw_dir = base / "raw"
            receipts_dir.mkdir()
            raw_dir.mkdir()

            outside_file = base / "outside_secret.json"
            outside_file.write_bytes(b"secret")

            # 1. Bronze test
            rec_bronze = {
                "request_key": "tablo4_10001_TL_2021_1",
                "downloaded_at": "2026-09-11T12:00:00",
                "parameters": {"tabloNo": "4", "taraf": ["10001"], "paraBirimi": "TL", "yil": 2021, "ay": 1},
                "validation": {"rows": 41},
                "path": "../../outside_secret.json",
                "size_bytes": 6,
                "sha256": hashlib.sha256(b"secret").hexdigest(),
            }
            (receipts_dir / "bronze_traversal.json").write_text(json.dumps(rec_bronze), encoding="utf-8")

            buf = io.StringIO()
            with redirect_stdout(buf):
                code = bronze_main(receipts_dir=receipts_dir, raw_dir=raw_dir)
            self.assertEqual(code, 1)
            self.assertIn("guvensiz yol", buf.getvalue())

            # 2. Gunluk test
            (receipts_dir / "bronze_traversal.json").unlink()
            rec_gunluk = {
                "request_key": "gunluk_1",
                "downloaded_at": "2026-09-11T12:00:00",
                "path": "../../outside_secret.json",
                "size_bytes": 6,
                "sha256": hashlib.sha256(b"secret").hexdigest(),
                "validation": {"dates": ["2026-09-07"], "historical_coverage": "unverified"},
            }
            (receipts_dir / "gunluk_traversal.json").write_text(json.dumps(rec_gunluk), encoding="utf-8")
            res_gunluk = inspect_gunluk(receipts_dir=receipts_dir, raw_dir=raw_dir)
            self.assertFalse(res_gunluk["is_valid"])
            self.assertGreater(res_gunluk["dosya_hatalari_count"], 0)

    def test_inspect_scripts_fail_on_boolean_size_bytes(self):
        """size_bytes degeri bool (True/False) oldugunda fail-closed olarak reddedilmeli."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            receipts_dir = base / "receipts"
            raw_dir = base / "raw"
            receipts_dir.mkdir()
            raw_dir.mkdir()

            raw_bytes = _make_bronze_raw_content()
            raw_file = raw_dir / "valid.json"
            raw_file.write_bytes(raw_bytes)

            expected_months = gen_bronze_months(2021, 1, 2026, 7)
            for y, m in expected_months:
                rec = {
                    "request_key": f"tablo4_10001_TL_{y}_{m}",
                    "downloaded_at": "2026-09-11T12:00:00",
                    "parameters": {"tabloNo": "4", "taraf": ["10001"], "paraBirimi": "TL", "yil": y, "ay": m},
                    "validation": {"rows": 41},
                    "path": "valid.json",
                    "size_bytes": True,  # Bool bypass attempt
                    "sha256": hashlib.sha256(raw_bytes).hexdigest(),
                }
                (receipts_dir / f"rec_{y}_{m}.json").write_text(json.dumps(rec), encoding="utf-8")

            buf = io.StringIO()
            with redirect_stdout(buf):
                code = bronze_main(receipts_dir=receipts_dir, raw_dir=raw_dir)
            self.assertEqual(code, 1)
            self.assertIn("gecersiz size_bytes", buf.getvalue())

    def test_inspect_weekly_rejects_nan_and_inf_numeric_values(self):
        """HTML hucrelerindeki NaN, inf veya -inf degerleri gecerli sayisal veri sayilmamali."""
        for bad_val in ["NaN", "nan", "Inf", "inf", "-Inf", "-infinity"]:
            with tempfile.TemporaryDirectory() as td:
                base = Path(td)
                receipts_dir = base / "receipts"
                raw_dir = base / "raw"
                receipts_dir.mkdir()
                raw_dir.mkdir()

                expected_months = gen_weekly_months(2021, 1, 2026, 7)
                for month_str in expected_months:
                    y, m = map(int, month_str.split("-"))
                    val = bad_val if month_str == "2024-03" else "100,00"
                    html_content = (
                        "<html><body>"
                        '<table id="TabloExcelGelismis">'
                        "<tr></tr>"
                        "<tr><td></td><td>Krediler / a) Konut</td><td></td><td></td></tr>"
                        "<tr><td></td><td>TP</td><td>YP</td><td>TOPLAM</td></tr>"
                        "<tr><td>Sektor</td></tr>"
                        f"<tr><td>01.{m:02d}.{y}</td><td>{val}</td><td>5,00</td><td>105,00</td></tr>"
                        "</table></body></html>"
                    ).encode("utf-8")
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
                        "sha256": hashlib.sha256(html_content).hexdigest(),
                    }
                    (receipts_dir / f"receipt_{month_str}.json").write_text(json.dumps(rec), encoding="utf-8")

                buf = io.StringIO()
                with redirect_stdout(buf):
                    res = inspect_haftalik(receipts_dir=receipts_dir, raw_dir=raw_dir)

                self.assertFalse(res["is_valid"])
                self.assertIn("2024-03", res["eksik_5690_html"])

    def test_inspect_weekly_rejects_invalid_calendar_request_date(self):
        """BaslangicTarihi 31.02.2021 veya 32.01.2021 gibi takvimde olmayan bir tarihse is_valid=False olmali."""
        for bad_date in ["31.02.2021", "32.01.2021", "29.02.2021"]:
            with tempfile.TemporaryDirectory() as td:
                base = Path(td)
                receipts_dir = base / "receipts"
                raw_dir = base / "raw"
                receipts_dir.mkdir()
                raw_dir.mkdir()

                expected_months = gen_weekly_months(2021, 1, 2026, 7)
                for month_str in expected_months:
                    y, m = map(int, month_str.split("-"))
                    if month_str == "2021-02" and "02" in bad_date:
                        start_date = bad_date
                    elif month_str == "2021-01" and "01" in bad_date:
                        start_date = bad_date
                    else:
                        start_date = f"01.{m:02d}.{y}"
                    html_content = _make_weekly_html_with_konut(f"01.{m:02d}.{y}")
                    html_file = raw_dir / f"sample_{month_str}.html"
                    html_file.write_bytes(html_content)

                    rec = {
                        "request_key": f"haftalik_{y}_{m}",
                        "downloaded_at": "2026-09-11T12:00:00",
                        "parameters": {
                            "BaslangicTarihi": start_date,
                            "Kalemler": ["5690"],
                            "SeciliParalar": "TL",
                            "Taraflar": ["10001"],
                        },
                        "validation": {"data_rows": 1},
                        "path": f"sample_{month_str}.html",
                        "size_bytes": len(html_content),
                        "sha256": hashlib.sha256(html_content).hexdigest(),
                    }
                    (receipts_dir / f"receipt_{month_str}.json").write_text(json.dumps(rec), encoding="utf-8")

                buf = io.StringIO()
                with redirect_stdout(buf):
                    res = inspect_haftalik(receipts_dir=receipts_dir, raw_dir=raw_dir)

                self.assertFalse(res["is_valid"])

    def test_inspect_weekly_rejects_invalid_calendar_html_row_date(self):
        """HTML satiri 31.02.2021 gibi gercek olmayan bir takvim tarihi icerdiginde o aya eslesmemeli."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            receipts_dir = base / "receipts"
            raw_dir = base / "raw"
            receipts_dir.mkdir()
            raw_dir.mkdir()

            expected_months = gen_weekly_months(2021, 1, 2026, 7)
            for month_str in expected_months:
                y, m = map(int, month_str.split("-"))
                row_date = "31.02.2021" if month_str == "2021-02" else f"01.{m:02d}.{y}"
                html_content = (
                    "<html><body>"
                    '<table id="TabloExcelGelismis">'
                    "<tr></tr>"
                    "<tr><td></td><td>Krediler / a) Konut</td><td></td><td></td></tr>"
                    "<tr><td></td><td>TP</td><td>YP</td><td>TOPLAM</td></tr>"
                    "<tr><td>Sektor</td></tr>"
                    f"<tr><td>{row_date}</td><td>100,00</td><td>5,00</td><td>105,00</td></tr>"
                    "</table></body></html>"
                ).encode("utf-8")
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
                    "sha256": hashlib.sha256(html_content).hexdigest(),
                }
                (receipts_dir / f"receipt_{month_str}.json").write_text(json.dumps(rec), encoding="utf-8")

            buf = io.StringIO()
            with redirect_stdout(buf):
                res = inspect_haftalik(receipts_dir=receipts_dir, raw_dir=raw_dir)

            self.assertFalse(res["is_valid"])
            self.assertIn("2021-02", res["eksik_5690_html"])

    def test_inspect_scripts_fail_on_non_dict_receipt_json(self):
        """Makbuz JSON'i dict disinda bir tur (liste, string, int) oldugunda fail-closed olmali."""
        bad_receipts = ["[1, 2, 3]", '"just a string"', "12345"]
        for bad_content in bad_receipts:
            with tempfile.TemporaryDirectory() as td:
                base = Path(td)
                receipts_dir = base / "receipts"
                raw_dir = base / "raw"
                receipts_dir.mkdir()
                raw_dir.mkdir()

                # 1. Bronze test
                (receipts_dir / "bad_rec.json").write_text(bad_content, encoding="utf-8")
                buf = io.StringIO()
                with redirect_stdout(buf):
                    code = bronze_main(receipts_dir=receipts_dir, raw_dir=raw_dir)
                self.assertEqual(code, 1)
                self.assertIn("dictionary (object) olmali", buf.getvalue())

                # 2. Haftalik test
                buf = io.StringIO()
                with redirect_stdout(buf):
                    res_h = inspect_haftalik(receipts_dir=receipts_dir, raw_dir=raw_dir)
                self.assertFalse(res_h["is_valid"])

                # 3. Gunluk test
                buf = io.StringIO()
                with redirect_stdout(buf):
                    res_g = inspect_gunluk(receipts_dir=receipts_dir, raw_dir=raw_dir)
                self.assertFalse(res_g["is_valid"])

    def test_inspect_scripts_fail_on_missing_or_empty_request_key(self):
        """Makbuzda request_key eksik, bos veya string disi oldugunda sessizce yutulmamali, fail-closed olmali."""
        bad_keys = [None, "", "   ", 12345, True, []]
        for bad_key in bad_keys:
            with tempfile.TemporaryDirectory() as td:
                base = Path(td)
                receipts_dir = base / "receipts"
                raw_dir = base / "raw"
                receipts_dir.mkdir()
                raw_dir.mkdir()

                rec = {
                    "downloaded_at": "2026-09-11T12:00:00",
                    "parameters": {"tabloNo": "4"},
                    "path": "dummy.html",
                    "size_bytes": 10,
                    "sha256": "a" * 64,
                }
                if bad_key is not None:
                    rec["request_key"] = bad_key

                (receipts_dir / "bad_rk.json").write_text(json.dumps(rec), encoding="utf-8")

                # 1. Bronze test
                buf = io.StringIO()
                with redirect_stdout(buf):
                    code = bronze_main(receipts_dir=receipts_dir, raw_dir=raw_dir)
                self.assertEqual(code, 1)
                self.assertIn("request_key alani bos olmayan bir string olmali", buf.getvalue())

                # 2. Haftalik test
                buf = io.StringIO()
                with redirect_stdout(buf):
                    res_h = inspect_haftalik(receipts_dir=receipts_dir, raw_dir=raw_dir)
                self.assertFalse(res_h["is_valid"])

                # 3. Gunluk test
                buf = io.StringIO()
                with redirect_stdout(buf):
                    res_g = inspect_gunluk(receipts_dir=receipts_dir, raw_dir=raw_dir)
                self.assertFalse(res_g["is_valid"])

    def test_inspect_scripts_fail_on_non_dict_parameters(self):
        """Makbuzda parameters alani string, liste vb. dict disi bir deger oldugunda hata vermeli."""
        for bad_params in ["not_a_dict", [1, 2, 3], 1234]:
            with tempfile.TemporaryDirectory() as td:
                base = Path(td)
                receipts_dir = base / "receipts"
                raw_dir = base / "raw"
                receipts_dir.mkdir()
                raw_dir.mkdir()

                rec = {
                    "request_key": "valid_key_123",
                    "downloaded_at": "2026-09-11T12:00:00",
                    "parameters": bad_params,
                    "path": "dummy.html",
                    "size_bytes": 10,
                    "sha256": "a" * 64,
                }
                (receipts_dir / "bad_params.json").write_text(json.dumps(rec), encoding="utf-8")

                # 1. Bronze test
                buf = io.StringIO()
                with redirect_stdout(buf):
                    code = bronze_main(receipts_dir=receipts_dir, raw_dir=raw_dir)
                self.assertEqual(code, 1)
                self.assertIn("parameters alani dictionary veya null olmali", buf.getvalue())

                # 2. Haftalik test
                buf = io.StringIO()
                with redirect_stdout(buf):
                    res_h = inspect_haftalik(receipts_dir=receipts_dir, raw_dir=raw_dir)
                self.assertFalse(res_h["is_valid"])

                # 3. Gunluk test
                buf = io.StringIO()
                with redirect_stdout(buf):
                    res_g = inspect_gunluk(receipts_dir=receipts_dir, raw_dir=raw_dir)
                self.assertFalse(res_g["is_valid"])

    def test_weekly_daily_main_fails_when_daily_has_physical_errors(self):
        """Haftalik seri 100% basarili olsa dahi gunluk seride fiziksel/hash hatasi varsa main() exit code 1 dondurmeli."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            h_receipts = base / "h_receipts"
            h_raw = base / "h_raw"
            g_receipts = base / "g_receipts"
            g_raw = base / "g_raw"
            h_receipts.mkdir()
            h_raw.mkdir()
            g_receipts.mkdir()
            g_raw.mkdir()

            expected_months = gen_weekly_months(2021, 1, 2026, 7)
            for month_str in expected_months:
                y, m = map(int, month_str.split("-"))
                html_content = _make_weekly_html_with_konut(f"01.{m:02d}.{y}")
                (h_raw / f"sample_{month_str}.html").write_bytes(html_content)
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
                    "sha256": hashlib.sha256(html_content).hexdigest(),
                }
                (h_receipts / f"rec_{month_str}.json").write_text(json.dumps(rec), encoding="utf-8")

            # Gunluk seride fiziksel dosya eksik
            g_rec = {
                "request_key": "gunluk_bad_1",
                "downloaded_at": "2026-09-11T12:00:00",
                "path": "non_existent_gunluk.html",
                "size_bytes": 100,
                "sha256": "b" * 64,
                "validation": {"dates": ["2026-09-07"], "historical_coverage": "unverified"},
            }
            (g_receipts / "g_rec.json").write_text(json.dumps(g_rec), encoding="utf-8")

            buf = io.StringIO()
            with redirect_stdout(buf):
                exit_code = weekly_daily_main(
                    gunluk_receipts_dir=g_receipts,
                    gunluk_raw_dir=g_raw,
                    haftalik_receipts_dir=h_receipts,
                    haftalik_raw_dir=h_raw,
                )

            self.assertEqual(exit_code, 1)
            self.assertIn("BDDK veri denetimi basarisiz oldu", buf.getvalue())

    def test_inspect_bronze_fails_on_non_finite_numeric_values(self):
        """Aylik JSON verisindeki NaN/inf degerleri extract_housing_loan_data ve inspect_bronze tarafindan reddedilmeli."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            receipts_dir = base / "receipts"
            raw_dir = base / "raw"
            receipts_dir.mkdir()
            raw_dir.mkdir()

            bad_payload = json.dumps({
                "Json": {
                    "caption": "Krediler",
                    "colModels": [{"name": "ad"}, {"name": "tp"}, {"name": "yp"}, {"name": "toplam"}],
                    "data": {
                        "rows": [{"cell": ["Tüketici Kredileri - Konut", float("nan"), 0.0, 1000.0]}]
                    },
                }
            }).encode("utf-8")
            (raw_dir / "bad_raw.json").write_bytes(bad_payload)

            expected_months = gen_bronze_months(2021, 1, 2026, 7)
            for y, m in expected_months:
                rec = {
                    "request_key": f"tablo4_10001_TL_{y}_{m}",
                    "downloaded_at": "2026-09-11T12:00:00",
                    "parameters": {"tabloNo": "4", "taraf": ["10001"], "paraBirimi": "TL", "yil": y, "ay": m},
                    "validation": {"rows": 41, "period_confirmation": "response_caption"},
                    "path": "bad_raw.json",
                    "size_bytes": len(bad_payload),
                    "sha256": hashlib.sha256(bad_payload).hexdigest(),
                }
                (receipts_dir / f"rec_{y}_{m:02d}.json").write_text(json.dumps(rec), encoding="utf-8")

            buf = io.StringIO()
            with redirect_stdout(buf):
                exit_code = bronze_main(receipts_dir=receipts_dir, raw_dir=raw_dir)

            self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
