# Tests for cleaning_engine.py, step 1 (verified loading).

from __future__ import annotations
import hashlib
import logging
import pandas as pd
import pytest
import cleaning_engine as ce

MANIFEST_COLUMNS = ["file", "series_id", "ticker", "asset_class", "name", "source", "route",
                    "settings", "downloaded_utc", "status", "rows", "first_date", "last_date",
                    "sha256", "log_file", "notes"]
SPLITS_OK = "final_start: 2021-01-01\nlocked_market: [EEM]\n"


# Helpers that build a fake project
def write_price_csv(path, dates):
    frame = pd.DataFrame({"Date": dates, "Adj Close": 1.0, "Close": 1.0, "Dividends": 0.0,
                          "High": 1.0, "Low": 1.0, "Open": 1.0, "Stock Splits": 0.0, "Volume": 10})
    frame.to_csv(path, index=False)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest_row(series_id, file, status="ok", sha="", rows=0, first="", last=""):
    row = dict.fromkeys(MANIFEST_COLUMNS, "")
    row.update(file=file, series_id=series_id, ticker=series_id, status=status,
               sha256=sha, rows=str(rows), first_date=first, last_date=last)
    return row


@pytest.fixture
def project(tmp_path):
    # a fake session with SPY (ok), EEM (ok but locked) and SR3 (failed download).
    session = tmp_path / "data" / "raw" / "yahoo-raw" / "session"
    session.mkdir(parents=True)
    (tmp_path / "config").mkdir()
    splits = tmp_path / "config" / "splits.yaml"
    splits.write_text(SPLITS_OK)

    dates = ["2020-12-29", "2020-12-30", "2020-12-31"]
    spy_sha = write_price_csv(session / "SPY_daily_raw.csv", dates)
    rows = [
        manifest_row("SPY", "SPY_daily_raw.csv", sha=spy_sha, rows=3, first=dates[0], last=dates[-1]),
        # EEM's file deliberately does NOT exist: if the code ever tried to open it, it would fail.
        manifest_row("EEM", "EEM_daily_raw.csv", sha="0" * 64, rows=3, first=dates[0], last=dates[-1]),
        manifest_row("SR3", "", status="failed"),
    ]
    manifest = session / "manifest.csv"
    pd.DataFrame(rows, columns=MANIFEST_COLUMNS).to_csv(manifest, index=False)
    return {"manifest": manifest, "splits": splits, "session": session}


@pytest.fixture
def logger():
    log = logging.getLogger("test_cleaning_engine")
    log.addHandler(logging.NullHandler())
    return log


def rewrite_manifest(path, change):
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    change(frame)
    frame.to_csv(path, index=False)


# one test to show what working means
def test_loads_ok_series_and_skips_the_rest(project, logger):
    result = ce.ingest(project["manifest"], project["splits"], logger)
    assert list(result.frames) == ["SPY"]
    assert len(result.frames["SPY"]) == 3
    assert ("EEM", "locked market") in result.skipped
    assert ("SR3", "manifest status 'failed'") in result.skipped
    assert len(result.manifest_sha256) == 64


# Lock 2: the locked market must be refused before any file is touched
def test_locked_market_file_is_never_opened(project, logger, monkeypatch):
    touched = []
    real_sha = ce.sha256_of_file
    monkeypatch.setattr(ce, "sha256_of_file", lambda p: touched.append(p.name) or real_sha(p))
    real_read = pd.read_csv
    monkeypatch.setattr(ce.pd, "read_csv", lambda p, *a, **k: touched.append(getattr(p, "name", str(p))) or real_read(p, *a, **k))

    ce.ingest(project["manifest"], project["splits"], logger)

    assert "EEM_daily_raw.csv" not in touched
    assert "SPY_daily_raw.csv" in touched          # proves the spy was really watching


def test_locked_market_is_refused_whatever_the_case(project, logger):
    rewrite_manifest(project["manifest"], lambda f: f.__setitem__("series_id", f["series_id"].replace("EEM", " eem ")))
    result = ce.ingest(project["manifest"], project["splits"], logger)
    assert "EEM" not in result.frames
    assert ("EEM", "locked market") in result.skipped


@pytest.mark.parametrize("splits_text", [
    "final_start: 2021-01-01\nlocked_market: []\n",       # empty lock
    "final_start: 2021-01-01\n",                          # missing lock
    "final_start: 2021-01-01\nlocked_market: EEM\n",      # not a list
    "final_start: 2021-01-01\nlocked_market: ['']\n",     # empty entry
])
def test_empty_or_malformed_lock_stops_the_run(project, logger, splits_text):
    project["splits"].write_text(splits_text)
    with pytest.raises(ce.ConfigError):
        ce.ingest(project["manifest"], project["splits"], logger)


# Lock 1: the locked years
def test_row_in_locked_years_stops_the_run(project, logger):
    dates = ["2020-12-30", "2020-12-31", "2021-01-04"]
    sha = write_price_csv(project["session"] / "SPY_daily_raw.csv", dates)

    def change(frame):
        frame.loc[frame.series_id == "SPY", ["sha256", "rows", "first_date", "last_date"]] = [sha, "3", dates[0], dates[-1]]
    rewrite_manifest(project["manifest"], change)

    with pytest.raises(ce.IntegrityError, match="locked years"):
        ce.ingest(project["manifest"], project["splits"], logger)


@pytest.mark.parametrize("splits_text", ["locked_market: [EEM]\n", "final_start: not-a-date\nlocked_market: [EEM]\n"])
def test_missing_or_bad_final_start_stops_the_run(project, logger, splits_text):
    project["splits"].write_text(splits_text)
    with pytest.raises(ce.ConfigError):
        ce.ingest(project["manifest"], project["splits"], logger)


# Integrity: the raw files must be exactly what was downloaded
def test_changed_raw_file_stops_the_run(project, logger):
    path = project["session"] / "SPY_daily_raw.csv"
    path.write_text(path.read_text().replace("1.0", "1.1", 1))   # one changed character
    with pytest.raises(ce.IntegrityError, match="SHA-256 mismatch"):
        ce.ingest(project["manifest"], project["splits"], logger)


def test_missing_raw_file_stops_the_run(project, logger):
    (project["session"] / "SPY_daily_raw.csv").unlink()
    with pytest.raises(ce.IntegrityError, match="missing on disk"):
        ce.ingest(project["manifest"], project["splits"], logger)


def test_row_count_disagreeing_with_manifest_stops_the_run(project, logger):
    rewrite_manifest(project["manifest"], lambda f: f.loc.__setitem__((f.series_id == "SPY", "rows"), "4"))
    with pytest.raises(ce.IntegrityError, match="rows on disk"):
        ce.ingest(project["manifest"], project["splits"], logger)


def test_dates_disagreeing_with_manifest_stop_the_run(project, logger):
    rewrite_manifest(project["manifest"], lambda f: f.loc.__setitem__((f.series_id == "SPY", "first_date"), "2020-12-28"))
    with pytest.raises(ce.IntegrityError, match="dates"):
        ce.ingest(project["manifest"], project["splits"], logger)


# The manifest is an outside input: validate it
def test_missing_manifest_stops_the_run(project, logger):
    with pytest.raises(ce.ManifestError, match="not found"):
        ce.ingest(project["manifest"].with_name("nope.csv"), project["splits"], logger)


def test_manifest_without_sha256_column_stops_the_run(project, logger):
    rewrite_manifest(project["manifest"], lambda f: f.pop("sha256"))
    with pytest.raises(ce.ManifestError, match="missing columns"):
        ce.ingest(project["manifest"], project["splits"], logger)


def test_duplicate_series_in_manifest_stops_the_run(project, logger):
    rewrite_manifest(project["manifest"], lambda f: f.__setitem__("series_id", f["series_id"].replace("SR3", "SPY")))
    with pytest.raises(ce.ManifestError, match="Duplicate"):
        ce.ingest(project["manifest"], project["splits"], logger)


def test_unknown_status_stops_the_run(project, logger):
    rewrite_manifest(project["manifest"], lambda f: f.__setitem__("status", f["status"].replace("failed", "maybe")))
    with pytest.raises(ce.ManifestError, match="Unknown status"):
        ce.ingest(project["manifest"], project["splits"], logger)


@pytest.mark.parametrize("bad_name", ["../SPY_daily_raw.csv", "sub/SPY_daily_raw.csv", "C:\\x.csv", ""])
def test_file_column_must_be_a_plain_name(project, logger, bad_name):
    rewrite_manifest(project["manifest"], lambda f: f.loc.__setitem__((f.series_id == "SPY", "file"), bad_name))
    with pytest.raises(ce.ManifestError, match="plain file name"):
        ce.ingest(project["manifest"], project["splits"], logger)


# The command line: exit code 1 on any stop, so scripts and CI can see it
def test_main_returns_1_when_the_run_stops(project, monkeypatch, tmp_path):
    (project["session"] / "SPY_daily_raw.csv").write_text("Date,Close\n2020-12-31,2\n")
    monkeypatch.setattr(ce, "find_project_root", lambda start: tmp_path)
    assert ce.main([str(project["manifest"])]) == 1


def test_main_returns_0_when_everything_loads(project, monkeypatch, tmp_path):
    monkeypatch.setattr(ce, "find_project_root", lambda start: tmp_path)
    assert ce.main([str(project["manifest"])]) == 0
    assert list((tmp_path / "data" / "logs").glob("*_cleaning_engine.log"))