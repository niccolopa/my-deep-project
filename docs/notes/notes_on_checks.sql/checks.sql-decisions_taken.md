# Decisions taken on checks.sql:
## Why the spike check (the 10th) is built this way:
The check uses a log returns instead of a percentage returns because up and down moves cancel exactly. If a price goes from 100 to 110 and back to 100: 
- in percentages the moves are +10% and -9.09%, so they don't cancel;
- in logs, they are +0.0953 and -0.0953, so they do.
Log return returns also up over time, so the return over several days is simply the sum of the daily ones. Teh only cost is that the log of a price at or below zero does not exist, so those days are left empty.

To decide what a normal move is, it uses the "median and the MAD" (the median distance from the median) instead of the mean and the standard deviation. A single bad price would inflate the standard deviation and end up making itself look normal, while the median barely moves. Multipliyng the MAD by 1.4826 makes it equal to the standard deviation when the data is normally distributed, so it can be read the same way.

A day is flegged only when a huge move is reversed the next day: the next move goes in the opposite direction and undoes at least half of it. A real crash tend to stay down; a wrong price comes back. Without this second cpondition, every real crash would look like an error.

Normal is measured over a rolling window of 250 trading days about one year, instead of the whole history because volatility changes over time, eg: a quiet 2017 should not judge a stressed 2008. At least 60 days of history are required, so the estimate never rests on a handful of points.

The threshold is 8, not 3, standard deviations:
- if returns were normal, a move beyond 3 would happen on about 0.3% of days, roughly once every year and half, and real markets, with their fat tails, produce such moves even more often.
- A move beyond 8 would pratically never ahppen by chance.

So the check catches only the absurd, not ordinary market stress.

Finally, the check flags but never fixes. The code marks a suspicious day and a person decides what it is. Fixing a price automatically, for example by replacing it with the average of the day before and the day after, would use tomorrow’s price to rewrite today’s. That is look-ahead, the one mistake a backtest must never contain, in my opinion.