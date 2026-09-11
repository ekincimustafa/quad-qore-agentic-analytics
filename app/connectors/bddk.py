"""BDDK public bulletin acquisition; raw responses stay in Bronze.

Uses only Python's standard library. Endpoint contracts were checked against
BDDK's own HTML/JavaScript, not inferred from third-party bank-code lists.
"""
from __future__ import annotations

import calendar
import hashlib
import json
import re
import ssl
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timezone
from html import unescape
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, HTTPSHandler, Request, build_opener
from uuid import uuid4

# Official GlobalSign intermediate certificate SHA-256 fingerprint
# BDDK's web servers omit this intermediate certificate ('GlobalSign RSA OV SSL CA 2018')
# in their TLS handshakes. Supplying and verifying it allows standard OpenSSL/urllib
# to establish full cryptographic verification against the system Root CA.
GLOBALSIGN_INTERMEDIATE_SHA256 = (
    "b676ffa3179e8812093a1b5eafee876ae7a6aaf231078dad1bfb21cd2893764a"
)


def create_secure_ssl_context(cafile: str | Path | None = None) -> ssl.SSLContext:
    """Create an SSL context strictly enforcing certificate and hostname verification.

    Never disables CERT_REQUIRED or check_hostname. Loads the fingerprint-verified
    intermediate CA certificate if present.
    """
    ctx = ssl.create_default_context()
    ctx.verify_mode = ssl.CERT_REQUIRED
    ctx.check_hostname = True

    cert_path = Path(cafile) if cafile else Path(__file__).parent / "certs" / "globalsign_intermediate.pem"
    if cert_path.is_file():
        # Verify certificate content integrity before loading
        raw_pem = cert_path.read_text(encoding="utf-8")
        lines = [line.strip() for line in raw_pem.splitlines() if line and not line.startswith("---")]
        import base64
        der_bytes = base64.b64decode("".join(lines))
        actual_fp = hashlib.sha256(der_bytes).hexdigest()
        if actual_fp != GLOBALSIGN_INTERMEDIATE_SHA256:
            raise ValueError(
                f"CA sertifika parmak izi eşleşmiyor! Beklenen: {GLOBALSIGN_INTERMEDIATE_SHA256}, Alınan: {actual_fp}"
            )
        ctx.load_verify_locations(cafile=str(cert_path))

    return ctx


MONTHLY = "https://www.bddk.org.tr/BultenAylik"
WEEKLY = "https://www.bddk.org.tr/BultenHaftalik"
DAILY = "https://www.bddk.gov.tr/BultenGunluk"



@contextmanager
def exclusive_archive(root):
    """An OS lock prevents two CLI processes from overwriting the same index."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".download.lock").open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            import msvcrt
        except ImportError:
            import fcntl
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise RuntimeError("Bu çıktı klasöründe başka bir indirici çalışıyor.") from exc
        else:
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError("Bu çıktı klasöründe başka bir indirici çalışıyor.") from exc
        yield


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def month_ranges(start: date, end: date):
    if start > end:
        raise ValueError("Başlangıç bitişten sonra olamaz.")
    current = start.replace(day=1)
    while current <= end:
        last = date(current.year, current.month, calendar.monthrange(current.year, current.month)[1])
        yield max(start, current), min(end, last)
        if last >= end:
            break
        current = date.fromordinal(last.toordinal() + 1)


class Page(HTMLParser):
    """Small discovery parser: selects, clickable catalog labels and table rows."""
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.selects, self.clicks, self.tables = {}, {}, {}
        self.token = ""
        self.select = self.option = self.click = self.table = self.cell = None
        self.row = None
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "input" and a.get("name") == "__RequestVerificationToken":
            self.token = a.get("value", "")
        if tag == "select":
            self.select = a.get("id", a.get("name", ""))
            self.selects.setdefault(self.select, {})
        if tag == "option" and self.select:
            self.option = a.get("value", "")
            self.selects[self.select][self.option] = ""
        if a.get("onclick") and tag == "td":
            self.click = a["onclick"]
            self.clicks.setdefault(self.click, "")
        if tag == "table":
            self.table = a.get("id")
            if self.table:
                self.tables[self.table] = []
        if tag == "tr" and self.table:
            self.row = []
        if tag in ("td", "th") and self.row is not None:
            self.cell = ""

    def handle_data(self, data):
        if self.option is not None and self.select:
            self.selects[self.select][self.option] += data
        if self.click:
            self.clicks[self.click] += data
        if self.cell is not None:
            self.cell += data

    def handle_endtag(self, tag):
        if tag == "option":
            self.option = None
        if tag == "select":
            self.select = None
        if tag in ("td", "th"):
            if self.cell is not None and self.row is not None:
                self.row.append(" ".join(self.cell.split()))
            self.cell = None
            self.click = None
        if tag == "tr":
            if self.table and self.row is not None:
                self.tables[self.table].append(self.row)
            self.row = None
        if tag == "table":
            self.table = None

    def catalog(self, function):
        result = {}
        for call, label in self.clicks.items():
            match = re.match(rf"{function}\(['\"]?(\d+)", call)
            if match:
                result[match[1]] = " ".join(label.split())
        return result


@dataclass
class Response:
    body: bytes
    url: str
    content_type: str

    @property
    def text(self):
        return self.body.decode("utf-8-sig")


class Transport:
    def __init__(self, delay=0.75, retries=3, timeout=60, ssl_context=None):
        if delay < 0 or retries < 1 or timeout <= 0:
            raise ValueError("Geçersiz ağ ayarları.")
        self.delay, self.retries, self.timeout = delay, retries, timeout
        self.ssl_context = ssl_context or create_secure_ssl_context()
        self.opener = build_opener(
            HTTPSHandler(context=self.ssl_context),
            HTTPCookieProcessor(CookieJar()),
        )
        self.last_request = 0.0

    def request(self, url, data=None):
        body = urlencode(data, doseq=True).encode() if data is not None else None
        for attempt in range(self.retries):
            time.sleep(max(0, self.delay - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            request = Request(url, data=body, headers={
                "User-Agent": "Quad-Qore-BDDK-Research/0.1",
                "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            })
            try:
                with self.opener.open(request, timeout=self.timeout) as r:
                    return Response(r.read(), r.url, r.headers.get("Content-Type", ""))
            except HTTPError as exc:
                if exc.code not in (429, 500, 502, 503, 504) or attempt + 1 == self.retries:
                    raise
                retry_after = exc.headers.get("Retry-After", "")
                wait = min(60, float(retry_after)) if retry_after.isdigit() else 2 ** attempt
            except (URLError, TimeoutError):
                if attempt + 1 == self.retries:
                    raise
                wait = 2 ** attempt
            time.sleep(wait)
        raise RuntimeError("İstek tamamlanamadı.")


class Archive:
    """Content-addressed files + immutable receipt + resumable request index.

    Atomic replacement is used only for the local index; earlier raw versions
    and receipts are preserved. Run one downloader per output directory.
    """
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "index.json"
        # Receipts are authoritative, including a completed download immediately
        # before an interrupted index update. The index is a rebuildable cache.
        self.index = {}
        for path in self.root.glob("*/receipts/*.json"):
            item = json.loads(path.read_text("utf-8"))
            previous = self.index.get(item["request_key"])
            if previous is None or item["downloaded_at"] > previous["downloaded_at"]:
                self.index[item["request_key"]] = item

    @staticmethod
    def key(frequency, url, params):
        value = json.dumps([frequency, url, params], sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(value.encode()).hexdigest()

    def cached(self, key):
        item = self.index.get(key)
        if not item:
            return None
        path = self.root / item["path"]
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            return None
        return item

    def save(self, frequency, url, params, response, extension, validation):
        key = self.key(frequency, url, params)
        digest = hashlib.sha256(response.body).hexdigest()
        relative = Path(frequency) / "raw" / f"{key[:16]}-{digest}.{extension}"
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            temp = path.with_name(path.name + "." + uuid4().hex + ".part")
            temp.write_bytes(response.body)
            temp.replace(path)
        item = {
            "request_key": key, "source_url": url, "resolved_url": response.url,
            "method": "POST" if params else "GET", "parameters": params,
            "downloaded_at": utc_now(), "sha256": digest, "size_bytes": len(response.body),
            "content_type": response.content_type, "path": relative.as_posix(),
            "validation": validation,
        }
        receipts = self.root / frequency / "receipts"
        receipts.mkdir(parents=True, exist_ok=True)
        (receipts / f"{uuid4().hex}.json").write_text(json.dumps(item, ensure_ascii=False, indent=2), "utf-8")
        self.index[key] = item
        temp = self.index_path.with_suffix(".json.part")
        temp.write_text(json.dumps(self.index, ensure_ascii=False, indent=2), "utf-8")
        temp.replace(self.index_path)
        return item


def monthly_validation(response, year, month, expected_groups=None, table=None):
    payload = json.loads(response.text)
    if payload.get("success") is not True:
        raise ValueError("BDDK aylık yanıtı success=true değil.")
    report = payload.get("Json", {})
    rows = report.get("data", {}).get("rows", [])
    if not rows:
        raise ValueError("BDDK aylık yanıtında veri satırı yok.")
    caption = report.get("caption", "")
    period_in_caption = bool(re.search(rf"Dönem:\s*{year}/{month}(?!\d)", caption))
    known_undated = {"15": "Rasyolar", "16": "Diğer Bilgiler", "17": "Yurt Dışı Şube Rasyoları"}
    if not period_in_caption and known_undated.get(str(table)) != caption:
        raise ValueError(f"Yanıt dönemi istekle eşleşmiyor: {caption}")
    columns = report.get("colModels", [])
    if not columns or any(len(r.get("cell", [])) != len(columns) for r in rows):
        raise ValueError("Aylık sütun/satır şeması değişmiş.")
    if expected_groups:
        group_column = next((i for i, c in enumerate(columns) if c.get("name") == "BankaAdi"), None)
        observed = {r["cell"][group_column] for r in rows} if group_column is not None else set()
        if observed != set(expected_groups):
            raise ValueError(f"Aylık banka kapsamı eşleşmiyor: {sorted(observed)}")
    return {"period": f"{year}-{month:02d}", "period_confirmation": "response_caption" if period_in_caption else "request_only",
            "rows": len(rows), "caption": caption,
            "semantic_review": "pending"}


def extract_housing_loan_data(payload: dict) -> dict:
    """Extract housing loan figures from BDDK Table 4 JSON payload.

    Uses schema-aware column resolution via `colModels` and indicator label lookup,
    never positional indexing.

    Returns:
        dict with keys: 'label', 'tp', 'yp', 'toplam', 'caption'

    Raises:
        ValueError: If colModels is missing, required columns cannot be resolved uniquely,
                    or the indicator row cannot be uniquely identified.
    """
    if not isinstance(payload, dict):
        raise ValueError("BDDK yanıtı bir JSON sözlüğü (dict) olmalıdır.")
    report = payload.get("Json", {}) if "Json" in payload else payload
    if not isinstance(report, dict):
        raise ValueError("BDDK yanıtında 'Json' alanı bir sözlük olmalıdır.")
    col_models = report.get("colModels", [])
    if not col_models:
        raise ValueError("BDDK yanıtında 'colModels' sütun şeması bulunamadı.")

    col_map = {}
    for idx, col in enumerate(col_models):
        name = col.get("name", "").strip().lower()
        if name in col_map:
            raise ValueError(f"colModels içinde mükerrer sütun adı: {name}")
        col_map[name] = idx

    required_cols = {"ad", "tp", "yp", "toplam"}
    missing = required_cols - set(col_map.keys())
    if missing:
        raise ValueError(f"BDDK şemasında gerekli sütunlar bulunamadı: {missing}")

    ad_idx = col_map["ad"]
    tp_idx = col_map["tp"]
    yp_idx = col_map["yp"]
    toplam_idx = col_map["toplam"]

    rows = report.get("data", {}).get("rows", [])
    if not rows:
        raise ValueError("BDDK yanıtında veri satırı bulunamadı.")

    target_label = "Tüketici Kredileri - Konut"
    matched = []
    for r in rows:
        cell = r.get("cell", [])
        if len(cell) <= max(ad_idx, tp_idx, yp_idx, toplam_idx):
            continue
        cell_label = " ".join(str(cell[ad_idx]).split())
        if cell_label == target_label:
            matched.append(cell)

    if len(matched) == 0:
        raise ValueError(f"'{target_label}' gösterge satırı BDDK tablosunda bulunamadı.")
    if len(matched) > 1:
        raise ValueError(
            f"'{target_label}' gösterge satırı için birden fazla eşleşme bulundu: {len(matched)}"
        )

    row_cell = matched[0]
    return {
        "label": target_label,
        "tp": float(row_cell[tp_idx]),
        "yp": float(row_cell[yp_idx]),
        "toplam": float(row_cell[toplam_idx]),
        "caption": report.get("caption", ""),
    }



def weekly_validation(response, expected_dates, expected_groups=None, expected_values=None, currency=None):
    table = Page(response.text).tables.get("TabloExcelGelismis", [])
    if currency and not any(f"Birim: Milyon {currency}" == cell for row in table[:3] for cell in row):
        raise ValueError("Haftalık yanıt para birimi istekle eşleşmiyor.")
    dates = []
    grouped_dates = {}
    group = None
    for row in table:
        if len(row) == 1 and row[0].strip():
            group = row[0].casefold()
        if row and re.fullmatch(r"\d{1,2}\.\d{1,2}\.\d{4}", row[0]):
            if len(row) < 2:
                raise ValueError("Haftalık gözlemde değer sütunu yok.")
            if expected_values is not None and len(row) != expected_values + 1:
                raise ValueError(f"Haftalık sütun sayısı eşleşmiyor: {len(row) - 1}, beklenen {expected_values}")
            observation = datetime.strptime(row[0], "%d.%m.%Y").date().isoformat()
            dates.append(observation)
            grouped_dates.setdefault(group, []).append(observation)
    if not dates or set(dates) != set(expected_dates):
        raise ValueError("Haftalık tablo tarihleri yayın takvimiyle eşleşmiyor.")
    if expected_groups:
        expected_names = {g.casefold() for g in expected_groups}
        if set(grouped_dates) != expected_names:
            raise ValueError(f"Haftalık banka kapsamı eşleşmiyor: {list(grouped_dates)}")
        for observations in grouped_dates.values():
            if sorted(observations) != sorted(expected_dates):
                raise ValueError("Haftalık banka grubunda eksik veya tekrarlı dönem var.")
    return {"dates": sorted(set(dates)), "data_rows": len(dates),
            "semantic_review": "pending", "note": "Boş hücreler ham yanıtta korunur."}


def select_ids(requested, catalog, label):
    result = list(catalog) if requested == "all" else requested.split(",")
    if not result or any(x not in catalog for x in result):
        raise ValueError(f"Geçersiz {label}. Mevcut değerler: {catalog}")
    return list(dict.fromkeys(result))


class Downloader:
    def __init__(self, archive, transport=None, refresh=False):
        self.archive = archive
        self.transport = transport or Transport()
        self.refresh = refresh
        self.results = []
        self.catalogs = {}

    def acquire(self, frequency, url, params, extension, validate, token=None):
        key = self.archive.key(frequency, url, params)
        cached = None if self.refresh else self.archive.cached(key)
        if cached:
            try:
                # A newer validator also checks older cached downloads.
                validation = validate(Response((self.archive.root / cached["path"]).read_bytes(),
                                               cached["resolved_url"], cached["content_type"]))
                self.results.append({"status": "cached", **cached, "validation": validation})
                return
            except (ValueError, KeyError, TypeError):
                pass
        try:
            actual = dict(params) if params else None
            if token:
                actual["__RequestVerificationToken"] = token
            response = self.transport.request(url, actual)
            validation = validate(response)
            item = self.archive.save(frequency, url, params, response, extension, validation)
            self.results.append({"status": "downloaded", **item})
        except (ValueError, KeyError, TypeError, URLError, TimeoutError) as exc:
            self.results.append({"status": "failed", "source_url": url, "parameters": params,
                                 "error": str(exc)})
        print(f"{frequency}: {self.results[-1]['status']} ({len(self.results)})", flush=True)

    def monthly(self, start, end, groups="all", currencies="all", tables="all", limit=None, plan=False):
        home = self.transport.request(MONTHLY)
        page = Page(home.text)
        catalog = {"tables": page.selects.get("TabloListesi", {}),
                   "groups": page.selects.get("ddlTaraf", {})}
        table_ids = select_ids(tables, catalog["tables"], "aylık tablo")
        group_ids = select_ids(groups, catalog["groups"], "aylık banka grubu")
        self.archive.save("aylik", MONTHLY, None, home, "html", {"kind": "discovery"})
        self.catalogs["aylik"] = catalog
        jobs = []
        for table in table_ids:
            url = MONTHLY + "/tr/Home/ParaBirimiGetir?" + urlencode({"tabloNo": table})
            currency_response = self.transport.request(url)
            available = {x["Id"]: x["Name"] for x in json.loads(currency_response.text)}
            self.archive.save("aylik", url, None, currency_response, "json", {"kind": "currency_catalog"})
            chosen = list(available) if currencies == "all" else [x for x in currencies.split(",") if x in available]
            if not chosen:
                raise ValueError(f"Tablo {table} için seçilen para birimi desteklenmiyor: {available}")
            for first, last in month_ranges(start, end):
                for currency in chosen:
                    jobs.append({"tabloNo": table, "yil": first.year, "ay": first.month,
                                 "paraBirimi": currency, "taraf": group_ids})
        self.catalogs["aylik"]["planned_requests"] = len(jobs)
        if plan:
            return
        for job in jobs[:limit]:
            self.acquire("aylik", MONTHLY + "/tr/Home/BasitRaporGetir", job, "json",
                         lambda r, j=job: monthly_validation(r, j["yil"], j["ay"],
                                                           [catalog["groups"][g] for g in group_ids], j["tabloNo"]))

    def weekly(self, start, end, groups="all", currencies="all", limit=None, plan=False):
        url = WEEKLY + "/tr/Gelismis"
        home = self.transport.request(url)
        page = Page(home.text)
        catalog = {"items": page.catalog("KalemToggle"), "groups": page.catalog("TarafSec")}
        if not catalog["items"] or not page.token:
            raise ValueError("Haftalık katalog veya oturum formu bulunamadı.")
        group_ids = select_ids(groups, catalog["groups"], "haftalık banka grubu")
        currency_ids = select_ids(currencies, page.selects.get("CokluPara", {}), "haftalık para birimi")
        available_dates = sorted({datetime.strptime(x.split()[0], "%d.%m.%Y").date()
                                  for x in page.selects.get("baslangicTarih", {})})
        self.archive.save("haftalik", url, None, home, "html", {"kind": "discovery"})
        catalog["available_dates"] = [d.isoformat() for d in available_dates]
        self.catalogs["haftalik"] = catalog
        jobs = []
        # Bounded monthly requests; batches avoid very wide responses/server limits.
        items = list(catalog["items"])
        for first, last in month_ranges(start, end):
            expected = [d.isoformat() for d in available_dates if first <= d <= last]
            if not expected:
                self.results.append({"status": "unavailable", "frequency": "haftalik",
                                     "start": first.isoformat(), "end": last.isoformat()})
                continue
            for offset in range(0, len(items), 25):
                for currency in currency_ids:
                    params = {"BaslangicTarihi": first.strftime("%d.%m.%Y 00:00:00"),
                              "BitisTarihi": last.strftime("%d.%m.%Y 00:00:00"), "dil": "tr",
                              "Kalemler": items[offset:offset + 25], "Taraflar": group_ids,
                              "SeciliParalar": currency, "kalemSutun": ["TP", "YP", "Toplam"]}
                    jobs.append((params, expected))
        catalog["planned_requests"] = len(jobs)
        if plan:
            return
        for job, expected in jobs[:limit]:
            self.acquire("haftalik", url + "/GelismisRaporGetir", job, "html",
                         lambda r, e=expected, j=job: weekly_validation(
                             r, e, [catalog["groups"][g] for g in group_ids],
                             len(j["Kalemler"]) * 3, j["SeciliParalar"]), token=page.token)

    def daily(self, start, end, plan=False):
        response = self.transport.request(DAILY)
        page = Page(response.text)
        tables = {k: v for k, v in page.tables.items() if v}
        dates = sorted({datetime.strptime(x, "%d.%m.%Y").date().isoformat()
                        for x in re.findall(r"Tarih:\s*(\d{1,2}\.\d{1,2}\.\d{4})", unescape(response.text))})
        if not dates or not tables:
            raise ValueError("Günlük yayın tarihi veya veri tablosu bulunamadı.")
        self.catalogs["gunluk"] = {"snapshot_dates": dates, "tables": list(tables),
                                   "historical_endpoint_verified": False}
        if not plan:
            item = self.archive.save("gunluk", DAILY, None, response, "html",
                                     {"kind": "current_snapshot", "dates": dates,
                                      "requested_start": start.isoformat(), "requested_end": end.isoformat(),
                                      "historical_coverage": "unverified"})
            self.results.append({"status": "downloaded", **item})
        self.results.append({"status": "unavailable", "frequency": "gunluk",
                             "reason": "Geçmiş tarih aralığına erişim doğrulanmadı; yalnızca mevcut yayın erişimi doğrulandı."})
