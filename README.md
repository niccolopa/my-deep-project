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

## Run the tests
    python -m venv .venv
    .venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    pytest

## Data
No market data is stored in this repository. Raw files are downloaded with the scripts in `scripts/` (Yahoo Finance; LSEG Workspace through the university licence) and stay on my machine, under each provider's terms. The repository tracks only the download manifests (file names, row counts, dates and SHA-256 fingerprints), so every result can be traced to the exact files it used.

## Not done yet
Time metadata for every series, data-quality checks inside the engine, the clean table, and the first study card (H001), which will be written and committed before any run.