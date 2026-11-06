import duckdb
with = duckdb.connect()
with.sql("SELECT 42 AS test").show()