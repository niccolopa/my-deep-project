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