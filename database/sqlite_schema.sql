-- Application state (SQLite)

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,               -- argon2id, never returned by the API
  role TEXT NOT NULL DEFAULT 'viewer',       -- 'viewer' | 'analyst' | 'admin'
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS login_attempts (
  username TEXT, ip TEXT, attempted_at TEXT NOT NULL, success INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS role_audit (
  id INTEGER PRIMARY KEY, user_id INTEGER, changed_by INTEGER,
  old_role TEXT, new_role TEXT, changed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alert_subscription (
  user_id INTEGER, pair TEXT, z_threshold REAL, min_liquidity TEXT
);

CREATE TABLE IF NOT EXISTS alert_log (
  id INTEGER PRIMARY KEY, as_of DATE, pair TEXT, z REAL, reason TEXT, created_at TEXT
);
