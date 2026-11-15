-- Diagnostics on the 7 Nov Yahoo download (read-only, DuckDB).
-- Replace RAW with the session folder and check each file name against the manifest's `file` column.
-- These queries only LOOK. Nothing is rewritten. Findings go to the issues table at step 3.

-- 1. RB: which day is the weekend row, and what is around it?
SELECT Date, dayname(Date) AS weekday, Open, High, Low, Close, Volume
FROM read_csv('RAW/RB.csv')
WHERE dayofweek(Date) IN (0, 6);          -- 0 = Sunday, 6 = Saturday

-- 2. CL: the non-positive close and the days around it (expected: 20 Apr 2020, -37.63)
SELECT Date, Close, Volume
FROM read_csv('RAW/CL.csv')
WHERE Date BETWEEN DATE '2020-04-14' AND DATE '2020-04-24'
ORDER BY Date;

-- 3. The 5 largest daily moves WITH their dates (repeat for EURUSD, USDJPY, 6J, ZB, ZC, MOVE, UST13W)
WITH p AS (SELECT Date, Close FROM read_csv('RAW/EURUSD.csv') WHERE Close > 0),
r AS (SELECT Date, Close, lag(Close) OVER (ORDER BY Date) AS prev,
             ln(Close / lag(Close) OVER (ORDER BY Date)) AS ret FROM p)
SELECT Date, prev, Close, round(ret, 4) AS ret
FROM r WHERE ret IS NOT NULL
ORDER BY abs(ret) DESC LIMIT 5;

-- 4. Twin check: spot EURUSD vs CME 6E (same risk, different source and different clock).
--    Small gaps are normal (spot cut-off ~midnight UTC, 6E settles 14:00 Chicago). Gaps above 3% are prints.
WITH a AS (SELECT Date, ln(Close / lag(Close) OVER (ORDER BY Date)) AS ret_spot FROM read_csv('RAW/EURUSD.csv')),
b AS (SELECT Date, ln(Close / lag(Close) OVER (ORDER BY Date)) AS ret_fut  FROM read_csv('RAW/6E.csv'))
SELECT a.Date, round(ret_spot, 4) AS ret_spot, round(ret_fut, 4) AS ret_fut,
       round(ret_spot - ret_fut, 4) AS gap
FROM a JOIN b USING (Date)
WHERE abs(ret_spot - ret_fut) > 0.03
ORDER BY abs(ret_spot - ret_fut) DESC;
-- Same pattern: USDJPY vs 6J (note USDJPY is JPY per USD, 6J is USD per JPY: compare ret_spot with -ret_fut),
-- SPY vs ES, QQQ vs NQ, GLD vs GC, SLV vs SI.

-- 5. Yield indices with volume > 0 (an index should have none)
SELECT Date, Open, High, Low, Close, Volume
FROM read_csv('RAW/UST10Y.csv')
WHERE Volume > 0
ORDER BY Date;

-- 6. Inconsistent OHLC bars by year (ZS): if they stop around 2015, they are a pit-era artefact
SELECT year(Date) AS yr, count(*) AS ohlc_bad
FROM read_csv('RAW/ZS.csv')
WHERE High < greatest(Open, Close) OR Low > least(Open, Close) OR High < Low
GROUP BY yr ORDER BY yr;