--1) size and dates:
SELECT count(*) as rows, min("Date") as first, max("Date") as last from p;

--2) duplicate dates (expected result= nothing):
select "Date", count(*) as n from p group by "Date" having count(*) >1;

--3) weekend rows (0=Sunday, 6=Saturday):
select count(*) filter (where dayofweek("Date") in (0, 6)) as weekend_rows from p;

--4) missing or non-positive values per column:
select
count(*) filter (where "Close" is null) as close_null,
count(*) filter (where "Open" is null) as open_null,
count(*) filter (where "Volume" is null) as volume_null,
count(*) filter (where "Close" <= 0) as close_le_zero
from p;

--5) inconsistent prices: open or close outside high-low:
select count(*) as ohlc_bad from p
where "Low" > least("Open", "Close") or "High" < greatest("Open", "Close") or "High" < "Low";

--6) flat bars (high=low), by year:
select year("Date") as yr, count(*) as flat from p where "High" = "Low" group by yr order by yr;

--7) zero and tiny volume:
select
count(*) filter (where "Volume" = 0) as vol_zero,
count(*) filter (where "Volume" < 10) as vol_below_10
from p;

--8) weekdays with no row, by year:
with days as (
    select cast(unnest(generate_series(
        cast((select min("Date") from p) as timestamp),
        cast((select max("Date") from p) as timestamp),
    interval 1 day)) as date) as d
)
select YEAR(d) as yr, count(*) as missing
from days
where dayofweek(d) between 1 and 5
and d not in (select "Date" from p)
group by yr order by yr;

--9) stale prices, same close 3 days in a row:
select count(*) as stale_3 from (
    select "Close",
    lag("Close", 1) over (order by "Date") as c1,
    lag("Close", 2) over (order by "Date") as c2
    from p
) where "Close" = c1 and c1 = c2;

--10) spikes: move >8 robust deviations, followed by a substantial reversal:
create or replace table r as
select "Date", "Close",
    case when "Close" > 0 and lag("Close") over (order by "Date") > 0
         then ln("Close" / lag("Close") over (order by "Date"))
         else null
    end as ret
from p;

create or replace table r2 as
select *,
median(ret) over w as med,
count(ret) over w as n
from r
window w as (order by "Date" rows between 249 preceding and current row);

create or replace table r3 as
select *,
       1.4826 * median(abs(ret - med)) OVER w AS mad,
       count(abs(ret - med)) OVER w AS n2
from r2
window w as (order by "Date" rows between 249 preceding and current row);

select "Date", "Close", round(ret, 4) as ret, round(ret / nullif(mad, 0), 1) as z
from (
    select *, lead(ret) over (order by "Date") as next_ret from r3
    where n >= 60 and n2 >= 60
)
where mad > 0 and abs(ret / mad) > 8
and sign(next_ret) = -sign(ret)
and abs(next_ret) > 0.5 * abs(ret);

--11) the five biggest moves:
select "Date", "Close", round(ret, 4) as ret from r order by abs(ret) desc nulls last limit 5;