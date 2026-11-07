"""
Download daily data from Yahoo Finance (via yfinance) for the research universe,
up to the lock date 2020-12-31.

What it does
- One request per instrument, with retries, so one failure never hides another.
- Saves each raw file exactly as received (only rows after the lock are dropped,
  and the manifest says how many), one file per instrument.
- Writes manifest.csv: request settings, row count, first/last date, SHA-256.
- Never overwrites: every run gets its own timestamped folder.
- Writes download.log: every attempt, retry, error and lock drop, timestamped.

How to run (from the project folder, the one that contains data/):
    Clean files go to data/clean/yahoo-clean/<run>/, the log to data/logs/.
    The script finds the project folder by itself, so it can sit in the
    project root, in scripts/ or in data/.

    python download_yahoo.py                 # whole universe
    python download_yahoo.py --only SPY VIX  # just these series_ids (test first!)
    python download_yahoo.py --list          # show the universe and exit

Personal research use only: Yahoo's terms forbid republishing the raw data.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import logging
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

START = "1980-01-01"                 # Yahoo returns from each series' first day
LOCK_DATE = pd.Timestamp("2020-12-31")
END_EXCLUSIVE = "2021-01-01"         # yfinance's `end` is EXCLUSIVE

def find_project_root() -> Path:
    """The folder that contains data/, wherever this script sits
    (project root, scripts/ or data/) and wherever you run it from."""
    here = Path(__file__).resolve().parent
    for p in [here, *here.parents]:
        if p.name != "data" and (p / "data").is_dir():
            return p
    sys.exit("Can't find the project's data folder. Put this script inside"
             r"C:\dev\my-deep-project (or its scripts\ or data\ folder).")


PROJECT_ROOT = find_project_root()
DATA_DIR = PROJECT_ROOT / "data"
RAW_ROOT = DATA_DIR / "clean" / "yahoo-clean"   # one subfolder per run
LOG_DIR = DATA_DIR / "logs"                 # one log file per run

# Series that belong to your locked market. Fill in BEFORE running,
# e.g. {"EFA"}. They are skipped and never touch your disk.
LOCKED_MARKET: set[str] = {"EEM"}

FUT = "Yahoo continuous front month: rolls NOT adjusted, no open interest"

# (series_id, yahoo_ticker, asset_class, name, note)
UNIVERSE = [
    # --- Futures (front month only) ---
    ("ES",  "ES=F",  "future", "CME E-mini S&P 500",          FUT),
    ("NQ",  "NQ=F",  "future", "CME E-mini Nasdaq-100",       FUT),
    ("RTY", "RTY=F", "future", "CME E-mini Russell 2000",     FUT),
    ("ZT",  "ZT=F",  "future", "CBOT 2-Year Treasury Note",   FUT),
    ("ZF",  "ZF=F",  "future", "CBOT 5-Year Treasury Note",   FUT),
    ("ZN",  "ZN=F",  "future", "CBOT 10-Year Treasury Note",  FUT),
    ("ZB",  "ZB=F",  "future", "CBOT US Treasury Bond",       FUT),
    ("SR3", "SR3=F", "future", "CME Three-Month SOFR",        FUT + "; exists only since 2018"),
    ("6E",  "6E=F",  "future", "CME Euro FX",                 FUT),
    ("6J",  "6J=F",  "future", "CME Japanese Yen",            FUT),
    ("6B",  "6B=F",  "future", "CME British Pound",           FUT),
    ("6S",  "6S=F",  "future", "CME Swiss Franc",             FUT),
    ("6C",  "6C=F",  "future", "CME Canadian Dollar",         FUT),
    ("6A",  "6A=F",  "future", "CME Australian Dollar",       FUT),
    ("GC",  "GC=F",  "future", "COMEX Gold",                  FUT),
    ("SI",  "SI=F",  "future", "COMEX Silver",                FUT),
    ("HG",  "HG=F",  "future", "COMEX Copper",                FUT),
    ("CL",  "CL=F",  "future", "NYMEX WTI Light Sweet Crude", FUT),
    ("BZ",  "BZ=F",  "future", "ICE Brent Crude",             FUT),
    ("NG",  "NG=F",  "future", "NYMEX Henry Hub Natural Gas", FUT),
    ("RB",  "RB=F",  "future", "NYMEX RBOB Gasoline",         FUT),
    ("HO",  "HO=F",  "future", "NYMEX NY Harbor ULSD",        FUT),
    ("ZC",  "ZC=F",  "future", "CBOT Corn",                   FUT),
    ("ZW",  "ZW=F",  "future", "CBOT Chicago SRW Wheat",      FUT),
    ("ZS",  "ZS=F",  "future", "CBOT Soybeans",               FUT),
    ("ZL",  "ZL=F",  "future", "CBOT Soybean Oil",            FUT),
    ("KC",  "KC=F",  "future", "ICE US Coffee C",             FUT),
    ("CC",  "CC=F",  "future", "ICE US Cocoa",                FUT),
    ("BTC", "BTC=F", "future", "CME Bitcoin (optional)",      FUT + "; exists only since late 2017"),
    # --- ETFs (the PDF's list plus Tutorial 1's) ---
    ("SPY", "SPY", "etf", "SPDR S&P 500 ETF Trust", ""),
    ("QQQ", "QQQ", "etf", "Invesco QQQ Trust", ""),
    ("IWM", "IWM", "etf", "iShares Russell 2000 ETF", ""),
    ("TLT", "TLT", "etf", "iShares 20+ Year Treasury Bond ETF", ""),
    ("IEF", "IEF", "etf", "iShares 7-10 Year Treasury Bond ETF", ""),
    ("GLD", "GLD", "etf", "SPDR Gold Shares", ""),
    ("SLV", "SLV", "etf", "iShares Silver Trust", ""),
    ("XLE", "XLE", "etf", "Energy Select Sector SPDR Fund", ""),
    ("HYG", "HYG", "etf", "iShares iBoxx High Yield Corporate Bond ETF", ""),
    ("LQD", "LQD", "etf", "iShares iBoxx Investment Grade Corporate Bond ETF", ""),
    ("EFA", "EFA", "etf", "iShares MSCI EAFE ETF", "Tutorial 1"),
    ("EEM", "EEM", "etf", "iShares MSCI Emerging Markets ETF", "Tutorial 1"),
    ("DBC", "DBC", "etf", "Invesco DB Commodity Index Tracking Fund", "Tutorial 1"),
    ("FXE", "FXE", "etf", "Invesco CurrencyShares Euro Trust", "Tutorial 1"),
    ("FXY", "FXY", "etf", "Invesco CurrencyShares Japanese Yen Trust", "Tutorial 1"),
    ("FXB", "FXB", "etf", "Invesco CurrencyShares British Pound Trust", "Tutorial 1"),
    # --- Cash indices ---
    ("SPX", "^GSPC", "index", "S&P 500 index", "price index, no dividends"),
    ("NDX", "^NDX",  "index", "Nasdaq-100 index", "price index, no dividends"),
    # --- Spot FX (write the quote direction into your instruments table) ---
    ("EURUSD", "EURUSD=X", "fx", "EUR/USD", "USD per EUR"),
    ("USDJPY", "JPY=X",    "fx", "USD/JPY", "JPY per USD"),
    ("GBPUSD", "GBPUSD=X", "fx", "GBP/USD", "USD per GBP"),
    ("USDCHF", "CHF=X",    "fx", "USD/CHF", "CHF per USD"),
    ("USDCAD", "CAD=X",    "fx", "USD/CAD", "CAD per USD"),
    ("AUDUSD", "AUDUSD=X", "fx", "AUD/USD", "USD per AUD"),
    # --- Volatility indices ---
    ("VIX",  "^VIX",  "vol_index", "Cboe Volatility Index", ""),
    ("VVIX", "^VVIX", "vol_index", "Cboe VIX of VIX Index", ""),
    ("MOVE", "^MOVE", "vol_index", "ICE BofAML MOVE Index", "computed once a day, after the close"),
    # --- Treasury yields (Yahoo has no 2-year: use FRED DGS2) ---
    ("UST13W", "^IRX", "yield", "US 13-week T-bill yield", "check units: percent"),
    ("UST5Y",  "^FVX", "yield", "US 5-year Treasury yield", "check units: percent"),
    ("UST10Y", "^TNX", "yield", "US 10-year Treasury yield", "check units: percent"),
    ("UST30Y", "^TYX", "yield", "US 30-year Treasury yield", "check units: percent"),
]

# In the PDF but NOT obtainable from Yahoo. Get them elsewhere or skip.
NOT_ON_YAHOO = {
    "Futures 2nd-4th maturities, individual and expired contracts": "LSEG",
    "Futures open interest and settlement prices": "LSEG",
    "VIX futures": "LSEG (Yahoo coverage unreliable)",
    "Historical options (chains, implied vol, Greeks)": "LSEG / OptionMetrics; Yahoo has today's chain only",
    "COT positioning": "CFTC website, free",
    "US 2-year yield": "FRED DGS2",
    "SOFR overnight rate (and DFF substitute)": "FRED SOFR / DFF",
    "High-yield and investment-grade OAS": "LSEG or Datastream (FRED keeps only 3 years now)",
}

MANIFEST_COLUMNS = [
    "file", "series_id", "ticker", "asset_class", "name", "source", "route",
    "settings", "downloaded_utc", "status", "rows", "first_date", "last_date",
    "sha256", "log_file", "notes",
]


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Recent yfinance versions return (field, ticker) columns even for one ticker."""
    if isinstance(df.columns, pd.MultiIndex):
        level = 0 if "Close" in df.columns.get_level_values(0) else 1
        df = df.copy()
        df.columns = df.columns.get_level_values(level)
    return df


log = logging.getLogger("clean_yahoo")


def setup_logging(stamp: str) -> Path:
    """Log to the console (short) and to data/logs/<stamp>_yahoo_download.log
    (full, timestamped)."""
    log.setLevel(logging.DEBUG)
    log.handlers.clear()
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{stamp}_yahoo_download.log"

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(message)s"))

    log.addHandler(file_handler)
    log.addHandler(console)
    return log_path


def fetch(ticker: str, retries: int = 3, pause: float = 5.0) -> tuple[pd.DataFrame, str]:
    """One instrument. auto_adjust=False keeps Close AND Adj Close, plus
    dividends and splits, so nothing is overwritten before you see it."""
    last_err = ""
    for attempt in range(1, retries + 1):
        log.debug(f"{ticker}: attempt {attempt}/{retries}")
        try:
            df = yf.download(
                ticker,
                start=START,
                end=END_EXCLUSIVE,
                interval="1d",
                auto_adjust=False,
                actions=True,
                progress=False,
                threads=False,
            )
            if df is not None and not df.empty:
                log.debug(f"{ticker}: received {len(df)} rows, columns {list(flatten_columns(df).columns)}")
                return flatten_columns(df), ""
            last_err = "empty response"
        except Exception as e:  # network errors, rate limits, bad tickers
            last_err = f"{type(e).__name__}: {e}"
        log.warning(f"{ticker}: attempt {attempt} failed ({last_err})")
        if attempt < retries:
            time.sleep(pause * attempt)
    return pd.DataFrame(), last_err


def enforce_lock(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Drop anything after 2020-12-31 and say how many rows went."""
    idx = pd.to_datetime(df.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    df = df.copy()
    df.index = idx
    after = df.index > LOCK_DATE
    return df.loc[~after], int(after.sum())


def run(universe=UNIVERSE, sleep_between: float = 1.0) -> Path:
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    session = RAW_ROOT / f"{stamp}_universe"
    session.mkdir(parents=True, exist_ok=False)   # raw folders are never reused
    log_path = setup_logging(stamp)

    route = f"yfinance {yf.__version__}, pandas {pd.__version__}"
    settings = f"start={START} end={END_EXCLUSIVE}(exclusive) interval=1d auto_adjust=False actions=True"
    log.info(f"Project:        {PROJECT_ROOT}")
    log.info(f"Session folder: {session}")
    log.info(f"Log file:       {log_path}")
    log.debug(f"Python {platform.python_version()} on {platform.platform()}")
    log.debug(f"Route: {route}")
    log.debug(f"Settings: {settings}")
    log.debug(f"Locked market: {sorted(LOCKED_MARKET) or 'NONE SET'}")
    if not LOCKED_MARKET:
        log.warning("LOCKED_MARKET is empty: is that intended?")
    log.info(f"{len(universe)} series requested\n")

    manifest = []
    t0 = time.time()

    for series_id, ticker, asset_class, name, note in universe:
        if series_id in LOCKED_MARKET:
            log.info(f"skip   {series_id:7s} locked market")
            continue

        row = dict.fromkeys(MANIFEST_COLUMNS, "")
        row.update(series_id=series_id, ticker=ticker, asset_class=asset_class,
                   name=name, source="Yahoo Finance", route=route, settings=settings,
                   downloaded_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   log_file=log_path.name, notes=note)

        try:
            df, err = fetch(ticker)
            if df.empty:
                row.update(status="failed", notes="; ".join(x for x in (note, err) if x))
                log.error(f"FAILED {series_id:7s} {ticker:9s} {err}")
            else:
                df, n_after = enforce_lock(df)
                if n_after:
                    log.debug(f"{ticker}: dropped {n_after} rows after the lock")
                if df.empty:
                    row.update(status="no data before lock")
                    log.warning(f"empty  {series_id:7s} {ticker:9s} no rows up to 2020-12-31")
                else:
                    df.index.name = "Date"
                    fname = f"{series_id}_daily_raw.csv"
                    path = session / fname
                    df.to_csv(path)
                    extra = f"dropped {n_after} rows after lock" if n_after else ""
                    row.update(file=fname, status="ok", rows=len(df),
                               first_date=df.index.min().date().isoformat(),
                               last_date=df.index.max().date().isoformat(),
                               sha256=sha256_of(path),
                               notes="; ".join(x for x in (note, extra) if x))
                    log.info(f"ok     {series_id:7s} {ticker:9s} {row['first_date']} -> "
                             f"{row['last_date']}  {len(df):>6} rows")
                    log.debug(f"{fname}: sha256 {row['sha256']}")
        except Exception:  # never let one series kill the whole run
            log.exception(f"CRASH  {series_id:7s} {ticker:9s} unexpected error")
            row.update(status="crashed")

        manifest.append(row)
        time.sleep(sleep_between)

    with open(session / "manifest.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_COLUMNS)
        writer.writeheader()
        writer.writerows(manifest)

    counts: dict[str, int] = {}
    for r in manifest:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    log.info(f"\nDone in {time.time() - t0:.0f} s: "
             + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    for r in manifest:
        if r["status"] != "ok":
            log.info(f"  to check: {r['series_id']} ({r['ticker']}): {r['status']}")
    log.info(f"Manifest: {session / 'manifest.csv'}")
    log.info(f"Log:      {log_path}")
    log.info("Not on Yahoo, get these elsewhere:")
    for what, where in NOT_ON_YAHOO.items():
        log.info(f"  - {what}: {where}")
    logging.shutdown()
    return session


def main() -> None:
    parser = argparse.ArgumentParser(description="Download the Yahoo universe up to 2020-12-31.")
    parser.add_argument("--only", nargs="+", metavar="SERIES_ID",
                        help="download only these series_ids, e.g. --only SPY VIX")
    parser.add_argument("--list", action="store_true", help="print the universe and exit")
    parser.add_argument("--pause", type=float, default=1.0,
                        help="seconds between instruments (default 1)")
    args = parser.parse_args()

    if args.list:
        for sid, tic, ac, name, _ in UNIVERSE:
            flag = "  (locked)" if sid in LOCKED_MARKET else ""
            print(f"{sid:7s} {tic:9s} {ac:10s} {name}{flag}")
        return

    universe = UNIVERSE
    if args.only:
        wanted = {s.upper() for s in args.only}
        known = {sid.upper() for sid, *_ in UNIVERSE}
        unknown = wanted - known
        if unknown:
            sys.exit(f"Unknown series_id: {', '.join(sorted(unknown))}. Use --list to see them.")
        universe = [u for u in UNIVERSE if u[0].upper() in wanted]

    run(universe, sleep_between=args.pause)


if __name__ == "__main__":
    main()