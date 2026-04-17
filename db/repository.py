"""
SQL repository.

- Khởi tạo db schema và trigger
- Chứa các truy vấn db
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


"""
Trả về timestamp UTC ở dạng ISO-8601 ngay bây giờ
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
Tạo db schema và trigger
db_path: đường dẫn đến folder db
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
    Truy vấn table user
    - create_user: Tạo user mới
    - get_user_id_by_peer_id: Lấy user_id từ peer_id hiện tại
    - get_user_by_id: Lấy user bằng user_id
    - get_user_by_username: Lấy user bằng username
    - update_user: Cập nhật user đã tồn tại
    - update_user_status: Cập nhật trạng thái user
    """

    # Tạo user mới
    def create_user(self, conn, user_id, display_name, username=None, password_hash=None):
        now = _utcnow_iso()
        normalized_username = (username or "").strip() or "user_{}".format(user_id[:8])

        conn.execute(
            """
            INSERT INTO users(
                user_id,
                username,
                display_name,
                password_hash,
                status,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, 'ACTIVE', ?, ?)
            """,
            (user_id, normalized_username, display_name, password_hash, now, now),
        )

    # Lấy user_id từ peer_id hiện tại
    def get_user_id_by_peer_id(self, conn, peer_id):
        row = conn.execute(
            "SELECT peer_uuid FROM peers WHERE id = ?",
            (peer_id,),
        ).fetchone()
        if row is None:
            raise ValueError("Peer không tồn tại: {}".format(peer_id))
        format_row = _row_to_dict(row)
        return format_row["peer_uuid"]

    # Lấy user bằng user_id
    def get_user_by_id(self, conn, user_id):
        row = conn.execute(
            """
            SELECT user_id, username, display_name, password_hash, status, created_at, updated_at
            FROM users
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        return _row_to_dict(row)

    # Lấy user bằng username
    def get_user_by_username(self, conn, username):
        row = conn.execute(
            """
            SELECT user_id, username, display_name, password_hash, status, created_at, updated_at
            FROM users
            WHERE username = ?
            """,
            (username,),
        ).fetchone()
        return _row_to_dict(row)

    # Cập nhật user đã tồn tại
    def update_user(self, conn, user_id, username=None):
        now = _utcnow_iso()
        normalized_username = (username or "").strip() or None

        current_row = conn.execute(
            "SELECT username, display_name FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()

        if current_row is None:
            raise ValueError("User không tồn tại: {}".format(user_id))

        effective_username = normalized_username or current_row["username"]

        conn.execute(
            """
            UPDATE users
            SET
                username = ?,
                updated_at = ?
            WHERE user_id = ?
            """,
            (effective_username, now, user_id),
        )

    # Cập nhật trạng thái user
    def update_user_status(self, user_id, status):
        now = _utcnow_iso()
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE users
                SET
                    status = ?,
                    updated_at = ?
                WHERE user_id = ?
                """,
                (status, now, user_id,),
            )
            conn.commit()

            row = conn.execute(
                """
                SELECT user_id, username, display_name, password_hash, status, created_at, updated_at
                FROM users
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()

        if row is None:
            raise ValueError("User không tồn tại: {}".format(user_id))

        return _row_to_dict(row)

    """
    Truy vấn table peers
    - create_peer: Tạo peer mới
    - update_peer: Cập nhật lại thông tin peer theo user_id
    - get_peer_by_user_id: Lấy peer theo user_id
    - get_active_peers: Trả về danh sách peer đang hoạt động
    - get_peer_detail_by_user_id: Lấy chi tiết peer theo user_id (bao gồm thông tin user)
    - get_peer_detail_by_id: Lấy chi tiết peer theo peer_id (bao gồm thông tin user)
    """

    # Tạo peer mới
    def create_peer(self, ip, port, peer_uuid, display_name=None, status="ACTIVE"):
        user_id = peer_uuid or str(uuid4())
        now = _utcnow_iso()
        effective_display_name = (display_name or "").strip() or "peer_{}".format(user_id[:8])

        sql = """
        INSERT INTO peers(peer_uuid, display_name, ip, port, status, last_seen, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """

        with self._connect() as conn:
            if not self.get_user_by_id(conn, user_id):
                raise ValueError("User chưa tồn tại: {}".format(user_id))
            if self.get_peer_by_user_id(conn, user_id):
                raise ValueError("Peer đã tồn tại: {}".format(user_id))

            conn.execute(sql, (user_id, effective_display_name, ip, port, status, now, now, now))
            conn.commit()

            row = conn.execute(
                """
                SELECT p.*, u.username, u.user_id
                FROM peers p
                JOIN users u ON u.user_id = p.peer_uuid
                WHERE p.peer_uuid = ?
                """,
                (user_id,),
            ).fetchone()

        return _row_to_dict(row)

    # Cập nhật peer theo user_id (hỗ trợ cập nhật ip/port/status một phần)
    def update_peer(self, user_id, ip=None, port=None, status=None):
        now = _utcnow_iso()

        with self._connect() as conn:
            if not self.get_peer_by_user_id(conn, user_id):
                raise ValueError("Peer chưa tồn tại cho user_id: {}".format(user_id))

            current_row = conn.execute(
                "SELECT display_name, ip, port, status FROM peers WHERE peer_uuid = ?",
                (user_id,),
            ).fetchone()

            effective_ip = ip if ip is not None else current_row["ip"]
            effective_port = int(port) if port is not None else int(current_row["port"])
            effective_status = status if status is not None else current_row["status"]

            conn.execute(
                """
                UPDATE peers
                SET
                    ip = ?,
                    port = ?,
                    status = ?,
                    last_seen = ?,
                    updated_at = ?
                WHERE peer_uuid = ?
                """,
                (effective_ip, effective_port, effective_status, now, now, user_id),
            )

            conn.commit()
            row = conn.execute(
                """
                SELECT p.*, u.username, u.user_id
                FROM peers p
                JOIN users u ON u.user_id = p.peer_uuid
                WHERE p.peer_uuid = ?
                """,
                (user_id,),
            ).fetchone()

        return _row_to_dict(row)

    # Lấy peer theo user_id
    def get_peer_by_user_id(self, conn, user_id):
        row = conn.execute(
            "SELECT 1 FROM peers WHERE peer_uuid = ?",
            (user_id,),
        ).fetchone()
        return _row_to_dict(row) if row is not None else None

    # Lấy chi tiết peer theo user_id
    def get_peer_detail_by_user_id(self, user_id):
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT p.*, u.username, u.user_id
                FROM peers p
                JOIN users u ON u.user_id = p.peer_uuid
                WHERE p.peer_uuid = ?
                """,
                (user_id,),
            ).fetchone()
        return _row_to_dict(row)

    # Lấy chi tiết peer theo peer_id
    def get_peer_detail_by_id(self, peer_id):
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT p.*, u.username, u.user_id
                FROM peers p
                JOIN users u ON u.user_id = p.peer_uuid
                WHERE p.id = ?
                """,
                (peer_id,),
            ).fetchone()
        return _row_to_dict(row)

    # Trả về danh sách peer đang hoạt động
    def get_active_peers(self):
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, peer_uuid, peer_uuid AS user_id, display_name, ip, port, status, last_seen
                FROM peers
                WHERE status = 'ACTIVE'
                ORDER BY id ASC
                """
            ).fetchall()
        return [dict(r) for r in rows]


    """
    Truy vấn peer_connection
    - create_peer_connection: Tạo peer_connection khi có kết nối mới giữa 2 peer
    - update_connection_status: Cập nhật trạng thái kết nối của một user
    - update_connection_status_by_id: Cập nhật trạng thái một kết nối theo id
    - get_peer_connections: Lấy danh sách kết nối theo peer_id hoặc user_id hoặc trạng thái
    """

    # Tạo peer_connection
    def create_peer_connection(self, from_peer_id, to_peer_id, status="CONNECTED"):
        now = _utcnow_iso()
        with self._connect() as conn:
            from_user_id = self.get_user_id_by_peer_id(conn, from_peer_id)
            to_user_id = self.get_user_id_by_peer_id(conn, to_peer_id)

            conn.execute(
                """
                INSERT INTO peer_connections(
                    from_peer_id,
                    to_peer_id,
                    from_user_id,
                    to_user_id,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (from_peer_id, to_peer_id, from_user_id, to_user_id, status, now),
            )
            conn.commit()
            row = conn.execute(
                """
                SELECT * FROM peer_connections
                WHERE from_user_id = ? AND to_user_id = ?
                """,
                (from_user_id, to_user_id),
            ).fetchone()
        return _row_to_dict(row)
    
    # Cập nhật trạng thái các kết nối của một user
    def update_connection_status(self, user_id, status):
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE peer_connections
                SET status = ?
                WHERE from_user_id = ? OR to_user_id = ?
                """,
                (status, user_id, user_id),
            )
            conn.commit()
            return cur.rowcount

    # Cập nhật trạng thái một kết nối theo id
    def update_connection_status_by_id(self, connection_id, status):
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE peer_connections
                SET status = ?
                WHERE id = ?
                """,
                (status, connection_id),
            )
            conn.commit()

            row = conn.execute(
                "SELECT * FROM peer_connections WHERE id = ?",
                (connection_id,),
            ).fetchone()

        return _row_to_dict(row), cur.rowcount

    # Lấy danh sách kết nối theo peer_id hoặc user_id
    def get_peer_connections(self, peer_id=None, user_id=None, status=None):
        clauses = []
        params = []

        if peer_id is not None:
            clauses.append("(from_peer_id = ? OR to_peer_id = ?)")
            params.extend([peer_id, peer_id])

        elif user_id is not None:
            clauses.append("(from_user_id = ? OR to_user_id = ?)")
            params.extend([user_id, user_id])

        elif status is not None:
            clauses.append("status = ?")
            params.append(status)

        where_sql = ""
        if clauses:
            where_sql = " WHERE " + " AND ".join(clauses)

        sql = (
            "SELECT id, from_peer_id, to_peer_id, from_user_id, to_user_id, status, created_at"
            " FROM peer_connections"
            + where_sql
            + " ORDER BY id DESC"
        )

        with self._connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()

        return [dict(r) for r in rows]


    """
    Truy vấn table channels và channel_members
    - create_channel_and_channel_owner: Tạo channel mới và thêm người tạo vào channel_members với role là owner
    - create_channel_member: Thêm peer (peer_id) vào channel (channel_id)
    - get_channel_by_id: Trả về channel theo channel_id
    - get_channels_by_peer_id: Trả về danh sách channel mà peer (peer_id) đã tham gia
    - get_channels_by_user_id: Trả về channel mà user (user_id) đã tham gia
    - get_channel_member_ids: Trả về danh sách peer_id của các thành viên trong channel (channel_id)
    - get_channel_member_user_ids: Trả về danh sách user_id của các thành viên trong channel (channel_id)
    """

    # Tạo channel mới và thêm người tạo vào channel_members với role là owner
    def create_channel_and_channel_owner(self, name, created_by, is_private=False, access_policy=None):
        now = _utcnow_iso()
        policy_json = json.dumps(access_policy or {}, ensure_ascii=False)

        with self._connect() as conn:
            created_by_user_id = self.get_user_id_by_peer_id(conn, created_by)

            cur = conn.execute(
                """
                INSERT INTO channels(
                    name,
                    created_by,
                    created_by_user_id,
                    is_private,
                    access_policy,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (name, created_by, created_by_user_id, 1 if is_private else 0, policy_json, now),
            )
            channel_id = cur.lastrowid
            conn.execute(
                """
                INSERT OR IGNORE INTO channel_members(channel_id, peer_id, user_id, role, joined_at)
                VALUES (?, ?, ?, 'owner', ?)
                """,
                (channel_id, created_by, created_by_user_id, now),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM channels WHERE id = ?", (channel_id,)).fetchone()

        data = _row_to_dict(row)
        data["access_policy"] = json.loads(data["access_policy"])
        return data

    # Thêm peer (peer_id) vào channel (channel_id) mới
    def create_channel_member(self, channel_id, peer_id, role="member"):
        now = _utcnow_iso()
        with self._connect() as conn:
            user_id = self.get_user_id_by_peer_id(conn, peer_id)

            conn.execute(
                """
                INSERT OR REPLACE INTO channel_members(channel_id, peer_id, user_id, role, joined_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (channel_id, peer_id, user_id, role, now),
            )
            conn.commit()
            row = conn.execute(
                """
                SELECT channel_id, peer_id, user_id, role, joined_at
                FROM channel_members
                WHERE channel_id = ? AND user_id = ?
                """,
                (channel_id, user_id),
            ).fetchone()

        return _row_to_dict(row)
    
    # Trả về channel theo channel_id
    def get_channel_by_id(self, channel_id):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM channels WHERE id = ?",
                (channel_id,),
            ).fetchone()

        if row is None:
            return None

        data = _row_to_dict(row)
        data["access_policy"] = json.loads(data["access_policy"])
        return data

    # Trả về danh sách channel mà peer (peer_id) đã tham gia
    def get_channels_by_peer_id(self, peer_id):
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT c.id, c.name, c.is_private, c.access_policy, c.created_at, cm.role, cm.user_id
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
    
    # Trả về channel mà user (user_id) đã tham gia
    def get_channels_by_user_id(self, user_id):
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT c.id, c.name, c.is_private, c.access_policy, c.created_at, cm.role, cm.peer_id
                FROM channels c
                JOIN channel_members cm ON c.id = cm.channel_id
                WHERE cm.user_id = ?
                ORDER BY c.id ASC
                """,
                (user_id,),
            ).fetchall()

        result = []
        for row in rows:
            item = dict(row)
            item["access_policy"] = json.loads(item["access_policy"])
            result.append(item)
        return result

    # Trả về danh sách peer_id của các thành viên trong channel (channel_id)
    def get_channel_member_ids(self, channel_id):
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT peer_id FROM channel_members WHERE channel_id = ?",
                (channel_id,),
            ).fetchall()
        return [int(r["peer_id"]) for r in rows]
    
    # Trả về danh sách user_id của các thành viên trong channel (channel_id)
    def get_channel_member_user_ids(self, channel_id):
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT user_id FROM channel_members WHERE channel_id = ?",
                (channel_id,),
            ).fetchall()
        return [str(r["user_id"]) for r in rows]
    

    """
    Truy vấn table messages
    - create_message: Tạo message mới
    - get_messages_by_channel_id: Trả về message của channel (channel_id) + sắp xếp theo thứ tự mới đến cũ
    """

    # Tạo message
    def create_message(
        self,
        channel_id,
        sender_peer_id,
        sender_user_id,
        body,
        message_type="BROADCAST",
        target_peer_id=None,
        target_user_id=None,
    ):
        now = _utcnow_iso()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO messages(
                    channel_id,
                    sender_peer_id,
                    sender_user_id,
                    target_peer_id,
                    target_user_id,
                    message_type,
                    body,
                    immutable,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    channel_id,
                    sender_peer_id,
                    sender_user_id,
                    target_peer_id,
                    target_user_id,
                    message_type,
                    body,
                    now,
                ),
            )
            message_id = cur.lastrowid
            conn.commit()
            row = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()

        return _row_to_dict(row)

    # Trả về message của channel (channel_id) + sắp xếp theo thứ tự mới đến cũ
    def get_messages_by_channel_id(self, channel_id, limit=100):
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    id,
                    channel_id,
                    sender_peer_id,
                    sender_user_id,
                    target_peer_id,
                    target_user_id,
                    message_type,
                    body,
                    created_at
                FROM messages
                WHERE channel_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (channel_id, limit),
            ).fetchall()

        return [dict(r) for r in rows]


    """
    Truy vấn table notifications
    - create_notification: Tạo notification (peer_id: máy nhận)
    - get_notifications_by_user_id: Lấy notifications theo user_id
    - mark_notifications_read: Đánh dấu notifications đã đọc
    """
    # Tạo notification (peer_id: máy nhận)
    def create_notification(self, peer_id, user_id, message_id):
        now = _utcnow_iso()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO notifications(peer_id, user_id, message_id, is_read, created_at)
                VALUES (?, ?, ?, 0, ?)
                """,
                (peer_id, user_id, message_id, now),
            )
            notification_id = cur.lastrowid
            conn.commit()
            row = conn.execute(
                "SELECT * FROM notifications WHERE id = ?",
                (notification_id,),
            ).fetchone()

        return _row_to_dict(row)

    # Lấy notifications theo user_id
    def get_notifications_by_user_id(self, user_id, only_unread=True):
        with self._connect() as conn:
            # Ưu tiên truy vấn theo user_id để dữ liệu vẫn đồng bộ nếu peer đổi IP/port.
            if isinstance(user_id, int):
                user_id = self.get_user_id_by_peer_id(conn, user_id)
            else:
                user_id = str(user_id)

            if only_unread:
                rows = conn.execute(
                    """
                    SELECT
                        n.id,
                        n.peer_id,
                        n.user_id,
                        n.message_id,
                        n.is_read,
                        n.created_at,
                        m.body,
                        m.sender_peer_id,
                        m.sender_user_id
                    FROM notifications n
                    JOIN messages m ON m.id = n.message_id
                    WHERE n.user_id = ? AND n.is_read = 0
                    ORDER BY n.id DESC
                    """,
                    (user_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT
                        n.id,
                        n.peer_id,
                        n.user_id,
                        n.message_id,
                        n.is_read,
                        n.created_at,
                        m.body,
                        m.sender_peer_id,
                        m.sender_user_id
                    FROM notifications n
                    JOIN messages m ON m.id = n.message_id
                    WHERE n.user_id = ?
                    ORDER BY n.id DESC
                    """,
                    (user_id,),
                ).fetchall()

        return [dict(r) for r in rows]

    # Đánh dấu notifications đã đọc
    def mark_notifications_read(self, notification_ids):
        if not notification_ids:
            return 0

        placeholders = ",".join("?" for _ in notification_ids)
        sql = "UPDATE notifications SET is_read = 1 WHERE id IN ({})".format(placeholders)

        with self._connect() as conn:
            cur = conn.execute(sql, tuple(notification_ids))
            conn.commit()
            return cur.rowcount