"""Run with python -m scripts.download_bddk --help."""
import argparse
import json
from collections import Counter
from datetime import date
from pathlib import Path
from uuid import uuid4

from app.connectors.bddk import Archive, Downloader, Transport, exclusive_archive, utc_now


def main(argv=None):
    parser = argparse.ArgumentParser(description="BDDK ham bültenlerini yerel Bronze'a indir.")
    parser.add_argument("--start", type=date.fromisoformat, default=date(2021, 1, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2026, 7, 31))
    parser.add_argument("--frequency", choices=["all", "aylik", "haftalik", "gunluk"], default="all")
    parser.add_argument("--groups", default="all", help="all veya virgüllü kodlar; kodlar frekansa özgüdür")
    parser.add_argument("--currencies", choices=["all", "TL", "USD"], default="all")
    parser.add_argument("--monthly-tables", default="all", help="all veya virgüllü tablo kodları")
    parser.add_argument("--output", type=Path, default=Path("data/bronze/bddk"))
    parser.add_argument("--limit", type=int, help="Her frekansta en fazla N veri isteği; örnek koşu")
    parser.add_argument("--delay", type=float, default=0.75)
    parser.add_argument("--refresh", action="store_true", help="Önceki veriyi silmeden yeni sürüm kontrol et")
    parser.add_argument("--plan", action="store_true", help="Katalogları al, veri istek sayısını hesapla")
    args = parser.parse_args(argv)
    if args.start > args.end or (args.limit is not None and args.limit < 1) or args.delay < 0:
        parser.error("Tarih aralığı, limit veya bekleme süresi geçersiz.")
    try:
        with exclusive_archive(args.output):
            return run(args)
    except RuntimeError as exc:
        print(str(exc))
        return 1


def run(args):
    downloader = Downloader(Archive(args.output), Transport(delay=args.delay), args.refresh)
    for frequency in (["aylik", "haftalik", "gunluk"] if args.frequency == "all" else [args.frequency]):
        try:
            if frequency == "aylik":
                downloader.monthly(args.start, args.end, args.groups, args.currencies,
                                   args.monthly_tables, args.limit, args.plan)
            elif frequency == "haftalik":
                downloader.weekly(args.start, args.end, args.groups, args.currencies, args.limit, args.plan)
            else:
                downloader.daily(args.start, args.end, args.plan)
        except Exception as exc:
            # Preserve successes from other sources; the process still exits non-zero.
            downloader.results.append({"status": "failed", "frequency": frequency,
                                       "error": f"{type(exc).__name__}: {exc}"})
            print(f"{frequency}: {type(exc).__name__}: {exc}", flush=True)
    counts = dict(Counter(x["status"] for x in downloader.results))
    report = {"created_at": utc_now(), "start": args.start.isoformat(), "end": args.end.isoformat(),
              "mode": "plan" if args.plan else "sample" if args.limit else "download",
              "counts": counts, "catalogs": downloader.catalogs, "results": downloader.results,
              "complete": not args.plan and args.limit is None and not any(counts.get(k) for k in ("failed", "unavailable")),
              "human_semantic_review": "pending"}
    path = args.output / "runs" / f"{uuid4().hex}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps({"counts": counts, "complete": report["complete"], "report": str(path)}, ensure_ascii=False))
    return 1 if counts.get("failed") else 2 if counts.get("unavailable") else 0


if __name__ == "__main__":
    raise SystemExit(main())
