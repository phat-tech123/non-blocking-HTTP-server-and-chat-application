-- Time helper format:

-- 0) users: tự điền created_at / updated_at khi insert
CREATE TRIGGER IF NOT EXISTS trg_users_ai_fill_time
AFTER INSERT ON users
FOR EACH ROW
BEGIN
    UPDATE users
    SET
        created_at = CASE
            WHEN NEW.created_at IS NULL OR TRIM(NEW.created_at) = ''
            THEN STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')
            ELSE NEW.created_at
        END,
        updated_at = CASE
            WHEN NEW.updated_at IS NULL OR TRIM(NEW.updated_at) = ''
            THEN STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')
            ELSE NEW.updated_at
        END
    WHERE user_id = NEW.user_id;
END;

-- 0.1) users: tự cập nhật updated_at mỗi khi row bị update
CREATE TRIGGER IF NOT EXISTS trg_users_au_touch_updated_at
AFTER UPDATE ON users
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE users
    SET updated_at = STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')
    WHERE user_id = NEW.user_id;
END;

-- 1) peers: tự điền created_at / updated_at / last_seen khi insert
CREATE TRIGGER IF NOT EXISTS trg_peers_ai_fill_time
AFTER INSERT ON peers
FOR EACH ROW
BEGIN
    UPDATE peers
    SET
        created_at = CASE
            WHEN NEW.created_at IS NULL OR TRIM(NEW.created_at) = ''
            THEN STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')
            ELSE NEW.created_at
        END,
        updated_at = CASE
            WHEN NEW.updated_at IS NULL OR TRIM(NEW.updated_at) = ''
            THEN STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')
            ELSE NEW.updated_at
        END,
        last_seen = CASE
            WHEN NEW.last_seen IS NULL OR TRIM(NEW.last_seen) = ''
            THEN STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')
            ELSE NEW.last_seen
        END
    WHERE id = NEW.id;
END;

-- 2) peers: tự cập nhật updated_at mỗi khi row bị update
CREATE TRIGGER IF NOT EXISTS trg_peers_au_touch_updated_at
AFTER UPDATE ON peers
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE peers
    SET updated_at = STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')
    WHERE id = NEW.id;
END;

-- 3) peers: nếu thay đổi ip/port/status thì tự touch last_seen
CREATE TRIGGER IF NOT EXISTS trg_peers_au_touch_last_seen
AFTER UPDATE OF ip, port, status ON peers
FOR EACH ROW
WHEN NEW.last_seen = OLD.last_seen
BEGIN
    UPDATE peers
    SET
        last_seen = STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now'),
        updated_at = STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')
    WHERE id = NEW.id;
END;

-- 4) peer_connections: tự điền created_at khi insert
CREATE TRIGGER IF NOT EXISTS trg_peer_connections_ai_fill_created_at
AFTER INSERT ON peer_connections
FOR EACH ROW
BEGIN
    UPDATE peer_connections
    SET created_at = CASE
        WHEN NEW.created_at IS NULL OR TRIM(NEW.created_at) = ''
        THEN STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')
        ELSE NEW.created_at
    END
    WHERE id = NEW.id;
END;

-- 5) channels: tự điền created_at khi insert
CREATE TRIGGER IF NOT EXISTS trg_channels_ai_fill_created_at
AFTER INSERT ON channels
FOR EACH ROW
BEGIN
    UPDATE channels
    SET created_at = CASE
        WHEN NEW.created_at IS NULL OR TRIM(NEW.created_at) = ''
        THEN STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')
        ELSE NEW.created_at
    END
    WHERE id = NEW.id;
END;

-- 6) channel_members: tự điền joined_at khi insert
CREATE TRIGGER IF NOT EXISTS trg_channel_members_ai_fill_joined_at
AFTER INSERT ON channel_members
FOR EACH ROW
BEGIN
    UPDATE channel_members
    SET joined_at = CASE
        WHEN NEW.joined_at IS NULL OR TRIM(NEW.joined_at) = ''
        THEN STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')
        ELSE NEW.joined_at
    END
    WHERE channel_id = NEW.channel_id
      AND peer_id = NEW.peer_id;
END;

-- 7) messages: tự điền created_at khi insert
CREATE TRIGGER IF NOT EXISTS trg_messages_ai_fill_created_at
AFTER INSERT ON messages
FOR EACH ROW
BEGIN
    UPDATE messages
    SET created_at = CASE
        WHEN NEW.created_at IS NULL OR TRIM(NEW.created_at) = ''
        THEN STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')
        ELSE NEW.created_at
    END
    WHERE id = NEW.id;
END;

-- 8) notifications: tự điền created_at khi insert
CREATE TRIGGER IF NOT EXISTS trg_notifications_ai_fill_created_at
AFTER INSERT ON notifications
FOR EACH ROW
BEGIN
    UPDATE notifications
    SET created_at = CASE
        WHEN NEW.created_at IS NULL OR TRIM(NEW.created_at) = ''
        THEN STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')
        ELSE NEW.created_at
    END
    WHERE id = NEW.id;
END;

-- 9) peer_connections: đồng bộ from_user_id/to_user_id từ peer id
CREATE TRIGGER IF NOT EXISTS trg_peer_connections_ai_sync_user_id
AFTER INSERT ON peer_connections
FOR EACH ROW
BEGIN
    UPDATE peer_connections
    SET
        from_user_id = COALESCE(
            (SELECT peer_uuid FROM peers WHERE id = NEW.from_peer_id),
            NEW.from_user_id
        ),
        to_user_id = COALESCE(
            (SELECT peer_uuid FROM peers WHERE id = NEW.to_peer_id),
            NEW.to_user_id
        )
    WHERE id = NEW.id;
END;

-- 10) channel_members: đồng bộ user_id từ peer_id
CREATE TRIGGER IF NOT EXISTS trg_channel_members_ai_sync_user_id
AFTER INSERT ON channel_members
FOR EACH ROW
BEGIN
    UPDATE channel_members
    SET user_id = COALESCE(
        (SELECT peer_uuid FROM peers WHERE id = NEW.peer_id),
        NEW.user_id
    )
    WHERE channel_id = NEW.channel_id
      AND peer_id = NEW.peer_id;
END;

-- 11) messages: đồng bộ sender_user_id/target_user_id từ peer_id
CREATE TRIGGER IF NOT EXISTS trg_messages_ai_sync_user_id
AFTER INSERT ON messages
FOR EACH ROW
BEGIN
    UPDATE messages
    SET
        sender_user_id = COALESCE(
            (SELECT peer_uuid FROM peers WHERE id = NEW.sender_peer_id),
            NEW.sender_user_id
        ),
        target_user_id = CASE
            WHEN NEW.target_peer_id IS NULL THEN NEW.target_user_id
            ELSE COALESCE(
                (SELECT peer_uuid FROM peers WHERE id = NEW.target_peer_id),
                NEW.target_user_id
            )
        END
    WHERE id = NEW.id;
END;

-- 12) notifications: đồng bộ user_id từ peer_id
CREATE TRIGGER IF NOT EXISTS trg_notifications_ai_sync_user_id
AFTER INSERT ON notifications
FOR EACH ROW
BEGIN
    UPDATE notifications
    SET user_id = COALESCE(
        (SELECT peer_uuid FROM peers WHERE id = NEW.peer_id),
        NEW.user_id
    )
    WHERE id = NEW.id;
END;