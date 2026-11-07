import duckdb
import sqlparse
from pathlib import Path

sql_file = Path(__file__).parent / "checks.sql"

connection = duckdb.connect()

sql = sql_file.read_text(encoding="utf-8")

for i, statement in enumerate(sqlparse.split(sql), 1):
    statement = statement.strip()

    if not statement:
        continue

    try:
        result = connection.execute(statement)

        if result.description:
            print(f"\n--- RESULT {i} ---")
            print(result.df().to_string(index=False))

    except Exception as e:
        print(f"\nERROR in statement {i}: {e}")
        raise

connection.close()

print("\nAll checks completed.")
