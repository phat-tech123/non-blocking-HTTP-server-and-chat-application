PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    password_hash TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS peers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    peer_uuid TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    ip TEXT NOT NULL,
    port INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    last_seen TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (peer_uuid) REFERENCES users (user_id) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS peer_connections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_peer_id INTEGER NOT NULL,
    to_peer_id INTEGER NOT NULL,
    from_user_id TEXT NOT NULL,
    to_user_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'CONNECTED',
    created_at TEXT NOT NULL,
    UNIQUE (from_peer_id, to_peer_id),
    UNIQUE (from_user_id, to_user_id),
    FOREIGN KEY (from_peer_id) REFERENCES peers (id),
    FOREIGN KEY (to_peer_id) REFERENCES peers (id),
    FOREIGN KEY (from_user_id) REFERENCES users (user_id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (to_user_id) REFERENCES users (user_id) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_by INTEGER NOT NULL,
    created_by_user_id TEXT NOT NULL,
    is_private INTEGER NOT NULL DEFAULT 0,
    access_policy TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (created_by) REFERENCES peers (id),
    FOREIGN KEY (created_by_user_id) REFERENCES users (user_id) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS channel_members (
    channel_id INTEGER NOT NULL,
    peer_id INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'member',
    joined_at TEXT NOT NULL,
    PRIMARY KEY (channel_id, user_id),
    UNIQUE (channel_id, peer_id),
    FOREIGN KEY (channel_id) REFERENCES channels (id),
    FOREIGN KEY (peer_id) REFERENCES peers (id),
    FOREIGN KEY (user_id) REFERENCES users (user_id) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id INTEGER,
    sender_peer_id INTEGER NOT NULL,
    sender_user_id TEXT NOT NULL,
    target_peer_id INTEGER,
    target_user_id TEXT,
    message_type TEXT NOT NULL,
    body TEXT NOT NULL,
    immutable INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    FOREIGN KEY (channel_id) REFERENCES channels (id),
    FOREIGN KEY (sender_peer_id) REFERENCES peers (id),
    FOREIGN KEY (target_peer_id) REFERENCES peers (id),
    FOREIGN KEY (sender_user_id) REFERENCES users (user_id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (target_user_id) REFERENCES users (user_id) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    peer_id INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    message_id INTEGER NOT NULL,
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (peer_id) REFERENCES peers (id),
    FOREIGN KEY (user_id) REFERENCES users (user_id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (message_id) REFERENCES messages (id)
);

CREATE INDEX IF NOT EXISTS idx_users_status ON users (status);

CREATE INDEX IF NOT EXISTS idx_peers_status ON peers (status);

CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages (channel_id, id DESC);

CREATE INDEX IF NOT EXISTS idx_peer_connections_from_user ON peer_connections (from_user_id, status);

CREATE INDEX IF NOT EXISTS idx_peer_connections_to_user ON peer_connections (to_user_id, status);

CREATE INDEX IF NOT EXISTS idx_channel_members_user ON channel_members (user_id, channel_id);

CREATE INDEX IF NOT EXISTS idx_messages_sender_user ON messages (sender_user_id, id DESC);

CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications (user_id, is_read);

CREATE INDEX IF NOT EXISTS idx_notifications_peer ON notifications (peer_id, is_read);