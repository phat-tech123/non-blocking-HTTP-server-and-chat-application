#
# Copyright (C) 2026 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course,
# and is released under the "MIT License Agreement". Please see the LICENSE
# file that should have been included as part of this package.
#
# AsynapRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course
#


"""
app.sampleapp
~~~~~~~~~~~~~~~~~

"""

import hmac
import hashlib
import json
import base64
import socket
import threading
import time

from collections.abc import Mapping

from pathlib import Path
from uuid import uuid4

from daemon import AsynapRous
from db.repository import ChatRepository, initialize_database

app = AsynapRous()
SESSION_TTL_SECONDS = 24 * 60 * 60


"""
Helper func
"""

# Convert data to JSON string
def json_response(data):
    return json.dumps(data).encode("utf-8")

# Standard success response
def ok_response(data=None, message="ok"):
    return json_response({"success": True, "message": message, "data": data})

# Standard error response
def error_response(message, code="BAD_REQUEST"):
    return json_response({"success": False, "error": code, "message": message})

# Create envelope for hook response (format HTTPAdapter use)
def build_hook_response(body, status_code=200, reason="OK", headers=None, cookies=None):
    payload = body if isinstance(body, (bytes, bytearray)) else str(body).encode("utf-8")
    return {
        "body": bytes(payload),
        "status_code": int(status_code),
        "reason": str(reason),
        "headers": headers or {},
        "cookies": cookies or {},
    }

# Parse JSON body from request
def parse_json_body(body):
    if body is None:
        return {}
    if isinstance(body, bytes):
        body = body.decode("utf-8", errors="ignore")
    if not isinstance(body, str):
        return None
    raw = body.strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None

# Get header value from headers
def get_header(headers, key, default=""):
    if isinstance(headers, Mapping):
        return headers.get(key, default)
    return default

# Parse Basic Auth header and return username/password
def parse_basic_auth(headers):
    raw_auth = str(get_header(headers, "authorization", "") or "")
    if not raw_auth.lower().startswith("basic "):
        return None, None

    encoded = raw_auth.split(" ", 1)[1].strip()
    if not encoded:
        return None, None

    try:
        decoded = base64.b64decode(encoded).decode("utf-8")
        if ":" not in decoded:
            return None, None
        username, password = decoded.split(":", 1)
        return username, password
    except Exception:
        return None, None

# Extract session_id from Cookie
def extract_session_id(headers):
    raw_cookie = str(get_header(headers, "cookie", "") or "")
    if not raw_cookie:
        return None

    for pair in raw_cookie.split(";"):
        part = pair.strip()
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        if k.strip().lower() == "session_id":
            value = v.strip()
            return value if value else None

    return None
 
# Get repository instance from app
def get_repo():
    repo = app.get_state("repository")
    if repo is None:
        raise RuntimeError("Repository is not initialized")
    return repo

# Get session store from app state
def get_session_store():
    sessions = app.get_state("sessions")
    if sessions is None:
        sessions = {}
        app.set_state("sessions", sessions)
    return sessions

# Create a new session for a user
def create_session(user_id, username):
    sessions = get_session_store()
    session_id = uuid4().hex
    sessions[session_id] = {
        "user_id": str(user_id),
        "username": str(username),
        "issued_at": int(time.time()),
        "expires_at": int(time.time()) + SESSION_TTL_SECONDS,
    }
    return session_id

# Get session info by session_id
def get_session(session_id):
    if not session_id:
        return None

    sessions = get_session_store()
    data = sessions.get(session_id)
    if data is None:
        return None

    now_ts = int(time.time())
    if int(data.get("expires_at", 0)) <= now_ts:
        sessions.pop(session_id, None)
        return None

    return data

# Invalidate a session by session_id
def invalidate_session(session_id):
    sessions = get_session_store()
    return sessions.pop(session_id, None) is not None

# Get or initialize stream runtime state used by persistent P2P sockets.
def get_stream_runtime():
    runtime = app.get_state("stream_runtime")
    if runtime is None:
        runtime = {
            "lock": threading.RLock(),
            "connections": {},
            "listener_socket": None,
            "listener_thread": None,
            "listener_addr": None,
            "inbox": [],
        }
        app.set_state("stream_runtime", runtime)
    return runtime

# Build a unique key for one directional stream connection.
def stream_key(from_peer_id, to_peer_id):
    return "{}->{}".format(int(from_peer_id), int(to_peer_id))

# Safely close a socket and ignore close errors.
def close_socket_quietly(sock):
    if sock is None:
        return
    try:
        sock.close()
    except Exception:
        pass

# Encode one stream packet as a newline-delimited JSON frame.
def encode_stream_packet(packet):
    return (json.dumps(packet) + "\n").encode("utf-8")

# Read a full JSON frame line from stream socket.
def recv_stream_line(sock, timeout=2.0, max_bytes=65536):
    sock.settimeout(float(timeout))
    data = bytearray()
    while len(data) < max_bytes:
        chunk = sock.recv(1)
        if not chunk:
            break
        data.extend(chunk)
        if chunk == b"\n":
            break
    if not data:
        return None
    return data.decode("utf-8", errors="ignore").strip()

# Send one JSON packet to stream peer and optionally wait for ack.
def send_stream_packet(sock, packet, wait_ack=True, ack_timeout=1.5):
    try:
        sock.sendall(encode_stream_packet(packet))
    except Exception:
        return False, None

    if not wait_ack:
        return True, None

    try:
        line = recv_stream_line(sock, timeout=ack_timeout)
        if not line:
            return False, None
        ack = json.loads(line)
        return bool(ack.get("ok", False)), ack
    except Exception:
        return False, None

# Handle one inbound stream client and push accepted events to runtime inbox.
def handle_stream_client(conn, addr):
    try:
        line = recv_stream_line(conn, timeout=30.0)
        if not line:
            return

        packet = json.loads(line)
        runtime = get_stream_runtime()
        with runtime["lock"]:
            runtime["inbox"].append(
                {
                    "event_type": str(packet.get("event_type", "unknown")),
                    "payload": packet.get("payload", {}),
                    "received_at": int(time.time()),
                    "from_ip": addr[0] if isinstance(addr, tuple) and addr else "",
                }
            )

        ack_packet = {"ok": True, "event_type": packet.get("event_type", "unknown"), "received_at": int(time.time())}
        conn.sendall(encode_stream_packet(ack_packet))
    except Exception:
        try:
            conn.sendall(encode_stream_packet({"ok": False, "reason": "invalid_packet"}))
        except Exception:
            pass
    finally:
        close_socket_quietly(conn)

# Run listener loop that accepts inbound stream sockets.
def stream_listener_loop(listener_sock):
    while True:
        try:
            conn, addr = listener_sock.accept()
            t = threading.Thread(target=handle_stream_client, args=(conn, addr), daemon=True)
            t.start()
        except Exception:
            break

# Ensure stream listener is running on provided endpoint.
def ensure_stream_listener(ip, port):
    runtime = get_stream_runtime()
    try:
        port = int(port)
    except (TypeError, ValueError):
        return {"ok": False, "reason": "invalid_port"}

    with runtime["lock"]:
        running_addr = runtime.get("listener_addr")
        if running_addr is not None and running_addr == (str(ip), int(port)):
            return {"ok": True, "reason": "already_running", "addr": running_addr}

        if runtime.get("listener_socket") is not None and running_addr != (str(ip), int(port)):
            return {"ok": False, "reason": "listener_running_on_other_port", "addr": running_addr}

        try:
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((str(ip), int(port)))
            listener.listen(50)
        except Exception:
            close_socket_quietly(listener)
            return {"ok": False, "reason": "bind_failed", "addr": (str(ip), int(port))}

        runtime["listener_socket"] = listener
        runtime["listener_addr"] = (str(ip), int(port))
        t = threading.Thread(target=stream_listener_loop, args=(listener,), daemon=True)
        t.start()
        runtime["listener_thread"] = t

    return {"ok": True, "reason": "started", "addr": (str(ip), int(port))}

# Establish and keep one persistent stream socket from source peer to target peer.
def establish_stream_connection(from_peer, to_peer, timeout=2.0):
    if from_peer is None or to_peer is None:
        return {"attempted": False, "ok": False, "reason": "peer_not_found"}

    from_peer_id = int(from_peer.get("id"))
    to_peer_id = int(to_peer.get("id"))
    key = stream_key(from_peer_id, to_peer_id)
    runtime = get_stream_runtime()

    with runtime["lock"]:
        existing = runtime["connections"].get(key)
        if existing is not None:
            return {"attempted": True, "ok": True, "reason": "already_connected", "reused": True}

    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(float(timeout))
        sock.connect((str(to_peer.get("ip")), int(to_peer.get("port"))))

        packet = {
            "event_type": "peer_connect_request",
            "payload": {
                "from_peer_id": from_peer_id,
                "to_peer_id": to_peer_id,
                "from_ip": from_peer.get("ip"),
                "from_port": from_peer.get("port"),
            },
            "sent_at": int(time.time()),
        }
        ok, ack = send_stream_packet(sock, packet, wait_ack=True, ack_timeout=1.5)
        if not ok:
            close_socket_quietly(sock)
            return {"attempted": True, "ok": False, "reason": "handshake_failed"}

        with runtime["lock"]:
            runtime["connections"][key] = {
                "socket": sock,
                "from_peer_id": from_peer_id,
                "to_peer_id": to_peer_id,
                "target_ip": to_peer.get("ip"),
                "target_port": to_peer.get("port"),
                "connected_at": int(time.time()),
            }

        return {"attempted": True, "ok": True, "reason": "connected", "ack": ack}
    except Exception as ex:
        close_socket_quietly(sock)
        return {"attempted": True, "ok": False, "reason": "socket_error", "error": str(ex)}

# Send direct message packet via existing persistent stream connection.
def send_direct_via_stream(sender_peer, target_peer, message):
    if sender_peer is None or target_peer is None:
        return {"attempted": False, "ok": False, "reason": "peer_not_found"}

    key = stream_key(int(sender_peer.get("id")), int(target_peer.get("id")))
    runtime = get_stream_runtime()

    with runtime["lock"]:
        entry = runtime["connections"].get(key)

    if entry is None:
        return {"attempted": False, "ok": False, "reason": "stream_not_connected"}

    packet = {
        "event_type": "direct_message",
        "payload": {
            "message": message,
            "from_peer_id": sender_peer.get("id"),
            "to_peer_id": target_peer.get("id"),
        },
        "sent_at": int(time.time()),
    }

    ok, ack = send_stream_packet(entry.get("socket"), packet, wait_ack=True, ack_timeout=1.5)
    if ok:
        return {"attempted": True, "ok": True, "reason": "delivered", "ack": ack}

    with runtime["lock"]:
        stale = runtime["connections"].pop(key, None)
    if stale is not None:
        close_socket_quietly(stale.get("socket"))
    return {"attempted": True, "ok": False, "reason": "stream_send_failed"}

# Reconnect stream sockets for active historical connections of a logged-in user.
def reconnect_stream_connections_for_user(repo, user_id):
    peer_self = repo.get_peer_detail_by_user_id(user_id)
    if peer_self is None:
        return []

    rows = repo.get_peer_connections(user_id=user_id, status="CONNECTED")
    results = []
    for row in rows:
        from_peer_id = int(row.get("from_peer_id"))
        to_peer_id = int(row.get("to_peer_id"))

        target_peer_id = to_peer_id if from_peer_id == int(peer_self.get("id")) else from_peer_id
        target_peer = repo.get_peer_detail_by_id(target_peer_id)
        if target_peer is None or str(target_peer.get("status", "")).upper() != "ACTIVE":
            continue

        result = establish_stream_connection(peer_self, target_peer, timeout=2.0)
        result["target_peer_id"] = target_peer_id
        results.append(result)

    return results

# Close all stream sockets associated with one user and drop them from runtime pool.
def close_stream_connections_for_user(repo, user_id):
    peer_self = repo.get_peer_detail_by_user_id(user_id)
    if peer_self is None:
        return 0

    peer_id = int(peer_self.get("id"))
    runtime = get_stream_runtime()

    keys_to_close = []
    with runtime["lock"]:
        for key, value in runtime["connections"].items():
            if int(value.get("from_peer_id", -1)) == peer_id or int(value.get("to_peer_id", -1)) == peer_id:
                keys_to_close.append(key)

        for key in keys_to_close:
            entry = runtime["connections"].pop(key, None)
            if entry is not None:
                close_socket_quietly(entry.get("socket"))

    return len(keys_to_close)

# Check if user exists
def check_user(repo, user_id):
    with repo._connect() as conn:
        existing = repo.get_user_by_id(conn, user_id)
    if existing:
        return True
    else:
        return False
    
def hash_password(password):
    if not isinstance(password, str) or not password:
        raise ValueError("Password must be non-empty string")

    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def verify_password(password, stored_hash):
    try:
        if not isinstance(password, str) or not password:
            return False
        actual = hashlib.sha256(password.encode("utf-8")).hexdigest()
        return hmac.compare_digest(actual, str(stored_hash or ""))
    except Exception:
        return False
    
def require_fields(payload, names):
    missing = [n for n in names if payload.get(n) in (None, "", [])]
    if missing:
        return "Missing fields: {}".format(", ".join(missing))
    return None

# Lấy IP client từ headers (x-forwarded-for, x-real-ip, client-ip, remote-addr)
def extract_client_ip(headers):
    ip = ""

    if isinstance(headers, Mapping):
        forwarded = get_header(headers, "x-forwarded-for") or get_header(headers, "X-Forwarded-For")
        real_ip = get_header(headers, "x-real-ip") or get_header(headers, "X-Real-IP")
        client_ip = get_header(headers, "client-ip") or get_header(headers, "Client-IP")
        remote_addr = get_header(headers, "remote-addr") or get_header(headers, "Remote-Addr")

        if forwarded:
            ip = str(forwarded).split(",")[0].strip()
        elif real_ip:
            ip = str(real_ip).strip()
        elif client_ip:
            ip = str(client_ip).strip()
        elif remote_addr:
            ip = str(remote_addr).strip()

    return ip

# Kiểm tra port hợp lệ
def parse_port(value):
    try:
        port = int(value)
    except (TypeError, ValueError):
        return None
    if port <= 0 or port > 65535:
        return None
    return port

# Lấy thông tin user và peer từ username
def get_user_peer_context(repo, username):
    with repo._connect() as conn:
        user = repo.get_user_by_username(conn, username)
        if user is None:
            return None, None

    peer = repo.get_peer_detail_by_user_id(user["user_id"])
    return user, peer


"""
Danh sách api:
- POST /register: Đang ký tài khoản mới, tạo user và peer
- POST /login: Đăng nhập, kích hoạt user/peer, tạo kết nối P2P giữa peer và các peer khác đang active (đã connect trước đó)
- POST /logout: Đăng xuất, hủy kích hoạt user/peer, hủy kết nối P2P giữa peer và các peer khác
- GET /peers/active: Lấy danh sách peer đang hoạt động
- POST /peers/connect: Tạo kết nối P2P giữa 2 peer
- POST /peers/reconnect-active: Kết nối lại stream tới các peer đang active và đã connect trước đó
- POST /connections/list: Lấy danh sách connection của user/peer
- POST /connections/update-status: Cập nhật trạng thái 1 connection theo id
- POST /channels/create: Tạo channel mới
- POST /channels/join: Thêm thành viên vào channel
- POST /channels/list: Liệt kê channel theo user
- POST /channels/messages: Xem lịch sử tin nhắn trong channel
- POST /messages/direct: Gửi direct, luôn lưu DB; offline thì chỉ lưu, online thì lưu + realtime
- POST /notifications/list: Lấy danh sách thông báo của user
- POST /notifications/read: Đánh dấu thông báo đã đọc
"""

@app.route('/register', methods=['POST'])
def register(headers="guest", body="anonymous"):
    payload = parse_json_body(body)
    if payload is None:
        return error_response("Invalid JSON body", "INVALID_JSON")

    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", "") or "")

    if not username or not password:
        auth_username, auth_password = parse_basic_auth(headers)
        username = username or str(auth_username or "").strip()
        password = password or str(auth_password or "")

    err = require_fields(
        {"username": username, "password": password, "port": payload.get("port")},
        ["username", "password", "port"],
    )
    if err:
        return error_response(err, "VALIDATION_ERROR")

    display_name = str(payload.get("display_name", "")).strip() or username
    ip = extract_client_ip(headers)
    port = parse_port(payload["port"])

    if not username:
        return error_response("username must not be empty", "VALIDATION_ERROR")
    if not password:
        return error_response("password must not be empty", "VALIDATION_ERROR")
    if not ip:
        return error_response("Cannot determine client IP", "VALIDATION_ERROR")
    if port is None:
        return error_response("Port is invalid", "VALIDATION_ERROR")

    repo = get_repo()

    try:
        with repo._connect() as conn:
            existing = repo.get_user_by_username(conn, username)
            if existing is not None:
                return error_response("Username already exists", "USERNAME_EXISTS")

            user_id = str(uuid4())
            password_hash = hash_password(password)

            repo.create_user(
                conn,
                user_id=user_id,
                display_name=display_name,
                username=username,
                password_hash=password_hash,
            )
            conn.commit()

        peer = repo.create_peer(
            ip=ip,
            port=port,
            peer_uuid=user_id,
            display_name=display_name,
            status="ACTIVE",
        )

        session_id = create_session(user_id, username)

        return build_hook_response(
            body=json_response(
                {
                    "success": True,
                    "message": "Register successful",
                    "data": {
                        "user_id": user_id,
                        "username": username,
                        "peer": peer,
                        "session_id": session_id,
                        "auth_integration": "ready",
                    },
                }
            ),
            headers={"Content-Type": "application/json"},
            cookies={"session_id": session_id},
        )
    except ValueError as ex:
        return error_response(str(ex), "BUSINESS_ERROR")
    except Exception as ex:
        return error_response(str(ex), "REGISTER_FAILED")

@app.route('/login', methods=['POST'])
def login(headers="guest", body="anonymous"):
    """
    Handle user login via POST request.

    This route simulates a login process and prints the provided headers and body
    to the console.

    :param headers (str): The request headers or user identifier.
    :param body (str): The request body or login payload.
    """
    payload = parse_json_body(body)
    if payload is None:
        return error_response("Invalid JSON body", "INVALID_JSON")

    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", "") or "")

    if not username or not password:
        auth_username, auth_password = parse_basic_auth(headers)
        username = username or str(auth_username or "").strip()
        password = password or str(auth_password or "")

    err = require_fields(
        {"username": username, "password": password, "port": payload.get("port")},
        ["username", "password", "port"],
    )
    if err:
        return error_response(err, "VALIDATION_ERROR")

    ip = extract_client_ip(headers)
    port = parse_port(payload["port"])

    if not username:
        return error_response("username must not be empty", "VALIDATION_ERROR")
    if not password:
        return error_response("password must not be empty", "VALIDATION_ERROR")
    if not ip:
        return error_response("Cannot determine client IP", "VALIDATION_ERROR")
    if port is None:
        return error_response("Port is invalid", "VALIDATION_ERROR")

    repo = get_repo()

    try:
        with repo._connect() as conn:
            user = repo.get_user_by_username(conn, username)

            if user is None:
                return error_response("User not found", "USER_NOT_FOUND")

            user_id = user["user_id"]
            stored_hash = user.get("password_hash") or ""
            if not verify_password(password, stored_hash):
                return error_response("Invalid username or password", "AUTH_FAILED")

        user_row = repo.update_user_status(user_id, "ACTIVE")

        with repo._connect() as conn:
            peer_exists = repo.get_peer_by_user_id(conn, user_id)

        if peer_exists:
            peer = repo.update_peer(
                user_id=user_id,
                ip=ip,
                port=port,
                status="ACTIVE",
            )
        else:
            peer = repo.create_peer(
                ip=ip,
                port=port,
                peer_uuid=user_id,
                display_name=user_row["display_name"],
                status="ACTIVE",
            )

        updated_connections = repo.update_connection_status(user_id, "CONNECTED")
        listener_status = ensure_stream_listener(ip, port)
        reconnect_results = reconnect_stream_connections_for_user(repo, user_id)

        session_id = create_session(user_id, username)

        return build_hook_response(
            body=json_response(
                {
                    "success": True,
                    "message": "Login successful",
                    "data": {
                        "mode": "LOGIN",
                        "user_id": user_id,
                        "username": username,
                        "peer": peer,
                        "connections_updated": updated_connections,
                        "stream_listener": listener_status,
                        "stream_reconnect": reconnect_results,
                        "session_id": session_id,
                        "auth_integration": "ready",
                    },
                }
            ),
            headers={"Content-Type": "application/json"},
            cookies={"session_id": session_id},
        )

    except ValueError as ex:
        return error_response(str(ex), "BUSINESS_ERROR")
    except Exception as ex:
        return error_response(str(ex), "LOGIN_FAILED")


@app.route('/logout', methods=['POST'])
def logout(headers="guest", body="anonymous"):
    payload = parse_json_body(body)
    if payload is None:
        return error_response("Invalid JSON body", "INVALID_JSON")

    username = str(payload.get("username", "")).strip()

    # Ho tro logout bang cookie session id sau khi daemon da parse Cookie header.
    session_id = extract_session_id(headers)

    if not username:
        auth_username, _ = parse_basic_auth(headers)
        username = str(auth_username or "").strip()

    if not username and not session_id:
        return error_response("username or session_id is required", "VALIDATION_ERROR")

    if not username:
        if session_id:
            session_info = get_session(session_id)
            if session_info:
                username = str(session_info.get("username", "")).strip()

    if not username:
        return error_response("username is required", "VALIDATION_ERROR")

    repo = get_repo()

    try:
        with repo._connect() as conn:
            user = repo.get_user_by_username(conn, username)
            if user is None:
                return error_response("User not found", "USER_NOT_FOUND")

            user_id = user["user_id"]
            peer_exists = repo.get_peer_by_user_id(conn, user_id)

        user_data = repo.update_user_status(user_id, "INACTIVE")

        peer = None
        if peer_exists:
            peer = repo.update_peer(
                user_id=user_id,
                status="INACTIVE",
            )

        updated_connections = repo.update_connection_status(user_id, "DISCONNECTED")
        closed_stream_connections = close_stream_connections_for_user(repo, user_id)

        invalidated = invalidate_session(session_id) if session_id else False

        return build_hook_response(
            body=json_response(
                {
                    "success": True,
                    "message": "Logout successful",
                    "data": {
                        "connections_updated": updated_connections,
                        "closed_stream_connections": closed_stream_connections,
                        "session_invalidated": invalidated,
                        "auth_integration": "ready",
                    },
                }
            ),
            headers={"Content-Type": "application/json"},
            cookies={"session_id": ""},
        )
    except ValueError as ex:
        return error_response(str(ex), "BUSINESS_ERROR")
    except Exception as ex:
        return error_response(str(ex), "LOGOUT_FAILED")

# Lấy danh sách peer đang hoạt động
@app.route('/peers/active', methods=['GET'])
def list_active_peers(headers="guest", body="anonymous"):
    repo = get_repo()
    try:
        peers = repo.get_active_peers()
        return ok_response(
            data={"peers": peers},
            message="Active peers fetched"
        )
    except Exception as ex:
        return error_response(str(ex), "GET_PEERS_FAILED")

# Tạo kết nối P2P
@app.route('/peers/connect', methods=['POST'])
def connect_peer(headers="guest", body="anonymous"):
    payload = parse_json_body(body)
    if payload is None:
        return error_response("Invalid JSON body", "INVALID_JSON")

    err = require_fields(payload, ["from_peer_id", "to_peer_id"])
    if err:
        return error_response(err, "VALIDATION_ERROR")

    try:
        from_peer_id = int(payload["from_peer_id"])
        to_peer_id = int(payload["to_peer_id"])
    except (TypeError, ValueError):
        return error_response("Peer id is invalid", "VALIDATION_ERROR")

    repo = get_repo()

    try:
        connection = repo.create_peer_connection(from_peer_id, to_peer_id, status="PENDING")

        from_peer = repo.get_peer_detail_by_id(from_peer_id)
        to_peer = repo.get_peer_detail_by_id(to_peer_id)
        connect_runtime = {
            "attempted": False,
            "ok": False,
            "reason": "stream_not_attempted",
        }

        if from_peer is None or to_peer is None:
            connect_runtime["reason"] = "target_peer_not_found"

        if from_peer is not None and to_peer is not None:
            connect_runtime.update(establish_stream_connection(from_peer, to_peer, timeout=2.0))

        if connect_runtime.get("ok"):
            connection, _ = repo.update_connection_status_by_id(connection["id"], "CONNECTED")
        else:
            connection, _ = repo.update_connection_status_by_id(connection["id"], "PENDING")

        return ok_response(
            data={
                "connection": connection,
                "runtime_connect": connect_runtime,
            },
            message="Peer connection created"
        )
    except ValueError as ex:
        return error_response(str(ex), "BUSINESS_ERROR")
    except Exception as ex:
        return error_response(str(ex), "CONNECT_PEER_FAILED")

# Kết nối lại stream tới các peer đang active và đã connect trước đó
@app.route('/peers/reconnect-active', methods=['POST'])
def reconnect_active_peers(headers="guest", body="anonymous"):
    payload = parse_json_body(body)
    if payload is None:
        return error_response("Invalid JSON body", "INVALID_JSON")

    user_id = payload.get("user_id")
    username = str(payload.get("username", "")).strip()

    if user_id is None and not username:
        return error_response("user_id or username is required", "VALIDATION_ERROR")

    repo = get_repo()

    try:
        if user_id is None:
            user, peer = get_user_peer_context(repo, username)
            if user is None:
                return error_response("User not found", "USER_NOT_FOUND")
            user_id = user["user_id"]
        else:
            user_id = str(user_id)
            peer = repo.get_peer_detail_by_user_id(user_id)

        if peer is None:
            return error_response("Peer not found", "PEER_NOT_FOUND")

        listener_status = ensure_stream_listener(peer.get("ip"), peer.get("port"))
        reconnect_results = reconnect_stream_connections_for_user(repo, user_id)

        success_count = sum(1 for item in reconnect_results if item.get("ok"))

        return ok_response(
            data={
                "user_id": user_id,
                "peer_id": peer.get("id"),
                "stream_listener": listener_status,
                "total_attempted": len(reconnect_results),
                "total_success": success_count,
                "results": reconnect_results,
            },
            message="Reconnect active peers completed"
        )
    except Exception as ex:
        return error_response(str(ex), "RECONNECT_ACTIVE_PEERS_FAILED")

# Lấy danh sách connection của user/peer
@app.route('/connections/list', methods=['POST'])
def list_connections(headers="guest", body="anonymous"):
    payload = parse_json_body(body)
    if payload is None:
        return error_response("Invalid JSON body", "INVALID_JSON")

    peer_id = payload.get("peer_id")
    user_id = payload.get("user_id")
    username = str(payload.get("username", "")).strip()
    status = payload.get("status")

    if user_id is None and not username and peer_id is None:
        return error_response(
            "One of user_id, username, or peer_id is required",
            "VALIDATION_ERROR",
        )

    repo = get_repo()

    try:
        if user_id is not None:
            user_id = str(user_id)
            peer_id = None
        elif username:
            user, _ = get_user_peer_context(repo, username)
            if user is None:
                return error_response("User not found", "USER_NOT_FOUND")
            user_id = user["user_id"]
            peer_id = None
        else:
            peer_id = int(peer_id)

        connections = repo.get_peer_connections(peer_id=peer_id, user_id=user_id, status=status)
        return ok_response(
            data={"connections": connections},
            message="Connections fetched"
        )
    except (TypeError, ValueError):
        return error_response("peer_id or user_id is invalid", "VALIDATION_ERROR")
    except Exception as ex:
        return error_response(str(ex), "GET_CONNECTIONS_FAILED")

# Cập nhật trạng thái connection theo id
@app.route('/connections/update-status', methods=['POST'])
def update_connection_status(headers="guest", body="anonymous"):
    payload = parse_json_body(body)
    if payload is None:
        return error_response("Invalid JSON body", "INVALID_JSON")

    err = require_fields(payload, ["connection_id", "status"])
    if err:
        return error_response(err, "VALIDATION_ERROR")

    try:
        connection_id = int(payload["connection_id"])
    except (TypeError, ValueError):
        return error_response("connection_id is invalid", "VALIDATION_ERROR")

    status = str(payload["status"]).strip().upper()
    repo = get_repo()

    try:
        connection, affected = repo.update_connection_status_by_id(connection_id, status)
        if affected == 0:
            return error_response("Connection not found", "CONNECTION_NOT_FOUND")

        return ok_response(
            data={"connection": connection, "affected": affected},
            message="Connection status updated"
        )
    except Exception as ex:
        return error_response(str(ex), "UPDATE_CONNECTION_FAILED")

# Tạo channel mới
@app.route('/channels/create', methods=['POST'])
def create_channel(headers="guest", body="anonymous"):
    payload = parse_json_body(body)
    if payload is None:
        return error_response("Invalid JSON body", "INVALID_JSON")

    err = require_fields(payload, ["owner_peer_id", "name"])
    if err:
        return error_response(err, "VALIDATION_ERROR")

    try:
        owner_peer_id = int(payload["owner_peer_id"])
    except (TypeError, ValueError):
        return error_response("owner_peer_id is invalid", "VALIDATION_ERROR")

    name = str(payload["name"]).strip()
    if not name:
        return error_response("Channel name must not be empty", "VALIDATION_ERROR")

    is_private = bool(payload.get("is_private", False))
    access_policy = payload.get("access_policy", {})
    repo = get_repo()

    try:
        channel = repo.create_channel_and_channel_owner(
            name=name,
            created_by=owner_peer_id,
            is_private=is_private,
            access_policy=access_policy,
        )

        runtime_events = app.get_state("runtime_events", [])
        event = {
            "event": "channel.created",
            "channel_id": channel.get("id"),
            "owner_peer_id": owner_peer_id,
            "at": int(time.time()),
        }
        runtime_events.append(event)
        app.set_state("runtime_events", runtime_events)

        return ok_response(
            data={"channel": channel, "runtime_event": event},
            message="Channel created"
        )
    except Exception as ex:
        return error_response(str(ex), "CREATE_CHANNEL_FAILED")

# Thêm thành viên vào channel
@app.route('/channels/join', methods=['POST'])
def join_channel(headers="guest", body="anonymous"):
    payload = parse_json_body(body)
    if payload is None:
        return error_response("Invalid JSON body", "INVALID_JSON")

    err = require_fields(payload, ["channel_id", "peer_id"])
    if err:
        return error_response(err, "VALIDATION_ERROR")

    try:
        channel_id = int(payload["channel_id"])
        peer_id = int(payload["peer_id"])
    except (TypeError, ValueError):
        return error_response("channel_id/peer_id is invalid", "VALIDATION_ERROR")

    role = str(payload.get("role", "member")).strip() or "member"
    repo = get_repo()

    try:
        member = repo.create_channel_member(channel_id=channel_id, peer_id=peer_id, role=role)
        return ok_response(
            data={"member": member},
            message="Joined channel"
        )
    except Exception as ex:
        return error_response(str(ex), "JOIN_CHANNEL_FAILED")

# Liêt kê channel theo user_id
@app.route('/channels/list', methods=['POST'])
def list_channels(headers="guest", body="anonymous"):
    payload = parse_json_body(body)
    if payload is None:
        return error_response("Invalid JSON body", "INVALID_JSON")

    username = str(payload.get("username", "")).strip()
    user_id = payload.get("user_id")

    if not username and not user_id:
        return error_response("username or user_id is required", "VALIDATION_ERROR")

    repo = get_repo()

    try:
        if username and not user_id:
            user, _ = get_user_peer_context(repo, username)
            if user is None:
                return error_response("User not found", "USER_NOT_FOUND")
            user_id = user["user_id"]

        channels = repo.get_channels_by_user_id(str(user_id))
        return ok_response(
            data={"channels": channels},
            message="Channels fetched"
        )
    except Exception as ex:
        return error_response(str(ex), "LIST_CHANNELS_FAILED")

# Lấy lịch sử tin nhắn trong channel
@app.route('/channels/messages', methods=['POST'])
def list_channel_messages(headers="guest", body="anonymous"):
    payload = parse_json_body(body)
    if payload is None:
        return error_response("Invalid JSON body", "INVALID_JSON")

    err = require_fields(payload, ["channel_id"])
    if err:
        return error_response(err, "VALIDATION_ERROR")

    try:
        channel_id = int(payload["channel_id"])
        limit = int(payload.get("limit", 100))
    except (TypeError, ValueError):
        return error_response("channel_id/limit is invalid", "VALIDATION_ERROR")

    limit = max(1, min(limit, 500))
    repo = get_repo()

    try:
        messages = repo.get_messages_by_channel_id(channel_id=channel_id, limit=limit)
        return ok_response(
            data={"messages": messages},
            message="Messages fetched"
        )
    except Exception as ex:
        return error_response(str(ex), "LIST_MESSAGES_FAILED")


# Gửi tin nhắn direct: luôn lưu DB, realtime chỉ khi cả 2 peer đang ACTIVE
@app.route('/messages/direct', methods=['POST'])
def send_direct_message(headers="guest", body="anonymous"):
    payload = parse_json_body(body)
    if payload is None:
        return error_response("Invalid JSON body", "INVALID_JSON")

    err = require_fields(payload, ["sender_peer_id", "target_peer_id", "body"])
    if err:
        return error_response(err, "VALIDATION_ERROR")

    try:
        sender_peer_id = int(payload["sender_peer_id"])
        target_peer_id = int(payload["target_peer_id"])
    except (TypeError, ValueError):
        return error_response("sender_peer_id/target_peer_id is invalid", "VALIDATION_ERROR")

    channel_id = payload.get("channel_id")

    if channel_id is not None:
        try:
            channel_id = int(channel_id)
        except (TypeError, ValueError):
            return error_response("channel_id is invalid", "VALIDATION_ERROR")

    body_text = str(payload["body"]).strip()
    if not body_text:
        return error_response("Message body must not be empty", "VALIDATION_ERROR")

    repo = get_repo()

    try:
        sender_peer = repo.get_peer_detail_by_id(sender_peer_id)
        if sender_peer is None:
            return error_response("Sender peer not found", "SENDER_PEER_NOT_FOUND")

        target_peer = repo.get_peer_detail_by_id(target_peer_id)
        if target_peer is None:
            return error_response("Target peer not found", "TARGET_PEER_NOT_FOUND")

        sender_user_id = sender_peer["user_id"]
        target_user_id = target_peer["user_id"]

        sender_active = str(sender_peer.get("status", "")).upper() == "ACTIVE"
        target_active = str(target_peer.get("status", "")).upper() == "ACTIVE"
        connected_links = repo.get_peer_connections(peer_id=sender_peer_id, status="CONNECTED")
        has_connected_path = any(
            (link.get("from_peer_id") == sender_peer_id and link.get("to_peer_id") == target_peer_id)
            or (link.get("from_peer_id") == target_peer_id and link.get("to_peer_id") == sender_peer_id)
            for link in connected_links
        )

        message = repo.create_message(
            channel_id=channel_id,
            sender_peer_id=sender_peer_id,
            sender_user_id=sender_user_id,
            body=body_text,
            message_type="DIRECT",
            target_peer_id=target_peer_id,
            target_user_id=target_user_id,
        )

        # Luon tao notification de peer dich doc lai khi login/vao channel sau
        repo.create_notification(target_peer_id, target_user_id, message["id"])

        delivery_mode = "stored_only"
        realtime_status = "not_applicable"
        realtime_detail = {"attempted": False, "ok": False, "reason": "not_attempted"}
        if sender_active and target_active and has_connected_path:
            realtime_detail = {
                "attempted": False,
                "ok": False,
                "reason": "stream_not_connected",
                "target_ip": target_peer["ip"],
                "target_port": target_peer["port"],
            }
            realtime_detail.update(send_direct_via_stream(sender_peer, target_peer, message))
            if realtime_detail.get("ok"):
                delivery_mode = "realtime_and_stored"
                realtime_status = "delivered_realtime"
            else:
                delivery_mode = "stored_only"
                realtime_status = "stored_target_unreachable"
        elif sender_active and target_active and not has_connected_path:
            realtime_status = "stored_no_connection"
            realtime_detail = {
                "attempted": False,
                "ok": False,
                "reason": "connection_not_found",
                "target_ip": target_peer["ip"],
                "target_port": target_peer["port"],
            }
        else:
            realtime_status = "target_or_sender_inactive"

        return ok_response(
            data={
                "message": message,
                "delivery_mode": delivery_mode,
                "realtime_status": realtime_status,
                "realtime_detail": realtime_detail,
                "sender_active": sender_active,
                "target_active": target_active,
                "has_connected_path": has_connected_path,
            },
            message="Direct message sent"
        )
    except Exception as ex:
        return error_response(str(ex), "DIRECT_MESSAGE_FAILED")

# Lấy danh sách thông báo của user
@app.route('/notifications/list', methods=['POST'])
def list_notifications(headers="guest", body="anonymous"):
    payload = parse_json_body(body)
    if payload is None:
        return error_response("Invalid JSON body", "INVALID_JSON")

    username = str(payload.get("username", "")).strip()
    user_id = payload.get("user_id")
    only_unread = bool(payload.get("only_unread", True))

    if not username and not user_id:
        return error_response("username or user_id is required", "VALIDATION_ERROR")

    repo = get_repo()

    try:
        if username and not user_id:
            user, _ = get_user_peer_context(repo, username)
            if user is None:
                return error_response("User not found", "USER_NOT_FOUND")
            user_id = user["user_id"]

        notifications = repo.get_notifications_by_user_id(user_id, only_unread=only_unread)
        return ok_response(
            data={"notifications": notifications},
            message="Notifications fetched"
        )
    except Exception as ex:
        return error_response(str(ex), "LIST_NOTIFICATIONS_FAILED")

# Đánh dấu thông báo đã đọc
@app.route('/notifications/read', methods=['POST'])
def mark_notifications_read(headers="guest", body="anonymous"):
    payload = parse_json_body(body)
    if payload is None:
        return error_response("Invalid JSON body", "INVALID_JSON")

    notification_ids = payload.get("notification_ids", [])
    if not isinstance(notification_ids, list) or not notification_ids:
        return error_response("notification_ids must be a non-empty list", "VALIDATION_ERROR")

    try:
        ids = [int(i) for i in notification_ids]
    except (TypeError, ValueError):
        return error_response("notification_ids contains invalid value", "VALIDATION_ERROR")

    repo = get_repo()

    try:
        affected = repo.mark_notifications_read(ids)
        return ok_response(
            data={"affected": affected},
            message="Notifications marked as read"
        )
    except Exception as ex:
        return error_response(str(ex), "MARK_NOTIFICATIONS_FAILED")

@app.route("/echo", methods=["POST"])
def echo(headers="guest", body="anonymous"):
    print("[SampleApp] received body {}".format(body))

    try:
        message = json.loads(body)
        data = {"received": message }
        # Convert to JSON string
        json_str = json.dumps(data)
        return (json_str.encode("utf-8"))
    except json.JSONDecodeError:
        data = {"error": "Invalid JSON"}
        # Convert to JSON string
        json_str = json.dumps(data)
        return (json_str.encode("utf-8"))


@app.route('/hello', methods=['PUT'])
async def hello(headers, body):
    """
    Handle greeting via PUT request.

    This route prints a greeting message to the console using the provided headers
    and body.

    :param headers (str): The request headers or user identifier.
    :param body (str): The request body or message payload.
    """
    print("[SampleApp] ['PUT'] **ASYNC** Hello in {} to {}".format(headers, body))
    data =  {"id": 1, "name": "Alice", "email": "alice@example.com"}

    # Convert to JSON string
    json_str = json.dumps(data)
    return (json_str.encode("utf-8"))

def create_sampleapp(ip, port):
    base_dir = Path(__file__).resolve().parent.parent
    db_path = base_dir / "db" / "chat.db"

    initialize_database(str(db_path))
    app.set_state("repository", ChatRepository(str(db_path)))
    app.set_state("sessions", {})
    app.set_state("runtime_events", [])
    app.set_state("stream_runtime", None)

    # Prepare and launch the RESTful application
    app.prepare_address(ip, port)
    app.run()

