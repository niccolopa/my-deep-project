# 16 Nov 2026
- Rewrote the git history to remove the LSEG file committed on 6 Oct (it was still downloadable from old commits) and to replace my personal email with the GitHub noreply address. Done on a mirror clone with git filter-repo; pushed to a new repository; the old one is renamed my-deep-project-old-private and stays private. Commit dates unchanged, hashes changed; old → new map kept privately.
- Fresh working folder cloned from the new repository; ignored files (data, logs, .venv) copied back; the LSEG file is ignored by .gitignore (checked with git check-ignore). pytest: 24 passed.
- AI help: procedure planned step by step with Claude.

- Second pass the same day: removed every PDF from the history (a published paper and exported notes, not mine to redistribute) and added *.pdf to .gitignore; the PDFs stay on my machine. Repository deleted and recreated before ever being public, so no cached copy of the old commits remains on GitHub.



# 15 nov 2026
- Fixed the pandas `inplace` deprecation in one test; the first attempt left a bare `lambda` on line 162 and broke the test (23 passed, 1 failed). Fixed in commit NEW (7062e51 before the history rewrites of 16 Nov). pytest after the fix: 24 passed.
- Wrote the decisions behind `checks.sql` (log returns, median and MAD, reversal condition, 250-day window, threshold 8, flag never fix), with two whiteboard photos, in `docs/notes/checks_sql/`.
- Started step 2, time metadata: draft for all 58 series in `reference/instruments_draft_2026-11-15.csv`, one official source per row (CME, CBOT, NYMEX, COMEX settlement times; NYSE Arca close; Cboe VIX and VVIX methodology; ICE hours and settlement windows).
  - 15 rows certain, 33 likely, 10 guessing.
  - Not documented anywhere public: daily cut-off of Yahoo spot FX, calculation time of Cboe yield indices, MOVE before 2019, exact publication time of SPX and NDX closes. These are marked unknown and treated as available at 23:59 New York.
  - Futures: Yahoo does not say whether `Close` is the settlement or the last trade, so availability is set at CME's final settlement publication (18:00 Chicago, 19:00 New York).
- Reviewed the 7 Nov quality report (produced by the fail-open `run_checks.py`, so zeros prove nothing):
  - bad prints in Yahoo spot FX: EURUSD 16% and USDJPY 17% in one day, while 6E, FXE and FXY never exceed 4.5%;
  - the returns check skips non-positive prices, so CL's -37.63 (April 2020) is invisible to the spike test;
  - large "moves" in ZB and ZC are likely roll jumps (Yahoo futures are not roll-adjusted);
  - RTY and BTC start in 2017: no data in the training period.
- Wrote `scripts/diagnostics_2026-11-15.sql`: six read-only queries to find the dates behind these anomalies, with notes in `docs/notes/diagnostics.md`.
- AI help: metadata research, report review, diagnostics queries and notes drafted with Claude. The metadata draft is not yet checked row by row.
- Next: run pytest and record the number; check the draft against its sources; run the diagnostics; then write step 2 code (join the metadata, stop on a missing series, compute `available_at_utc`, daylight-saving tests).



# 9 nov 2026
- Reviewed with Claude: the 7 Nov cleaning_engine.py crashed on the first row (`symbol` is not a manifest column) and locks.md claimed enforcement that didn't exist yet (see engineering standards, defects 14 and 20).
- Decisions: a SHA-256 mismatch stops the whole run; the locked market is read from config/splits.yaml, and an empty lock stops the run.
- Moved the 7 Nov download from data/clean to data/raw, and the QA report to reports/.
- Started hand-typing the new cleaning engine (step 1: verified loading) on branch wip/cleaning-engine-step1, to understand every line. Not runnable yet.
- Removed the old cleaning_engine.py and scripts/clean_yahoo.py. Added requirements.txt.

## 9 nov 2026 (part 2):
- Hand-typed `read_manifest`, `plan_ingestion` and `verify_and_read` (cleaning engine step 1) on branch `wip/cleaning-engine-step1`.
- `ruff check` found 12 name errors (typos such as `KNOWN_STATUSES`, `now`/`row`, `ro_load`, `exected_rows`).
- Code review found 5 bugs ruff cannot see: a misspelled attribute (`colummns`), a misspelled column key (`starus`), `list.append` called with two arguments in the locked-market branch, `return` indented inside the loop (only the first manifest row would be processed), and `row, dict` instead of `row: dict` in a function signature.
- Lesson: a linter checks names and syntax, not logic. Only the tests prove the code does what it should, especially the refusal paths. The 24 tests go in when step 1 is complete.
- Still to type: `ingest`, `setup_logger`, `main`.



# 7 nov 2026:
- fixed some bugs in checks.sql;
- created an engine with python that runs checks.sql;
- tested the checks.sql through duckdb on SPY and got this result:
--- RESULT 1 ---
 Count
  7033

--- RESULT 2 ---
 rows      first       last
 7033 1993-01-29 2020-12-31

--- RESULT 3 ---
Empty DataFrame
Columns: [Date, n]
Index: []

--- RESULT 4 ---
 weekday    n
       1 1325
       2 1442
       3 1442
       4 1416
       5 1408

--- RESULT 5 ---
 close_null  open_null  volume_null
          0          0            0

--- RESULT 6 ---
 ohlc_bad
        0

--- RESULT 7 ---
Empty DataFrame
Columns: [yr, flat]
Index: []

--- RESULT 8 ---
 vol_zero  vol_below_10
        0             0

--- RESULT 9 ---
  yr  missing
1993        7
1994        8
1995        8
1996        8
1997        8
1998        9
1999        9
2000        8
2001       13
2002        9
2003        9
2004       10
2005        8
2006        9
2007       10
2008        9
2009        9
2010        9
2011        8
2012       11
2013        9
2014        9
2015        9
2016        9
2017        9
2018       10
2019        9
2020        9

--- RESULT 10 ---
 stale_3
       2

--- RESULT 11 ---
 Count
  7033

--- RESULT 12 ---
 Count
  7033

--- RESULT 13 ---
 Count
  7033

--- RESULT 14 ---
      Date      Close     ret     z
2011-08-08 112.260002 -0.0673 -10.0
2018-03-26 265.109985  0.0270   8.4
2020-03-09 274.230011 -0.0813 -12.8
2020-03-12 248.110001 -0.1006 -15.5
2020-03-13 269.320007  0.0820  12.6
2020-03-26 261.200012  0.0567   8.4

--- RESULT 15 ---
      Date      Close     ret
2008-10-13 101.349998  0.1356
2020-03-16 239.850006 -0.1159
2008-10-28  93.760002  0.1105
2008-10-15  90.019997 -0.1036
2020-03-12 248.110001 -0.1006

All checks completed.

## 7 nov 2026 (Part 2): scaling QA to the full 58-asset universe

- Cleaned up `checks.sql` so it only holds the SQL queries. Updated `run_checks.py` to loop through all 58 CSV files in my download folder and feed them into DuckDB one by one.

- Set up pandas in the script to bundle everything into a clean master summary table (`data_quality_report.csv`) and save it right into `data/clean/yahoo-clean/`.

- Ran into a weird DuckDB crash (`_duckdb.Error: Unknown exception`) on statement 11 for `CL` and `UST13W`:
  - **Why it happened:** WTI Crude (`CL`) went negative on April 20, 2020 (`-37.63`), and the 13-week Treasury yield (`UST13W`) hit zero or negative during low-rate periods. Taking the natural log of price ratios (`ln(P_t / P_{t-1})`) when prices are `<= 0` gives `NaN` or `-inf`, which completely breaks DuckDB's window `median()` function.
  - **The fix:** Added a `close_le_zero` check in step 4, and wrapped the log return formula in step 10 with a `CASE WHEN` statement so zero/negative prices just return `NULL` instead of crashing.

- Fixed a couple of annoying pandas/SQL aggregation bugs after checking the first output:
  1. Stripped out leading SQL comments (`--`) so table creations (`r`, `r2`, `r3`) don't accidentally spit out useless row counts into the CSV.
  2. Fixed how multi-row checks (`missing_weekdays`, `flat_bars`, `spike_reversals`, etc.) get routed by column name *before* checking if the dataframe has only 1 row. (Otherwise, assets with just 1 flat year or 1 spike were creating messy random columns instead of adding up nicely).
  3. Simplified check 3 to just count weekend rows (`dayofweek in (0, 6)`).

- Re-ran the whole batch across all 58 files -> **0 errors**, and a neat `58 x 18` summary table got saved successfully to `data/clean/yahoo-clean/data_quality_report.csv`.


### Main data issues caught by the QA report (to fix in the cleaning engine next):
- **Duplicates & Nulls:** Exactly `0` duplicate dates and `0` missing values across the whole universe.
- **Weekend bars:** Only `RB` has `1` stray weekend row; everything else is clean.
- **Negative / zero closes (`close_le_zero`):** Just `CL` (1 row for negative oil in April 2020) and `UST13W` (7 rows).
- **Decimal shift on `6J`:** `max_abs_log_ret` is `2.3064` (a massive 10x single-day jump) with `3` spike reversals. Definitely a decimal-place glitch in Yahoo's JPY futures data.
- **Yields vs. Prices (`UST13W`, `UST5Y`, `UST10Y`, `UST30Y`):** Taking log returns on yield percentages near zero causes huge spikes (`UST13W` shows `37` spike reversals). For the backtester, I'll need to use simple basis-point changes (`y_t - y_{t-1}`) or convert them to proper bond prices.
- **Bad OHLC bars (`Low > Open/Close` or `High < Open/Close`):** ETFs and indices are totally clean (`0`), but continuous ags/metals futures have a bunch (`ZS`: 847, `ZW`: 835, `ZC`: 831, `ZL`: 709, `KC`: 506, `CC`: 458, `GC`: 441) along with spot FX (`USDJPY`: 199).

*(Next step: update my cleaning script to patch these issues before I start backtesting).*

## 7 nov 2026 (Part 3):
- Implement initial cleaning_engine.py with fail-closed market locks (EEM) and timestamped logging;
- Update locks.md to reflect active programmatic enforcement of market locks".