CREATE TABLE IF NOT EXISTS commands (
  id TEXT PRIMARY KEY,
  agent_id TEXT NOT NULL,
  action TEXT NOT NULL,
  args_json TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'pending',
  created_at INTEGER NOT NULL,
  sent_at INTEGER,
  started_at REAL,
  finished_at REAL,
  result_json TEXT,
  error TEXT
);

CREATE INDEX IF NOT EXISTS idx_commands_agent_status_created
ON commands(agent_id, status, created_at);

CREATE TABLE IF NOT EXISTS events (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id TEXT NOT NULL,
  ts INTEGER NOT NULL,
  type TEXT NOT NULL,
  command_id TEXT,
  payload_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_events_agent_seq
ON events(agent_id, seq);

CREATE TABLE IF NOT EXISTS agent_state (
  agent_id TEXT PRIMARY KEY,
  connected INTEGER NOT NULL DEFAULT 0,
  last_seen INTEGER NOT NULL,
  browser_url TEXT,
  title TEXT,
  viewport_w INTEGER,
  viewport_h INTEGER,
  screenshot_key TEXT,
  meta_json TEXT NOT NULL DEFAULT '{}'
);
