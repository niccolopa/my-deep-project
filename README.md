# My Deep Project

An honest, long-running quantitative research project: testing trading ideas the way a research desk would, with every rule fixed before looking at the data.

**Status:** building the data-cleaning engine. Step 1 (verified loading of raw files) is done and tested; no strategy results yet. Day-by-day log: [progress.md](./progress.md).

## How the research is protected
- **Cards before data:** every idea is written and committed before it is run.
- **Locks:** no data from 2021 onward and no data from one locked market (EEM) until the final phase. See [locks.md](./locks.md).
- **Every run is counted** in `logbook/runs.csv`, crashes included, so the number of attempts is known.
- **Raw files are never edited:** the cleaner checks each file's SHA-256 fingerprint against the download manifest and stops on any mismatch.

## Pipeline
raw files (as downloaded) → cleaning engine (load, check, flag) → one clean table → backtests

## Data cleaning

**Done and tested**
- Raw files are loaded only if their SHA-256 fingerprint, row count and date range match the download manifest. The locked market is refused before its file is opened, and the run stops on any row dated 2021 or later (24 tests, each protection tested in the case where it must refuse).

**In progress**
- One clock for every price: each series gets its exchange time zone and close time, and every row gets the UTC time at which the price could really be known (`available_at_utc`). A backtest will use a price only after that time. Draft metadata for 58 series: `reference/instruments_draft_2026-11-15.csv`; close times that no public source documents are marked unknown and treated conservatively.

**Planned**
- Data-quality checks inside the engine, writing to an issues table: robust spike detection (median and MAD over a rolling year, flagged only if the move reverses the next day), twin-series checks (e.g. spot EURUSD against the CME future), explicit flags for non-positive prices. Suspicious values are flagged, never rewritten.

## Run the tests
    python -m venv .venv
    .venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    pytest

## Data
No market data is stored in this repository. Raw files are downloaded with the scripts in `scripts/` (Yahoo Finance; LSEG Workspace through the university licence) and stay on my machine, under each provider's terms. The repository tracks only the download manifests (file names, row counts, dates and SHA-256 fingerprints), so every result can be traced to the exact files it used.

## Not done yet
The clean table and the first study card (H001), which will be written and committed before any run.