from __future__ import annotations
import argparse
import csv
import hashlib
import platform
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import yfinance as yf

start= "1980-01-01"
lock_date= pd.Timestamp("2020-12-31")
end_exclusive = "2021-01-01"

def find_project_root() -> Path:
    here= Path(__file__).resolve().parent
    for p in [here, *here.parents]:
        if p.name != "data" and (p/"data").is_dir():
            return p
        sys.exit("Can't find the project's data folder. Put this script inside "
                 r"C:\dev\my-deep-project (or its scripts\ or data\ folder).")

project_root = find_project_root()
data_dir= project_root/"data"
clean_root= data_dir/"clean" / "yahoo-clean"
log_dir = data_dir/"logs"

LOCKED_MARKET: set[str] = {"EEM"}
FUT = "Yahoo continuous front month: rolls NOT adjusted, no open interest"

UNIVERSE = [
    #Futures
    ("ES",  "ES=F",  "future", "CME E-mini S&P 500", FUT),
    ("NQ",  "NQ=F",  "future", "CME E-mini Nasdaq-100", FUT),
    ("RTY", "RTY=F", "future", "CME E-mini Russell 2000", FUT),
    ("ZT",  "ZT=F",  "future", "CBOT 2-Year Treasury Note", FUT),
    ("ZF",  "ZF=F",  "future", "CBOT 5-Year Treasury Note", FUT),
    ("ZN",  "ZN=F",  "future", "CBOT 10-Year Treasury Note", FUT),
    ("ZB",  "ZB=F",  "future", "CBOT US Treasury Bond", FUT),
    ("SR3", "SR3=F", "future", "CME Three-Month SOFR", FUT),
    ("6E",  "6E=F",  "future", "CME Euro FX", FUT),
    ("6J",  "6J=F",  "future", "CME Japanese Yen", FUT),
    ("6B",  "6B=F",  "future", "CME British Pound", FUT),
    ("6S",  "6S=F",  "future", "CME Swiss Franc", FUT),
    ("6C",  "6C=F",  "future", "CME Canadian Dollar",ù FUT),
    ("6A",  "6A=F",  "future", "CME Australian Dollar", FUT),
    ("GC",  "GC=F",  "future", "COMEX Gold", FUT),
    ("SI",  "SI=F",  "future", "COMEX Silver", FUT),
    ("HG",  "HG=F",  "future", "COMEX Copper", FUT),
    ("CL",  "CL=F",  "future", "NYMEX WTI Light Sweet Crude", FUT),
    ("BZ",  "BZ=F",  "future", "ICE Brent Crude", FUT),
    ("NG",  "NG=F",  "future", "NYMEX Henry Hub Natural Gas", FUT),
    ("RB",  "RB=F",  "future", "NYMEX RBOB Gasoline", FUT),
    ("HO",  "HO=F",  "future", "NYMEX NY Harbor ULSD", FUT),
    ("ZC",  "ZC=F",  "future", "CBOT Corn", FUT),
    ("ZW",  "ZW=F",  "future", "CBOT Chicago SRW Wheat", FUT),
    ("ZS",  "ZS=F",  "future", "CBOT Soybeans", FUT),
    ("ZL",  "ZL=F",  "future", "CBOT Soybean Oil", FUT),
    ("KC",  "KC=F",  "future", "ICE US Coffee C", FUT),
    ("CC",  "CC=F",  "future", "ICE US Cocoa", FUT),
    ("BTC", "BTC=F", "future", "CME Bitcoin", FUT),
    
    # ETFs
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
    
    #Cash indices
    ("SPX", "^GSPC", "index", "S&P 500 index", "price index, no dividends"),
    ("NDX", "^NDX",  "index", "Nasdaq-100 index", "price index, no dividends"),
    
    #Spot FX
    ("EURUSD", "EURUSD=X", "fx", "EUR/USD", "USD per EUR"),
    ("USDJPY", "JPY=X",    "fx", "USD/JPY", "JPY per USD"),
    ("GBPUSD", "GBPUSD=X", "fx", "GBP/USD", "USD per GBP"),
    ("USDCHF", "CHF=X",    "fx", "USD/CHF", "CHF per USD"),
    ("USDCAD", "CAD=X",    "fx", "USD/CAD", "CAD per USD"),
    ("AUDUSD", "AUDUSD=X", "fx", "AUD/USD", "USD per AUD"),
    
    #Volatility indices
    ("VIX",  "^VIX",  "vol_index", "Cboe Volatility Index", ""),
    ("VVIX", "^VVIX", "vol_index", "Cboe VIX of VIX Index", ""),
    ("MOVE", "^MOVE", "vol_index", "ICE BofAML MOVE Index", "computed once a day, after the close"),

    #Treasury yields
    ("UST13W", "^IRX", "yield", "US 13-week T-bill yield", "check units: percent"),
    ("UST5Y",  "^FVX", "yield", "US 5-year Treasury yield", "check units: percent"),
    ("UST10Y", "^TNX", "yield", "US 10-year Treasury yield", "check units: percent"),
    ("UST30Y", "^TYX", "yield", "US 30-year Treasury yield", "check units: percent"),
]

MANIFEST_COLUMNS = [
    "file", "series_id", "ticker", "asset_class", "name", "source", "route",
    "settings", "downloaded_utc", "status", "rows", "first_date", "last_date",
    "sha256", "log_file", "notes",
]

def sha256_of(path: Path) ->str:
    h=hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: d.read(1<<20), b""):
            h.update(chunk)
    return h.hexdigest()

def flatten_columns(df: pd.DataFrame) ->pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        level=0 if "Close" in df.columns.get_level_values(0) else 1
        df=df.copy()
        df.columns=df.columns.get_level_values(level)
    return df

log = logging.getLogger("download_yahoo")

#log to console
def setup_logging(stamp: str) ->Path:
    log.setLevel(logging.DEBUG)
    log.handlers.clear()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path= log_dir/f"{stamp}_yahoo_download.log"

    file_handler= logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    ))

    console= logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(message)s"))

    log.addHandler(file_handler)
    log.addHandler(console)
    return log_path

#instrument to adjust close/dividends/splits
def fetch(ticker: str, retries: int=3, pause: float=5.0 )-> tuple[pd.DataFrame, str]:
    last_err=""
    for attempt in range(1, retries + 1):
        log.debug(f"{ticker}: attempt {attempt}/{retries}")
        try:
            df= yf.download(
                ticker,
                start=start,
                end=end_exclusive,
                interval="1d",
                auto_adjust=False,
                actions=True,
                progress=False,
                threads=False
            )
            if df is not None and not df.empty:
                log.debug(f"{ticker}: received {len(df) rows, columns {list(flatten_columns(df).columns)}}")
                return flatten_columns(df), ""
            last_err= "empty response"
        except Exception as e: 
            last_err=f"{type(e).__name__}: {e}"
        log.warning(f"{ticker}: attempt {attempt} failed ({last_err})")
        if attempt < retries:
            time.sleep(pause*attempt)
    return pd.DataFrame(), last_err


#Drop anything after 2020-12-31 and say how many rows went.
def enforce_lock(df: pd.DataFrame)->tuple[pd.DataFrame]:
    idx=pd.to_datetime(df.index)
    if idx.tz is not None:
        idx=idx.tz_localize(None)
    df= df.copy()
    df.index=idx
    after= df.index >lock_date
    return df.loc[after], int(after.sum())

#stamp and log
def run(universe= UNIVERSE, sleep_between: float=1.0)->Path:
    stamp= datetime.now().strftime("%Y-%m-%d_%H%M%S")
    session= clean_root / f"{stamp}_universe"
    session.mkdir(parents=True, exist_ok=False)
    log_path= setup_logging(stamp)

    route= f"yfinance {yf.__version__}, pandas {pd.__version__}"
    settings = f"start={start} end={end_exclusive}(exclusive) interval=1d auto_adjust=Dalse actions=True"
    log.info()
    log.info()
    log.info()
    log.debug()