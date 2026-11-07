7 nov 2026:
- fixed some bugs in checks.sql;
- created an engine in python that runs checks.sql;
- tested the checks.sql through duckdb on SPY and got this result (I must still fix some bugs):
S C:\dev\personal_projects\my-deep-project> python .\data\run_checks.py


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

ERROR in statement 8: Parser Error: syntax error at or near "count"

LINE 4: count(*) filter (where "Volume" <10) as vol_below_10
        ^^^^^
Traceback (most recent call last):
  File "C:\dev\personal_projects\my-deep-project\data\run_checks.py", line 18, in <module>
    result = connection.execute(statement)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_duckdb.ParserException: Parser Error: syntax error at or near "count"

LINE 4: count(*) filter (where "Volume" <10) as vol_below_10 