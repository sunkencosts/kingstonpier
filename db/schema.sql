-- ============================================================================
--  readings — THE CONTRACT between the tracker (writer) and the API (reader).
-- ============================================================================
-- The CV worker in tracker/ APPENDS one row per sampling pass. The API in api/
-- only ever READS this table (opened mode=ro). As long as the worker keeps
-- writing these columns, the tracker internals can change freely without
-- touching the API. Integer counts only — no image blobs (privacy stance).
--
-- Keep this file the single source of truth: both the seed script and the
-- future tracker should initialise the DB from it.

CREATE TABLE IF NOT EXISTS readings (
  ts        TEXT    NOT NULL,            -- UTC, ISO-8601 'YYYY-MM-DDTHH:MM:SSZ'
  pier_1    INTEGER NOT NULL DEFAULT 0,  -- raw per-feed counts (kept for analysis;
  pier_2    INTEGER NOT NULL DEFAULT 0,  --   the public site does NOT show these —
  pier_3    INTEGER NOT NULL DEFAULT 0,  --   the 5 feeds overlap and double-count)
  pier_4    INTEGER NOT NULL DEFAULT 0,
  pier_5    INTEGER NOT NULL DEFAULT 0,
  total     INTEGER NOT NULL,            -- combined count the dashboard shows
  feeds_ok  INTEGER NOT NULL DEFAULT 0   -- how many of the 5 feeds responded (0–5)
);

-- Reads are almost always "recent rows, newest first" and "rows since T".
CREATE INDEX IF NOT EXISTS idx_readings_ts ON readings (ts);
