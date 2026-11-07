import duckdb
import sqlparse 
import pandas as pd
from pathlib import Path

# 1. Define Paths
base_dir = Path(r"C:\dev\personal_projects\my-deep-project")                                                        #"base_dir": store the main path to your project folder on your computer
sql_file = Path(__file__).parent / "checks.sql"

output_dir = base_dir / "data" / "clean" / "yahoo-clean"                                                            # "output_dir" and "output_report": Define where the final summary file (data_quality_report.csv) will end up once the script has finished working.
output_report = output_dir / "data_quality_report.csv"                                                              


# 2. Parse the SQL file
sql = sql_file.read_text(encoding="utf-8")                                                                          # sql_file.read_text(...): reads the whole content of check.sql such as a simple text
statements = [stmt.strip() for stmt in sqlparse.split(sql) if stmt.strip()]                                         # sqlparse.split(sql): takes the SQL text and splits it into a list of individual statements (control 1, control 2, etc.), cleaning up the extra whitespace

connection = duckdb.connect()
csv_files = sorted(session_folder.glob("*_daily_raw.csv"))                                                          # session_folder.glob("*_daily_raw.csv"): it searches the folder for all files that end with that name (the 58 assets); the sorted() function puts them in alphabetical order.
print(f"Running checks on {len(csv_files)} files...")

all_results = []                                                                                                    # all_results = []: it creates an empty list. In here I will put a "dictionary" of results for each individual asset analyzed, and then turn it into a table at the end.



# 3. Execute and Aggregate
for file_path in csv_files:                                                                                         # A large loop begins that repeats the same operations for each of the 58 files found.
    symbol = file_path.name.replace("_daily_raw.csv", "")                                                           # symbol = ... extracts asset name from file name   
    connection.execute(f"CREATE OR REPLACE TABLE p AS SELECT * FROM read_csv('{file_path.as_posix()}');")           # connection.execute(...) tells duckdb to read the current csv file and load it into a temporary table called p (like price).
    
    row_data = {"symbol": symbol}                                                                                   # "row_data = {"symbol": symbol}": it creates a dictionary for this asset, starting by putting its symbol (eg. symbol: "SPY"). As I do the checks, I'll add the test results in here.
    
    for i, statement in enumerate(statements, 1):                                                                   #"for i, statement in enumerate(statements, 1):" It does a second internal loop to run all the SQL checks written in the checks.sql file one at a time.
        # Strip leading SQL comments to accurately detect CREATE statements
        clean_stmt = "\n".join(                                                                                     #"clean_stmt = ...": cleans the query by removing comment lines, so it really understands what it's about to do.
            line for line in statement.splitlines() if not line.strip().startswith("--")
        ).strip()
        
        try:                                                                                                        # "try: ... except:"  This is a Python security lock. It says: "Try running this piece of code; if something goes wrong (e.g., corrupted data or mathematical errors), don't block the entire script, but print the error and move on."
            if clean_stmt.upper().startswith("CREATE"):                                                             # "if clean_stmt.upper().startswith("CREATE"):": If the query is to create a temporary support table (as in complex statistical calculations), it executes it and immediately moves on to the next query without looking for results to print.
                connection.execute(statement)
                continue
                
            result = connection.execute(statement)                                                                  # result = connection.execute(statement): Performs the actual SQL check on the asset table.
            if result.description:                                                                                  # if result.description:: Checks whether the query returned any data (a response table).
                df = result.df()                                                                                    # df = result.df(): Transforms the result of the SQL query into a Pandas DataFrame, which is a real Python table.
                cols = set(df.columns)                                                                              # cols = set(df.columns): Takes the names of the columns returned by the query to understand what kind of check I just did.
                
                
                # Route multi-row / anomaly checks by column structure FIRST    # Depending on which SQL check was performed, the results can have different shapes (a single row with counts or a table with dozens of anomalies).
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