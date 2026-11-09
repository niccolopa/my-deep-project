from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePath
import pandas as pd
import yaml

# COnstants: what a valid manifest looks like. They mirror download_yahoo.py
REQUIRED_MANIFEST_COLUMNS = {
    "file", "series_id", "status", "sha256", "rows", "first_date", "last_date",
}
# every status the downloader can write. An unknown status means the manifest format changed or was edited by hand, so I stop instead of guessing what it means
KNOWN_STATUS = {"ok", "failed", "no data before lock", "crashed"}
LOADABLE_STATUS = "ok"
DATE_COLUMN = "Date"




#errors. One family, so main() can tell "the run stopped for a known reason" exit 1, clear message) from a real bug (exit 1, full traceback in the log).
class CleaningError(Exception):
    """Base class: the run stopped on purpose."""
 
 
class ConfigError(CleaningError):
    """config/splits.yaml is missing, malformed or leaves a lock empty."""
 
 
class ManifestError(CleaningError):
    """The manifest is missing, malformed or inconsistent."""
 
 
class IntegrityError(CleaningError):
   """A raw file is missing, changed, or does not match what the manifest says."""


# Data structure:
@dataclass(frozen=True)
class Locks:
    locked_markets: frozenset[str]   # series_ids, upper case
    final_start: dt.date             # first locked day: no row may be on or after it

@dataclass
class IngestResult:
    frames: dict[str, pd.DataFrame] = field(default_factory=dict)
    skipped: list[tuple[str, str]] = field(default_factory=list)   # (series_id, reason)
    manifest_sha256: str = ""




# Small pure helpers (no files, no network), 'cause it's easy to test:
def find_project_root(start: Path) -> Path:
    """walk up from 'start' until a folder contains config/splits.yaml.
    Why? The paths must not depend on where the script is launched from, or on where the project folder lives on disk.
    """
    for folder in [start, *start.parents]:
        if (folder / "config" / "splits.yaml").is_file():
            return folder
    raise ConfigError(f"no config/splits.yaml found above {start}")


def normalise_series_id(value: object) -> str:
    """'eem ' and 'EEM' must be the same series, or the lock could be dodged by a typo."""
    return str(value).strip().upper()


def is_bare_filename(name: str) -> bool:
    """The manifest's `file` column must be a plain name, never a path.
    Why? 'cause the manifest is an input from outside this script. A value like '../x.csv' or 
    'C:/x.csv' would make me read a file outside the session folder."""
    
    if not name or name in {".", ".."}:
        return False
    return PurePath(name).name == name and "/" not in name and "\\" not in name


def sha256_of_file(path: Path) -> str:
    """SHA-256 of a file, read in 1 MB chunks so big files don't fill memory."""
    digest = hashlib.sha256()                                                       # Create the footprint "calculator", still empty.
    with open(path, "rb") as handle:                                                # Opens the file in binary read ("rb"): reads the exact bytes, not the interpreted text. An imprint must see the true bytes, including the Windows line breaks. with closes the file at the end, even if an error occurs.
        for chunk in iter(lambda: handle.read(1<<20), b""):                         # Reads the file in 1 MB chunks. 1 << 20 means 2 to the twentieth power, or 1,048,576 bytes. iter(function, b"") repeats the read until the read returns an empty chunk (b""), that is, until the file is finished. 
            digest.update(chunk)                                                    # Adds that piece to the calculation. The final result is identical to what I would have by reading the entire file at once.
    return digest.hexdigest()                                                       # Returns the imprint in hexadecimal, in the same format as the manifest.




#COnfig:
def load_locks(splits_path: Path) -> Locks:
    """Read the two locks from config/splits.yaml. Any doubt stops the run."""
    if not splits_path.is_file():
        raise ConfigError(f"Missing {splits_path}")
    with open(splits_path, encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}

    # Lock 2: the locked market. Empty or missing = fail-closed.
    raw_locked = config.get("locked_market")
    if not isinstance(raw_locked, list) or not raw_locked:
        raise ConfigError("locked_market must be a non-empty list in config/splits.yaml")
    locked = frozenset(normalise_series_id(item) for item in raw_locked)
    if "" in locked:
        raise ConfigError("locked_market contains an empty entry")

    # Lock 1: the locked years. YAML turns 2021-01-01 into a date; accept a string too.
    raw_final = config.get("final_start")
    if isinstance(raw_final, dt.date):
        final_start = raw_final
    elif isinstance(raw_final, str):
        try:
            final_start = dt.date.fromisoformat(raw_final)
        except ValueError as error:
            raise ConfigError(f"final_start is not a date: {raw_final!r}") from error
    else:
        raise ConfigError("final_start is missing in config/splits.yaml")
 
    return Locks(locked_markets=locked, final_start=final_start)




# Manifest:

def read_manifest(manifest_path: Path) -> pd.DataFrame:
    "read the manifest and check that it is valid"

    if not manifest_path.is_file():
        raise ManifestError(f"Manifest not found: {manifest_path}")                          #if the manifest is not there, it stops immediately with a clear message

    manifest = pd.read_csv(manifest_path, dtype=str, keep_default_na=False)                 # pd.read_csv(manifest_path, dtype=str, keep_default_na=False): Reads everything as text. dtype=str prevents pandas from guessing types (for example, turning a SHA starting with digits into a number). keep_default_na=False causes an empty cell to remain "" instead of becoming NaN
    manifest.colummns = manifest.columns.str.strip()                                        # removes any spaces from column names.

    missing = REQUIRED_MANIFEST_COLUMNS - set(manifest.columns)                             # the difference between two sets, i.e. the missing mandatory columns. If it's not empty, it stops.
    if missing:
        raise ManifestError(f'manifest is missing columns: {sorted(missing)}')
    if manifest.empty:
        raise ManifestError(f'manifest has no rows')                                        # an unlined manifest is an error

    manifest["series_id"] = manifest["series_id"].map(normalise_series_id)                  # apply the function I have already written to each line, so eem becomes EEM.
    manifest["starus"] = manifest["starus"].str.strip().str.lower()                         # .str.strip().str.lower() on status: " OK " becomes "ok".

    duplicated = manifest["series_id"][manifest["series_id"].duplicated()].tolist()         # find the repeated series_ids; eg, two lines for SPY would make it ambiguous which file to clean, so it stops.
    if duplicated:
        raise ManifestError(f"Duplicate series_id in manifest: {duplicated}")
    unknown= sorted(set(manifest['status']) - KNOWN_STATUSES)                               # the statuses that the downloader never writes.
    if unknown:
        raise ManifestError(f"Unknown status values in manifest: {unknown}")
    return manifest


def plan_ingestion(manifest: pd.DataFrame, loks: Locks) -> tuple[list[dict], list[tuple[str, str]]]:
    "decide without touching any file, which rows to load and wich to skip. I separated this step to prove that the locked market is excluded before any file is opened, and it can be tested with a manifest alone"

    to_load: list[dict] = []
    skipped: list[tuple[str, str]] = []
    for now in manifest.to_dict('records'):                                                  # it transforms the table into a list of dictionaries, one per row, for example {"series_id": "SPY", "file": "SPY_daily_raw.csv", ...}.
        series_id = row['series_id']
        if series_id in locks.locked_markets:           # the lock is checked first
            skipped.append(series_id, "locked market")
            continue
        if row["status"] != LOADABLE_STATUS:
            skipped.append((series_id, f"manifest status '{row['status']}'"))
            continue
        if not is_bare_filename(row["file"]):
            raise ManifestError(f"{series_id}: 'file' must be a plain file name, got {row['file']!r}")
            ro_load.append(row)
        return to_load, skipped


 
