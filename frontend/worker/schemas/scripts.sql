-- AXIS user Pine scripts (D1). Apply with:
--   wrangler d1 execute pynescript --file=schemas/scripts.sql
-- Or local:
--   wrangler d1 execute pynescript --local --file=schemas/scripts.sql

CREATE TABLE IF NOT EXISTS scripts (
  user_id TEXT NOT NULL,
  id TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  path TEXT,
  content TEXT NOT NULL,
  revision TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  PRIMARY KEY (user_id, id)
);

CREATE INDEX IF NOT EXISTS idx_scripts_user_updated
  ON scripts (user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS script_drafts (
  user_id TEXT PRIMARY KEY,
  content TEXT NOT NULL,
  name TEXT,
  updated_at INTEGER NOT NULL
);
