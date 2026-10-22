"""Builds docs/hsi.json: one row per HKEX trading day with the Hang Seng Index close,
previous close and the whole-market (Main Board) HK$ turnover.

Sources
- HKEX Daily Quotations sheet (about 5 weeks kept online): HSI close, previous close, HK$ turnover.
- HKEX Securities Statistics Archive JSON: daily HK$ turnover back to 1986 (up to last month end).
- Eastmoney kline API: HSI closes for the one-time history backfill only.

Usage
  python scripts/hsidata.py update            # daily job: add any new trading days
  python scripts/hsidata.py backfill --since 2016-01-01
"""

import argparse
import datetime as dt
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "docs" / "hsi.json"
HKT = dt.timezone(dt.timedelta(hours=8))
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/130 Safari/537.36"

HKEX = "https://www.hkex.com.hk"
SHEET_URL = HKEX + "/eng/stat/smstat/dayquot/d{:%y%m%d}e.htm"
ARCHIVE_URL = HKEX + "/eng/stat/smstat/mthbull/rpt_data_statistics_archive_trading_data_{}.json"
ARCHIVE_SPANS = [(1986, 1989)] + [(y, y + 4) for y in range(1990, 2030, 5)]
EASTMONEY_URL = ("https://push2his.eastmoney.com/api/qt/stock/kline/get"
                 "?secid=100.HSI&fields1=f1,f2,f3&fields2=f51,f53&klt=101&fqt=0&beg={:%Y%m%d}&end=20500101")

COLUMNS = ["date", "close", "prevClose", "turnover", "halfDay"]
SHEET_DAYS_ONLINE = 35
SHEET_HEAD_BYTES = 64 * 1024  # the figures sit near the top of a ~10 MB sheet


def fetch(url, timeout=60, limit=-1):
    """Returns the response body (the first `limit` bytes if set) as text, or None on HTTP 404."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read(limit).decode("latin-1")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def _num(s):
    return float(s.replace(",", ""))


def parse_sheet(text):
    """Parses a Daily Quotations sheet. Returns a row dict, or None if it lacks the figures."""
    m = re.search(r"Today's Turnover:\s*\(HK\$\):\s*([\d,]+)", text)
    hsi = re.search(r"^\s*HANG SENG INDEX\s+(.+)$", text, re.M)
    date = re.search(r"DATE:\s*(\d{1,2} [A-Z]{3} \d{4})", text)
    if not (m and hsi and date):
        return None
    nums = [_num(x) for x in hsi.group(1).split()]
    # Full day: morning close, close, prev close, change, %change. Half day: no afternoon close.
    if len(nums) not in (4, 5):
        return None
    prev, change = nums[-3], nums[-2]
    return {
        "date": dt.datetime.strptime(date.group(1), "%d %b %Y").date().isoformat(),
        "close": round(prev + change, 2),
        "prevClose": prev,
        "turnover": int(_num(m.group(1))),
        "halfDay": 1 if len(nums) == 4 else 0,
    }


def parse_archive(text):
    """Parses an archive JSON file into {date: (turnover, halfDay)}."""
    cells = {}
    for c in json.loads(text)["tables"][0]["body"]:
        cells.setdefault(c["row"], {})[c["col"]] = c["text"]
    out = {}
    for row in cells.values():
        day = row.get(0, "")
        if re.fullmatch(r"\d{4}/\d{2}/\d{2}", day) and row.get(2):
            out[day.replace("/", "-")] = (int(_num(row[2])), 1 if "*" in row.get(1, "") else 0)
    return out


def parse_eastmoney(text):
    """Parses an Eastmoney kline response ("YYYY-MM-DD,close" lines) into {date: close}."""
    out = {}
    for line in json.loads(text)["data"]["klines"]:
        day, close = line.split(",")[:2]
        out[day] = float(close)
    return out


def load():
    if DATA_FILE.exists():
        data = json.loads(DATA_FILE.read_text())
        return {r[0]: dict(zip(COLUMNS, r)) for r in data["rows"]}
    return {}


def save(rows):
    """Writes the file only if the rows changed. Returns True if written."""
    ordered = [[rows[d][c] for c in COLUMNS] for d in sorted(rows)]
    if DATA_FILE.exists() and json.loads(DATA_FILE.read_text())["rows"] == ordered:
        return False
    doc = {
        "source": "HKEX Daily Quotations and Securities Statistics Archive; history closes from Eastmoney",
        "turnover": "HKEX Main Board total trading value, HKD",
        "updated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "columns": COLUMNS,
        "rows": ordered,
    }
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, separators=(",", ":"))
    DATA_FILE.write_text(text.replace("],[", "],\n[") + "\n")
    return True


def recent_sheets(start, end):
    """Fetches Daily Quotations sheets for weekdays in [start, end]. Missing sheets are skipped."""
    out = {}
    day = start
    while day <= end:
        if day.weekday() < 5:
            text = fetch(SHEET_URL.format(day), limit=SHEET_HEAD_BYTES)
            row = parse_sheet(text) if text else None
            if row:
                out[row["date"]] = row
                print(f"sheet {row['date']}: close {row['close']} turnover {row['turnover']:,}")
        day += dt.timedelta(days=1)
    return out


def update():
    rows = load()
    today = dt.datetime.now(HKT).date()
    start = today - dt.timedelta(days=10)
    if rows:
        start = min(start, dt.date.fromisoformat(max(rows)) + dt.timedelta(days=1))
    start = max(start, today - dt.timedelta(days=SHEET_DAYS_ONLINE))
    rows.update(recent_sheets(start, today))
    print("updated" if save(rows) else "no change")


def backfill(since):
    since_date = dt.date.fromisoformat(since)
    turnover = {}
    for a, b in ARCHIVE_SPANS:
        if b >= since_date.year:
            turnover.update(parse_archive(fetch(ARCHIVE_URL.format(f"{a}_{b}"))))
    closes = parse_eastmoney(fetch(EASTMONEY_URL.format(since_date - dt.timedelta(days=10))))
    print(f"archive turnover days: {len(turnover)}, eastmoney closes: {len(closes)}")

    rows = {}
    prev = None
    for day in sorted(closes):
        if prev is not None and day in turnover and day >= since:
            t, half = turnover[day]
            rows[day] = {"date": day, "close": closes[day], "prevClose": closes[prev],
                         "turnover": t, "halfDay": half}
        prev = day

    today = dt.datetime.now(HKT).date()
    sheets = recent_sheets(today - dt.timedelta(days=SHEET_DAYS_ONLINE), today)
    mismatches = [(d, rows[d]["close"], s["close"]) for d, s in sheets.items()
                  if d in rows and abs(rows[d]["close"] - s["close"]) > 0.05]
    for m in mismatches:
        print("close mismatch (eastmoney vs hkex):", m)
    rows.update(sheets)
    save(rows)
    print(f"rows: {len(rows)}, {min(rows)} to {max(rows)}, mismatches: {len(mismatches)}")
    if len(mismatches) > 2:
        sys.exit("too many mismatches between Eastmoney and HKEX closes")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("update")
    b = sub.add_parser("backfill")
    b.add_argument("--since", default="2016-01-01")
    args = ap.parse_args()
    if args.cmd == "update":
        update()
    else:
        backfill(args.since)


if __name__ == "__main__":
    main()
