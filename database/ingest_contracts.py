import duckdb
import yaml
from pathlib import Path

def ingest_contracts_meta(duckdb_path: str = "data/commodex.duckdb", yaml_path: str = "contracts_meta.yaml"):
    with open(yaml_path, "r") as f:
        meta = yaml.safe_load(f)
        
    contracts = meta.get("contracts", [])
    if not contracts:
        print("No contracts found in YAML.")
        return
        
    conn = duckdb.connect(duckdb_path)
    
    # We use INSERT OR REPLACE for idempotency
    for c in contracts:
        # Default expiry window logic if not specified in YAML (since YAML doesn't have it explicitly yet)
        # GoldM: 3-5, others 27-31
        window = "3-5" if c["symbol"] == "GOLDM" else "27-31"
        
        conn.execute("""
            INSERT INTO contract_meta (symbol, lot_grams, quote_grams, purity, expiry_window)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (symbol) DO UPDATE SET
                lot_grams = excluded.lot_grams,
                quote_grams = excluded.quote_grams,
                purity = excluded.purity,
                expiry_window = excluded.expiry_window
        """, (
            c["symbol"],
            c["trading_unit_grams"],
            c["quote_grams"],
            c["purity"],
            window
        ))
        
    conn.close()
    print(f"Ingested {len(contracts)} contracts into {duckdb_path}.")

if __name__ == "__main__":
    ingest_contracts_meta()
