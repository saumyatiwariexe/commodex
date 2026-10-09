import duckdb
import sqlite3
from pathlib import Path
import os

def setup_databases(data_dir: str = "data"):
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    
    duckdb_path = Path(data_dir) / "commodex.duckdb"
    sqlite_path = Path(data_dir) / "commodex.sqlite"
    
    # Setup DuckDB
    duck_conn = duckdb.connect(str(duckdb_path))
    with open("database/duckdb_schema.sql", "r") as f:
        duck_conn.execute(f.read())
    duck_conn.close()
    
    # Setup SQLite
    sqlite_conn = sqlite3.connect(str(sqlite_path))
    with open("database/sqlite_schema.sql", "r") as f:
        sqlite_conn.executescript(f.read())
    sqlite_conn.close()
    
    print(f"Databases setup complete in {data_dir}/")

if __name__ == "__main__":
    setup_databases()
