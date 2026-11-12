CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY
);
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    request_key TEXT NOT NULL UNIQUE,
    fingerprint TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('analyzing','ready','merging','complete','failed')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    result_json TEXT,
    error TEXT
);
INSERT OR IGNORE INTO schema_migrations(version) VALUES (1);

