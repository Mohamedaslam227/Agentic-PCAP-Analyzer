-- Enable required extensions (must run once per database)
CREATE EXTENSION IF NOT EXISTS "pgvector";
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

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
    -- capture_type: raw_80211 | capwap | ip_mgmt | mixed
    -- Set by pipeline after analysing the first chunk.
    -- Drives which analysis modules the agent uses.
    capture_type    TEXT DEFAULT 'unknown',
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
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      TEXT NOT NULL,
    bssid           TEXT NOT NULL,
    ssid            TEXT,
    -- Vendor resolved from BSSID OUI (Ruckus / Cisco / Juniper Mist / etc.)
    vendor          TEXT,
    -- WiFi generation: 802.11a/b/g/n/ac/ax/be (highest advertised)
    wifi_generation TEXT,
    channel         INT,
    band            TEXT,
    -- 802.11k/v/r roaming capabilities
    dot11k          BOOLEAN DEFAULT FALSE,
    dot11r          BOOLEAN DEFAULT FALSE,
    dot11v          BOOLEAN DEFAULT FALSE,
    -- WiFi 6 / 6E specific
    wifi6_capable   BOOLEAN DEFAULT FALSE,   -- wlan_radio.11ax.mcs present
    bss_color       INT,                     -- BSS Color (0-63) for spatial reuse
    -- VHT / HT channel width
    max_chan_width   TEXT,   -- '20MHz' | '40MHz' | '80MHz' | '160MHz' | '80+80MHz'
    -- Security
    akm_type        INT,    -- 1=WPA2-PSK, 2=802.1X, 6=WPA3-SAE, 8=SAE+OWE
    group_cipher    INT,    -- 2=TKIP, 4=CCMP, 8=GCMP-128
    client_count    INT DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
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

-- ── 802.1X / EAP exchange events ─────────────────────────────────────────────
-- Tracks each EAP exchange (Identity, TLS, PEAP, FAST, etc.) and 4-way
-- EAPOL handshake messages. Critical for diagnosing enterprise auth failures
-- in Cisco ISE, Juniper Mist, and Ruckus Cloudpath environments.
CREATE TABLE IF NOT EXISTS wifi_eap_events (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      TEXT NOT NULL,
    timestamp       FLOAT,
    client_mac      TEXT,
    bssid           TEXT,
    -- eap.code: 1=Request 2=Response 3=Success 4=Failure
    eap_code        INT,
    -- eap.type: 1=Identity 13=TLS 21=TTLS 25=PEAP 43=FAST
    eap_type        INT,
    eap_type_name   TEXT,
    -- wlan_rsna_eapol.keydes.msgnr: 1-4 (4-way handshake step)
    eapol_msg_nr    INT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── CAPWAP tunnel events ──────────────────────────────────────────────────────
-- Populated when capture_type = 'capwap' or 'mixed'.
-- Tracks CAPWAP-Control keepalive failures, radio restarts, and BSS state
-- changes seen in Ruckus SmartZone and Cisco Catalyst Center captures.
CREATE TABLE IF NOT EXISTS capwap_events (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      TEXT NOT NULL,
    timestamp       FLOAT,
    -- capwap.header.rid: radio ID on the AP
    radio_id        INT,
    -- capwap.header.wbid: 1=802.11
    wbid            INT,
    -- capwap.preamble.type: 0=CAPWAP Data, 1=DTLS Data
    payload_type    INT,
    src_ip          TEXT,
    dst_ip          TEXT,
    event_note      TEXT,    -- e.g. 'keepalive', 'bss_disable', 'radio_reset'
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── AP capability detail (one row per AP per session) ────────────────────────
-- Stores the detailed WiFi generation capabilities derived from beacons and
-- radiotap headers. Used by the agent for per-vendor root-cause analysis.
CREATE TABLE IF NOT EXISTS ap_capabilities (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      TEXT NOT NULL,
    bssid           TEXT NOT NULL,
    vendor          TEXT,           -- From OUI lookup (Ruckus/Cisco/Juniper/…)
    -- WiFi 6 / 6E (802.11ax) HE fields
    he_mcs_max      INT,            -- Highest HE MCS seen in radiotap
    he_bw_max       INT,            -- Highest HE bandwidth (MHz)
    bss_color       INT,            -- BSS Color (0-63; 0=disabled)
    -- 802.11ac (VHT)
    vht_chan_width   INT,            -- 0=20/40, 1=80, 2=160, 3=80+80
    -- 802.11n (HT)
    ht_chan_width    INT,            -- 0=20MHz, 1=40MHz
    -- Security suite
    akm_type        INT,
    group_cipher    INT,
    -- Roaming support
    dot11k          BOOLEAN DEFAULT FALSE,
    dot11r          BOOLEAN DEFAULT FALSE,
    dot11v          BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(session_id, bssid)
);

-- ── Network Knowledge Graph ──────────────────────────────────────────────────
-- Node table – every named entity in the network
-- node_type: 'client' | 'ap' | 'channel' | 'ssid' | 'vendor'
--            | 'flow'  | 'auth_event' | 'disconnect_event' | 'roam_event'
CREATE TABLE IF NOT EXISTS entity_nodes (
    node_id    SERIAL PRIMARY KEY,
    session_id TEXT         NOT NULL,
    node_type  VARCHAR(30)  NOT NULL,
    node_value VARCHAR(255) NOT NULL,
    metadata   JSONB        DEFAULT '{}',
    created_at TIMESTAMPTZ  DEFAULT NOW(),
    UNIQUE (session_id, node_type, node_value)
);

-- Edge table – directed, typed relationships between nodes
-- relation: 'connected_to' | 'roamed_to' | 'generated' | 'operates_on'
--           | 'broadcasts'   | 'has_vendor' | 'occurs_on'
--           | 'involves'     | 'from'       | 'to'
CREATE TABLE IF NOT EXISTS entity_edges (
    edge_id    SERIAL PRIMARY KEY,
    session_id TEXT         NOT NULL,
    source_id  INTEGER      NOT NULL REFERENCES entity_nodes(node_id) ON DELETE CASCADE,
    target_id  INTEGER      NOT NULL REFERENCES entity_nodes(node_id) ON DELETE CASCADE,
    relation   VARCHAR(50)  NOT NULL,
    weight     FLOAT        DEFAULT 1.0,
    metadata   JSONB        DEFAULT '{}',
    created_at TIMESTAMPTZ  DEFAULT NOW()
);

-- Session-level summary (human-readable narrative + Level-2 embedding)
CREATE TABLE IF NOT EXISTS session_summaries (
    summary_id   SERIAL PRIMARY KEY,
    session_id   TEXT UNIQUE  NOT NULL,
    summary_text TEXT         NOT NULL,
    embedding    vector(384),
    generated_at TIMESTAMPTZ  DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_flows_session      ON wifi_flows(session_id);
CREATE INDEX IF NOT EXISTS idx_flows_embedding    ON wifi_flows
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_auth_session       ON wifi_auth_events(session_id);
CREATE INDEX IF NOT EXISTS idx_disconnect_session ON wifi_disconnect_events(session_id);
CREATE INDEX IF NOT EXISTS idx_roaming_session    ON wifi_roaming_events(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_id        ON sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_eap_session        ON wifi_eap_events(session_id);
CREATE INDEX IF NOT EXISTS idx_capwap_session     ON capwap_events(session_id);
CREATE INDEX IF NOT EXISTS idx_ap_cap_session     ON ap_capabilities(session_id);
CREATE INDEX IF NOT EXISTS idx_aps_session        ON wifi_access_points(session_id);
CREATE INDEX IF NOT EXISTS idx_clients_session    ON wifi_clients(session_id);
-- Knowledge Graph indexes
CREATE INDEX IF NOT EXISTS idx_entity_nodes_session ON entity_nodes(session_id);
CREATE INDEX IF NOT EXISTS idx_entity_nodes_type    ON entity_nodes(session_id, node_type);
CREATE INDEX IF NOT EXISTS idx_entity_nodes_value   ON entity_nodes(session_id, node_value);
CREATE INDEX IF NOT EXISTS idx_entity_edges_session ON entity_edges(session_id);
CREATE INDEX IF NOT EXISTS idx_entity_edges_source  ON entity_edges(source_id, relation);
CREATE INDEX IF NOT EXISTS idx_entity_edges_target  ON entity_edges(target_id, relation);
CREATE INDEX IF NOT EXISTS idx_entity_edges_rel     ON entity_edges(session_id, relation);
-- Session summaries (ANN search for cross-session similarity)
CREATE INDEX IF NOT EXISTS idx_session_summaries_emb ON session_summaries
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10);