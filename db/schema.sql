PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS peers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    peer_uuid TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    ip TEXT NOT NULL,
    port INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    last_seen TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS peer_connections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_peer_id INTEGER NOT NULL,
    to_peer_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'CONNECTED',
    created_at TEXT NOT NULL,
    UNIQUE (from_peer_id, to_peer_id),
    FOREIGN KEY (from_peer_id) REFERENCES peers (id),
    FOREIGN KEY (to_peer_id) REFERENCES peers (id)
);

CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_by INTEGER NOT NULL,
    is_private INTEGER NOT NULL DEFAULT 0,
    access_policy TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (created_by) REFERENCES peers (id)
);

CREATE TABLE IF NOT EXISTS channel_members (
    channel_id INTEGER NOT NULL,
    peer_id INTEGER NOT NULL,
    role TEXT NOT NULL DEFAULT 'member',
    joined_at TEXT NOT NULL,
    PRIMARY KEY (channel_id, peer_id),
    FOREIGN KEY (channel_id) REFERENCES channels (id),
    FOREIGN KEY (peer_id) REFERENCES peers (id)
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id INTEGER,
    sender_peer_id INTEGER NOT NULL,
    target_peer_id INTEGER,
    message_type TEXT NOT NULL,
    body TEXT NOT NULL,
    immutable INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    FOREIGN KEY (channel_id) REFERENCES channels (id),
    FOREIGN KEY (sender_peer_id) REFERENCES peers (id),
    FOREIGN KEY (target_peer_id) REFERENCES peers (id)
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    peer_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (peer_id) REFERENCES peers (id),
    FOREIGN KEY (message_id) REFERENCES messages (id)
);

CREATE INDEX IF NOT EXISTS idx_peers_status ON peers (status);

CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages (channel_id, id DESC);

CREATE INDEX IF NOT EXISTS idx_notifications_peer ON notifications (peer_id, is_read);