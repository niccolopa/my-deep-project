import duckdb
import sqlparse
import pandas as pd
from pathlib import Path

# 1. Define Paths
base_dir = Path(r"C:\dev\personal_projects\my-deep-project")
session_folder = base_dir / "data" / "clean" / "yahoo-clean" / "2026-11-07_115132_universe"
sql_file = Path(__file__).parent / "checks.sql"

output_dir = base_dir / "data" / "clean" / "yahoo-clean"
output_report = output_dir / "data_quality_report.csv"

# 2. Parse the SQL file
sql = sql_file.read_text(encoding="utf-8")
statements = [stmt.strip() for stmt in sqlparse.split(sql) if stmt.strip()]

connection = duckdb.connect()
csv_files = sorted(session_folder.glob("*_daily_raw.csv"))
print(f"Running checks on {len(csv_files)} files...")

all_results = []

# 3. Execute and Aggregate
for file_path in csv_files:
    symbol = file_path.name.replace("_daily_raw.csv", "")
    connection.execute(f"CREATE OR REPLACE TABLE p AS SELECT * FROM read_csv('{file_path.as_posix()}');")
    
    row_data = {"symbol": symbol}
    
    for i, statement in enumerate(statements, 1):
        # Strip leading SQL comments to accurately detect CREATE statements
        clean_stmt = "\n".join(
            line for line in statement.splitlines() if not line.strip().startswith("--")
        ).strip()
        
        try:
            if clean_stmt.upper().startswith("CREATE"):
                connection.execute(statement)
                continue
                
            result = connection.execute(statement)
            if result.description:
                df = result.df()
                cols = set(df.columns)
                
                # Route multi-row / anomaly checks by column structure FIRST
                if "missing" in cols:
                    row_data["missing_weekdays"] = int(df["missing"].sum()) if not df.empty else 0
                elif "flat" in cols:
                    row_data["flat_bars"] = int(df["flat"].sum()) if not df.empty else 0
                elif "n" in cols and "Date" in cols:
                    row_data["duplicate_dates"] = int(df["n"].sum()) if not df.empty else 0
                elif "z" in cols:
                    row_data["spike_reversals"] = len(df)
                elif "ret" in cols and "z" not in cols:
                    # Check 11: top 5 biggest moves -> record max absolute log return
                    row_data["max_abs_log_ret"] = float(df["ret"].abs().max()) if not df.empty else 0.0
                elif len(df) == 1:
                    # True 1-row summary checks (Checks 1, 3, 4, 5, 7, 9)
                    for col in df.columns:
                        row_data[col] = df[col].iloc[0]
                        
        except Exception as e:
            print(f"ERROR in {symbol}, statement {i}: {e}")
            
    all_results.append(row_data)

connection.close()

# 4. Build and Save the DataFrame
report_df = pd.DataFrame(all_results).fillna(0)
output_dir.mkdir(parents=True, exist_ok=True)
report_df.to_csv(output_report, index=False)

print(f"Done! Quality report saved to:\n{output_report}")