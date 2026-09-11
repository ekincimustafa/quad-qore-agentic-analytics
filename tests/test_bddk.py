"""Offline contract and archive tests; runnable without third-party packages."""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from app.connectors.bddk import (
    Archive, Downloader, Page, Response, Transport, month_ranges,
    exclusive_archive, monthly_validation, select_ids, weekly_validation,
)


def monthly_response(period="2021/1", rows=None):
    return Response(json.dumps({"success": True, "Json": {
        "caption": "Krediler (milyon TL), Dönem:" + period,
        "colModels": [{"name": "Ad"}, {"name": "Toplam"}],
        "data": {"rows": rows if rows is not None else [{"cell": ["Konut", 0]}]},
    }}).encode(), "https://www.bddk.org.tr/report", "application/json")


class BddkTests(unittest.TestCase):
    def test_only_one_cli_can_write_to_an_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            with exclusive_archive(directory):
                with self.assertRaises(RuntimeError):
                    with exclusive_archive(directory):
                        pass
            with exclusive_archive(directory):
                pass

    def test_receipt_recovers_interrupted_index_update(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Archive(directory)
            record = archive.save("aylik", "url", {}, monthly_response(), "json", {})
            archive.index_path.write_text("{}")
            self.assertIsNotNone(Archive(directory).cached(record["request_key"]))

    def test_months_include_partial_and_leap_month(self):
        self.assertEqual(list(month_ranges(date(2024, 2, 15), date(2024, 3, 2))),
                         [(date(2024, 2, 15), date(2024, 2, 29)), (date(2024, 3, 1), date(2024, 3, 2))])
        self.assertEqual(len(list(month_ranges(date(2021, 1, 1), date(2026, 7, 31)))), 67)
        with self.assertRaises(ValueError):
            list(month_ranges(date(2026, 1, 1), date(2025, 1, 1)))

    def test_catalogs_keep_source_specific_ids_and_entities(self):
        page = Page('''<select id="ddlTaraf"><option value="10001">Sekt&#246;r</option></select>
        <td onclick="TarafSec('10005','Kamu')">Kamu</td>
        <td onclick="KalemToggle(55, 'Kredi')"><span>Konut</span></td>''')
        self.assertEqual(page.selects["ddlTaraf"], {"10001": "Sektör"})
        self.assertEqual(page.catalog("TarafSec"), {"10005": "Kamu"})
        self.assertEqual(page.catalog("KalemToggle"), {"55": "Konut"})
        with self.assertRaises(ValueError):
            select_ids("10006", page.catalog("TarafSec"), "grup")

    def test_monthly_zero_is_valid_but_wrong_date_empty_and_html_fail(self):
        self.assertEqual(monthly_validation(monthly_response(), 2021, 1)["rows"], 1)
        for response in (monthly_response("2021/10"), monthly_response(rows=[]),
                         Response(b"<html>Error</html>", "url", "text/html")):
            with self.assertRaises(ValueError):
                monthly_validation(response, 2021, 1)

    def test_weekly_ignores_dates_in_page_dropdowns(self):
        response = Response(b'''<option>08.01.2021</option>
        <table id="TabloExcelGelismis"><tr><td>15.01.2021</td><td>0</td></tr></table>''', "url", "text/html")
        with self.assertRaises(ValueError):
            weekly_validation(response, ["2021-01-08", "2021-01-15"])
        self.assertEqual(weekly_validation(response, ["2021-01-15"])["data_rows"], 1)

    def test_weekly_requires_each_group_currency_and_column(self):
        body = '''<table id="TabloExcelGelismis"><tr><th>Birim: Milyon TL</th></tr>
        <tr><td>Sektör</td></tr><tr><td>08.01.2021</td><td>1</td><td>2</td><td>3</td></tr></table>'''
        response = Response(body.encode(), "url", "text/html")
        weekly_validation(response, ["2021-01-08"], ["Sektör"], 3, "TL")
        for groups, columns, currency in [(["Sektör", "Kamu"], 3, "TL"), (["Sektör"], 6, "TL"), (["Sektör"], 3, "USD")]:
            with self.assertRaises(ValueError):
                weekly_validation(response, ["2021-01-08"], groups, columns, currency)

    def test_known_undated_monthly_tables_are_explicitly_flagged(self):
        original = monthly_response()
        obj = json.loads(original.text)
        obj["Json"]["caption"] = "Rasyolar"
        response = Response(json.dumps(obj).encode(), "url", "application/json")
        result = monthly_validation(response, 2021, 1, table="15")
        self.assertEqual(result["period_confirmation"], "request_only")
        with self.assertRaises(ValueError):
            monthly_validation(response, 2021, 1, table="4")

    def test_raw_versions_resume_and_corruption_detection(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Archive(directory)
            params = {"taraf": ["10001"], "yil": 2021}
            first = archive.save("aylik", "url", params, monthly_response(), "json", {})
            key = first["request_key"]
            self.assertIsNotNone(Archive(directory).cached(key))
            second = archive.save("aylik", "url", params, monthly_response("2021/2"), "json", {})
            self.assertNotEqual(first["path"], second["path"])
            self.assertTrue((Path(directory) / first["path"]).exists())
            (Path(directory) / second["path"]).write_bytes(b"damaged")
            self.assertIsNone(archive.cached(key))

    def test_resume_does_not_request_and_refresh_retains_revision(self):
        class Fake:
            calls = 0
            def request(self, url, data):
                self.calls += 1
                self.last = data
                return monthly_response()
        with tempfile.TemporaryDirectory() as directory:
            fake = Fake()
            downloader = Downloader(Archive(directory), fake)
            for _ in range(2):
                downloader.acquire("aylik", "url", {"yil": 2021}, "json", lambda r: {}, token="session-token")
            self.assertEqual(fake.calls, 1)
            self.assertEqual(fake.last["__RequestVerificationToken"], "session-token")
            self.assertNotIn("session-token", downloader.archive.index_path.read_text())
            downloader.refresh = True
            downloader.acquire("aylik", "url", {"yil": 2021}, "json", lambda r: {})
            self.assertEqual(fake.calls, 2)

    def test_validation_failure_is_not_marked_downloaded(self):
        class Fake:
            def request(self, url, data):
                return monthly_response("2026/7")
        with tempfile.TemporaryDirectory() as directory:
            downloader = Downloader(Archive(directory), Fake())
            downloader.acquire("aylik", "url", {}, "json", lambda r: monthly_validation(r, 2021, 1))
            self.assertEqual(downloader.results[0]["status"], "failed")
            self.assertEqual(downloader.archive.index, {})

    def test_transient_retry_but_not_permanent_http_error(self):
        transport = Transport(delay=0)
        transient = HTTPError("url", 503, "busy", {}, None)
        with patch.object(transport.opener, "open", side_effect=transient) as opened, patch("time.sleep"):
            with self.assertRaises(HTTPError):
                transport.request("https://www.bddk.org.tr")
            self.assertEqual(opened.call_count, 3)
        with patch.object(transport.opener, "open", side_effect=HTTPError("url", 404, "missing", {}, None)) as opened:
            with self.assertRaises(HTTPError):
                transport.request("https://www.bddk.org.tr")
            self.assertEqual(opened.call_count, 1)


if __name__ == "__main__":
    unittest.main()
