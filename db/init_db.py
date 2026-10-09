"""
db/init_db.py
=============
Initialise both databases and seed static data.

Usage
-----
    # Initialise from CLI:
    python -m db.init_db --duckdb data/analytics.duckdb --sqlite data/app.sqlite

    # Programmatic (e.g. in tests):
    from db.init_db import init_databases
    init_databases(duckdb_path=":memory:", sqlite_path=":memory:")

What this does
--------------
1. Creates all DuckDB tables via db/schema.py.
2. Seeds ``contract_meta`` from ``contracts_meta.yaml``
   (UPSERT so re-running is safe).
3. Creates all SQLite tables via db/schema.py.

Seeding ``contract_meta`` from YAML keeps the single source of truth in
``contracts_meta.yaml`` (DATA_PIPELINE.md §6, AGENTS.md §7) and avoids
hard-coding values in Python.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import yaml

from db import analytics_conn, app_conn
from db.schema import create_analytics_schema, create_app_schema

logger = logging.getLogger(__name__)

# Default paths — override via CLI or environment
_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_DUCKDB = _REPO_ROOT / "data" / "analytics.duckdb"
_DEFAULT_SQLITE = _REPO_ROOT / "data" / "app.sqlite"
_CONTRACTS_META = _REPO_ROOT / "contracts_meta.yaml"

# Expiry window lookup — derived from DATA_PIPELINE.md §6
# [Likely] correct; verify against MCX spec before the demo.
_EXPIRY_WINDOWS: dict[str, str] = {
    "GOLDM":        "3rd-5th",
    "GOLDTEN":      "27th-31st",
    "GOLDGUINEA":   "27th-31st",
    "GOLDPETAL":    "27th-31st",
}


def _load_contracts_meta() -> list[dict]:
    """Parse contracts_meta.yaml and return a list of row dicts."""
    with _CONTRACTS_META.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    rows = []
    for c in data["contracts"]:
        symbol = c["symbol"].strip().upper()
        rows.append({
            "symbol":        symbol,
            "lot_grams":     float(c["trading_unit_grams"]),
            "quote_grams":   float(c["quote_grams"]),
            "purity":        int(c["purity"]),
            "expiry_window": _EXPIRY_WINDOWS.get(symbol, "unknown"),
        })
    return rows


def _seed_contract_meta(con) -> None:  # type: ignore[no-untyped-def]
    """UPSERT contract_meta rows from contracts_meta.yaml."""
    rows = _load_contracts_meta()
    for row in rows:
        con.execute(
            """
            INSERT INTO contract_meta (symbol, lot_grams, quote_grams, purity, expiry_window)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (symbol) DO UPDATE SET
                lot_grams     = excluded.lot_grams,
                quote_grams   = excluded.quote_grams,
                purity        = excluded.purity,
                expiry_window = excluded.expiry_window
            """,
            [row["symbol"], row["lot_grams"], row["quote_grams"],
             row["purity"], row["expiry_window"]],
        )
    logger.info("Seeded %d rows into contract_meta", len(rows))


def init_databases(
    duckdb_path: str | Path = _DEFAULT_DUCKDB,
    sqlite_path: str | Path = _DEFAULT_SQLITE,
    *,
    seed: bool = True,
) -> None:
    """Create schemas and optionally seed static data.

    Args:
        duckdb_path: Path for the DuckDB analytics database.
                     Use ``":memory:"`` for tests.
        sqlite_path: Path for the SQLite application-state database.
                     Use ``":memory:"`` for tests.
        seed:        If ``True`` (the default), seed ``contract_meta``
                     from ``contracts_meta.yaml``.

    Raises:
        FileNotFoundError: If *seed* is ``True`` and ``contracts_meta.yaml``
                           is not found.
        yaml.YAMLError:    If the YAML cannot be parsed.
    """
    duckdb_path = Path(duckdb_path)
    sqlite_path = Path(sqlite_path)

    # Ensure data/ directory exists for persistent paths
    for p in (duckdb_path, sqlite_path):
        if str(p) != ":memory:":
            p.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Initialising DuckDB at %s", duckdb_path)
    with analytics_conn(duckdb_path) as duck:
        create_analytics_schema(duck)
        if seed:
            _seed_contract_meta(duck)

    logger.info("Initialising SQLite at %s", sqlite_path)
    with app_conn(sqlite_path) as lite:
        create_app_schema(lite)

    logger.info("Database initialisation complete.")


# ── CLI ───────────────────────────────────────────────────────────────────────

def _main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(
        description="Initialise Commodex databases and seed static data."
    )
    parser.add_argument(
        "--duckdb",
        default=str(_DEFAULT_DUCKDB),
        help=f"Path to DuckDB analytics database (default: {_DEFAULT_DUCKDB})",
    )
    parser.add_argument(
        "--sqlite",
        default=str(_DEFAULT_SQLITE),
        help=f"Path to SQLite app-state database (default: {_DEFAULT_SQLITE})",
    )
    parser.add_argument(
        "--no-seed",
        action="store_true",
        help="Skip seeding contract_meta from contracts_meta.yaml",
    )
    args = parser.parse_args()
    init_databases(
        duckdb_path=args.duckdb,
        sqlite_path=args.sqlite,
        seed=not args.no_seed,
    )


if __name__ == "__main__":
    _main()
