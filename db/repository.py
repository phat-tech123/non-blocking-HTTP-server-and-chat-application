"""
SQL repository.

- Khởi tạo db schema và trigger.
- Chứa các truy vấn db.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


"""
Trả về timestamp UTC ở dạng ISO-8601 ngay bây giờ.
"""
def _utcnow_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


"""
Đổi kết quả truy vấn SQLite thành dictionary
"""
def _row_to_dict(row):
    if row is None:
        return None

    return dict(row)


"""
Tạo db schema và trigger.
db_path: đường dẫn đến folder db.
"""
def initialize_database(db_path):
    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)

    base_dir = Path(__file__).parent
    schema_path = base_dir / "schema.sql"
    trigger_path = base_dir / "trigger.sql"

    schema_sql = schema_path.read_text(encoding="utf-8")
    trigger_sql = trigger_path.read_text(encoding="utf-8")

    with sqlite3.connect(str(db_file)) as conn:
        conn.executescript("PRAGMA foreign_keys = ON;")
        conn.executescript(schema_sql)
        conn.executescript(trigger_sql)
        conn.commit()


class ChatRepository:
    def __init__(self, db_path):
        self.db_path = db_path

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    """
    Đăng ký hoặc cập nhật heartbeat của peer.
    """
    def upsert_peer(self, ip, port, display_name, peer_uuid=None):
        peer_uuid = peer_uuid or str(uuid4())
        now = _utcnow_iso()

        sql = """
        INSERT INTO peers(peer_uuid, display_name, ip, port, status, last_seen, created_at, updated_at)
        VALUES (?, ?, ?, ?, 'ACTIVE', ?, ?, ?)
        ON CONFLICT(peer_uuid) DO UPDATE SET
            display_name = excluded.display_name,
            ip = excluded.ip,
            port = excluded.port,
            status = 'ACTIVE',
            last_seen = excluded.last_seen,
            updated_at = excluded.updated_at
        """
        with self._connect() as conn:
            conn.execute(sql, (peer_uuid, display_name, ip, port, now, now, now))
            conn.commit()
            row = conn.execute(
                "SELECT * FROM peers WHERE peer_uuid = ?",
                (peer_uuid,),
            ).fetchone()

        return _row_to_dict(row)

    """
    Trả về danh sách peer đang hoạt động
    """
    def list_active_peers(self):
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, peer_uuid, display_name, ip, port, status, last_seen
                FROM peers
                WHERE status = 'ACTIVE'
                ORDER BY id ASC
                """
            ).fetchall()
        return [dict(r) for r in rows]

    """
    Lưu trạng thái kết nối P2P giữa 2 peer (from_peer_id, to_peer_id)
    """
    def register_peer_connection(self, from_peer_id, to_peer_id, status="CONNECTED"):
        now = _utcnow_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO peer_connections(from_peer_id, to_peer_id, status, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(from_peer_id, to_peer_id) DO UPDATE SET
                    status = excluded.status
                """,
                (from_peer_id, to_peer_id, status, now),
            )
            conn.commit()
            row = conn.execute(
                """
                SELECT * FROM peer_connections
                WHERE from_peer_id = ? AND to_peer_id = ?
                """,
                (from_peer_id, to_peer_id),
            ).fetchone()
        return _row_to_dict(row)

    """
    Tạo channel mới và thêm ng tạo vào channel
    """
    def create_channel(self, name, created_by, is_private=False, access_policy=None):
        now = _utcnow_iso()
        policy_json = json.dumps(access_policy or {}, ensure_ascii=False)

        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO channels(name, created_by, is_private, access_policy, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (name, created_by, 1 if is_private else 0, policy_json, now),
            )
            channel_id = cur.lastrowid
            conn.execute(
                """
                INSERT OR IGNORE INTO channel_members(channel_id, peer_id, role, joined_at)
                VALUES (?, ?, 'owner', ?)
                """,
                (channel_id, created_by, now),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM channels WHERE id = ?", (channel_id,)).fetchone()

        data = _row_to_dict(row)
        data["access_policy"] = json.loads(data["access_policy"])
        return data

    """
    Thêm peer (peer_id) vào channel (channel_id) mới
    """
    def join_channel(self, channel_id, peer_id, role="member"):
        now = _utcnow_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO channel_members(channel_id, peer_id, role, joined_at)
                VALUES (?, ?, ?, ?)
                """,
                (channel_id, peer_id, role, now),
            )
            conn.commit()
            row = conn.execute(
                """
                SELECT channel_id, peer_id, role, joined_at
                FROM channel_members
                WHERE channel_id = ? AND peer_id = ?
                """,
                (channel_id, peer_id),
            ).fetchone()

        return _row_to_dict(row)

    """
    Trả về danh sách channel mà peer (peer_id) đã tham gia
    """
    def list_channels_for_peer(self, peer_id):
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT c.id, c.name, c.is_private, c.access_policy, c.created_at, cm.role
                FROM channels c
                JOIN channel_members cm ON c.id = cm.channel_id
                WHERE cm.peer_id = ?
                ORDER BY c.id ASC
                """,
                (peer_id,),
            ).fetchall()

        result = []
        for row in rows:
            item = dict(row)
            item["access_policy"] = json.loads(item["access_policy"])
            result.append(item)
        return result

    """
    Trả về danh sách peer_id của các thành viên trong channel (channel_id)
    """
    def list_channel_member_ids(self, channel_id):
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT peer_id FROM channel_members WHERE channel_id = ?",
                (channel_id,),
            ).fetchall()
        return [int(r["peer_id"]) for r in rows]

    """
    Thêm message
    """
    def insert_message(
        self,
        channel_id,
        sender_peer_id,
        body,
        message_type="BROADCAST",
        target_peer_id=None,
    ):
        now = _utcnow_iso()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO messages(
                    channel_id,
                    sender_peer_id,
                    target_peer_id,
                    message_type,
                    body,
                    immutable,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, 1, ?)
                """,
                (channel_id, sender_peer_id, target_peer_id, message_type, body, now),
            )
            message_id = cur.lastrowid
            conn.commit()
            row = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()

        return _row_to_dict(row)

    """
    Trả về message của channel (channel_id) + sắp xếp theo thứ tự mới đến cũ
    """
    def list_messages(self, channel_id, limit=100):
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, channel_id, sender_peer_id, target_peer_id, message_type, body, created_at
                FROM messages
                WHERE channel_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (channel_id, limit),
            ).fetchall()

        return [dict(r) for r in rows]

    """
    Thêm notification khi có message mới cho peer
    peer_id: máy nhận notification
    """
    def create_notification(self, peer_id, message_id):
        now = _utcnow_iso()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO notifications(peer_id, message_id, is_read, created_at)
                VALUES (?, ?, 0, ?)
                """,
                (peer_id, message_id, now),
            )
            notification_id = cur.lastrowid
            conn.commit()
            row = conn.execute(
                "SELECT * FROM notifications WHERE id = ?",
                (notification_id,),
            ).fetchone()

        return _row_to_dict(row)

    """
    Lấy notifications cho peer (peer_id)
    """
    def list_notifications(self, peer_id, only_unread=True):
        with self._connect() as conn:
            if only_unread:
                rows = conn.execute(
                    """
                    SELECT n.id, n.peer_id, n.message_id, n.is_read, n.created_at, m.body, m.sender_peer_id
                    FROM notifications n
                    JOIN messages m ON m.id = n.message_id
                    WHERE n.peer_id = ? AND n.is_read = 0
                    ORDER BY n.id DESC
                    """,
                    (peer_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT n.id, n.peer_id, n.message_id, n.is_read, n.created_at, m.body, m.sender_peer_id
                    FROM notifications n
                    JOIN messages m ON m.id = n.message_id
                    WHERE n.peer_id = ?
                    ORDER BY n.id DESC
                    """,
                    (peer_id,),
                ).fetchall()

        return [dict(r) for r in rows]

    """
    Đanh dấu notifications đã đọc
    """
    def mark_notifications_read(self, notification_ids):
        if not notification_ids:
            return 0

        placeholders = ",".join("?" for _ in notification_ids)
        sql = "UPDATE notifications SET is_read = 1 WHERE id IN ({})".format(placeholders)

        with self._connect() as conn:
            cur = conn.execute(sql, tuple(notification_ids))
            conn.commit()
            return cur.rowcount