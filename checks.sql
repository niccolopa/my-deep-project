-- Data quality checks on one Yahoo daily file, in DuckDB
--

import duckdb
with = duckdb.connect()
with.sql("SELECT 42 AS test").show()

CREATE OR REPLACE TABLE p AS SELECT * FROM read_csv('C:/dev/my-deep-project/data/raw/yahoo-raw/2026-10-22_211506_universe/6A_daily_raw.csv');

--1) size and dates:
SELECT count(*) as rows, min('Date') as first, max("Date") as last from p;

--2) duplicate dates (expected result= nothing):
select "Date", count(*) as n from p group by "Date" having count(*) >1;

-- 3) rows per week (0=Sunday, 6 = Saturday: 0 and 6 must not appear)
select dayofweek("Date") as weekday, count(*) as n from p group by weekday order by weekday;

--4) missing values per column:
select
count(*) filter (where "Close" is null) as close_null,
count(*) filter (where "Open" is null) as open_null,
count(*) filter (where "Volume" is null) as volume_null
from p;

--5. inconsistent prices: open or close outside high-low:
select count(*) as ohlc_bad from p
where "Low" > least("Open", "Close") ore "High" < greatest("Open", "Close") or "High" < "low";

--6) flat bars (high=low), by year:
select year("Date") as yr, count(*) as flat from p where "High" = "low" group by yr order by yr;

--7) zero and ty volume:
select
count(*) filter (where "Volume" = 0) as vol_zero;
count(*) filter (where "Volume" <10) as vol_below_10
from p;

--8) weekdays with no row, by year:
with days as (
    select cast(unnest(generate_series(
        cast((select min("Date") from p) as timestamp),
        cast((select max("Date") from p) as timestamp),
    inetrval 1 day)) as date) as d
)
select years(d) as yr, count(*) as missing
from days
where dayofweek(d) between 1 and 5
and d not in (select "Date" from p)
group by yr order by yr;

--9) stale prices, same close 3 days in a row:
select count(*) as stale_3 from (
    select "Close",
    lag("Close", 1 ) over (order by "Date") as c1,
    lag("Close", 2) over (order by "Date") as c2
    from p
) where "Close" = c1 and c1=c2;

--10. spikes: move >8 robust deviations that reverses the next day:
create or replace table r as
select "Date", "close", ln("Close" / lag("Close") over (order by "Date")) as ret from p;

create or replace table r2 as
select *,
median(ret) over w as med,
count(ret) over w as n
from r
window w as (order by "Date" rows between 249 preceding and current row);

create or replace r3 as
select *,
       1.4826 * median(abs(ret - med)) OVER w AS mad,
       count(abs(ret - med)) OVER w AS n2
from r2
window w as (order by "Date" rows between 249 preceding and current row);

select "Date", "Close", round(ret, 4) as ret, round(ret /mad, 1) as z
from (
    select *, lead(ret) over (order by "Date") as next_ret from r3
    where n >= 60 and n2 >=60
)
where abs(ret/mad) >8
and sign(next_ret) = -sign(ret)
and abs(next_ret) > 0.5*abs(ret);

--11) the five biggest moves:
select "Date", "Close", round(ret, 4) ad ret from r order by abs(ret) desc nulls last limit 5;