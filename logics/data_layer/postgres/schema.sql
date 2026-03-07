CREATE TABLE IF NOT EXISTS users (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username    TEXT UNIQUE NOT NULL,
    email       TEXT UNIQUE NOT NULL,
    password    TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
 
CREATE TABLE IF NOT EXISTS sessions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      TEXT UNIQUE NOT NULL,
    filename        TEXT NOT NULL,
    file_path       TEXT NOT NULL,
    status          TEXT DEFAULT 'pending',
    total_packets   BIGINT DEFAULT 0,
    total_flows     INT DEFAULT 0,
    unique_aps      INT DEFAULT 0,
    unique_clients  INT DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);
 
CREATE TABLE IF NOT EXISTS wifi_flows (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      TEXT NOT NULL,
    bssid           TEXT,
    client_mac      TEXT,
    wifi_band       TEXT,
    channel         INT,
    avg_signal_dbm  FLOAT,
    total_bytes     BIGINT DEFAULT 0,
    frame_count     INT DEFAULT 0,
    retry_count     INT DEFAULT 0,
    embedding       vector(384),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
 
CREATE TABLE IF NOT EXISTS wifi_access_points (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id  TEXT NOT NULL,
    bssid       TEXT NOT NULL,
    ssid        TEXT,
    vendor      TEXT,
    channel     INT,
    band        TEXT,
    dot11k      BOOLEAN DEFAULT FALSE,
    dot11r      BOOLEAN DEFAULT FALSE,
    dot11v      BOOLEAN DEFAULT FALSE,
    client_count INT DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(session_id, bssid)
);
 
CREATE TABLE IF NOT EXISTS wifi_clients (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      TEXT NOT NULL,
    mac_address     TEXT NOT NULL,
    vendor          TEXT,
    connected_bssid TEXT,
    signal_dbm      FLOAT,
    band            TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(session_id, mac_address)
);
 
CREATE TABLE IF NOT EXISTS wifi_auth_events (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id  TEXT NOT NULL,
    timestamp   FLOAT,
    client_mac  TEXT,
    bssid       TEXT,
    auth_type   TEXT,
    status      TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
 
CREATE TABLE IF NOT EXISTS wifi_disconnect_events (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      TEXT NOT NULL,
    timestamp       FLOAT,
    client_mac      TEXT,
    bssid           TEXT,
    reason_code     INT,
    reason_text     TEXT,
    initiated_by    TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
 
CREATE TABLE IF NOT EXISTS wifi_roaming_events (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      TEXT NOT NULL,
    timestamp       FLOAT,
    client_mac      TEXT,
    from_bssid      TEXT,
    to_bssid        TEXT,
    roam_type       TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
 
CREATE TABLE IF NOT EXISTS chat_messages (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id  TEXT NOT NULL,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
 
CREATE TABLE IF NOT EXISTS research_jobs (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id      TEXT UNIQUE NOT NULL,
    session_id  TEXT NOT NULL,
    question    TEXT,
    status      TEXT DEFAULT 'pending',
    result      TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);
 
CREATE TABLE IF NOT EXISTS wifi_anomalies (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id  TEXT NOT NULL,
    anomaly_type TEXT,
    description TEXT,
    severity    TEXT,
    bssid       TEXT,
    client_mac  TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
 
-- Indexes
CREATE INDEX IF NOT EXISTS idx_flows_session     ON wifi_flows(session_id);
CREATE INDEX IF NOT EXISTS idx_flows_embedding   ON wifi_flows 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_auth_session      ON wifi_auth_events(session_id);
CREATE INDEX IF NOT EXISTS idx_disconnect_session ON wifi_disconnect_events(session_id);
CREATE INDEX IF NOT EXISTS idx_roaming_session   ON wifi_roaming_events(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_id       ON sessions(session_id);