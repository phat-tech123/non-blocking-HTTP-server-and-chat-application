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

from pathlib import Path
from uuid import uuid4

from daemon import AsynapRous
from db.repository import ChatRepository, initialize_database

app = AsynapRous()

# Convert data to JSON string
def json_response(data):
    return json.dumps(data).encode("utf-8")

# Standard success response
def ok_response(data=None, message="ok"):
    return json_response({"success": True, "message": message, "data": data})

# Standard error response
def error_response(message, code="BAD_REQUEST"):
    return json_response({"success": False, "error": code, "message": message})

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
    
# Get repository instance from app
def get_repo():
    repo = app.get_state("repository")
    if repo is None:
        raise RuntimeError("Repository is not initialized")
    return repo

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

    if isinstance(headers, dict):
        forwarded = headers.get("x-forwarded-for") or headers.get("X-Forwarded-For")
        real_ip = headers.get("x-real-ip") or headers.get("X-Real-IP")
        client_ip = headers.get("client-ip") or headers.get("Client-IP")
        remote_addr = headers.get("remote-addr") or headers.get("Remote-Addr")

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


@app.route('/register', methods=['POST'])
def register(headers="guest", body="anonymous"):
    payload = parse_json_body(body)
    if payload is None:
        return error_response("Invalid JSON body", "INVALID_JSON")

    err = require_fields(payload, ["username", "password", "port"])
    if err:
        return error_response(err, "VALIDATION_ERROR")

    username = str(payload["username"]).strip()
    password = str(payload["password"])
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

        # TODO: issue cookie/session id and attach Set-Cookie in HTTP response layer
        session_id = None

        return ok_response(
            data={
                "user_id": user_id,
                "username": username,
                "peer": peer,
                "session_id": session_id,
            },
            message="Register successful"
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

    err = require_fields(payload, ["username", "password", "port"])
    if err:
        return error_response(err, "VALIDATION_ERROR")

    username = str(payload["username"]).strip()
    password = str(payload["password"])
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
        # Xử lý user: user phải tồn tại, sau đó verify password
        with repo._connect() as conn:
            user = repo.get_user_by_username(conn, username)

            if user is None:
                return error_response("User not found", "USER_NOT_FOUND")

            user_id = user["user_id"]
            stored_hash = user.get("password_hash") or ""
            if not verify_password(password, stored_hash):
                return error_response("Invalid username or password", "AUTH_FAILED")

        # Cập nhật user status sau khi xác thực thành công
        user_row, _ = repo.update_user_status(user_id, "ACTIVE")

        # Cập nhật peer status + endpoint sau khi login thành công
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

        # TODO: issue session and Set-Cookie in HTTP response layer
        session_id = None

        return ok_response(
            data={
                "mode": "LOGIN",
                "user_id": user_id,
                "username": username,
                "peer": peer,
                "connections_updated": updated_connections,
                "session_id": session_id,
            },
            message="Login successful"
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

    err = require_fields(payload, ["username"])
    if err:
        return error_response(err, "VALIDATION_ERROR")

    username = str(payload["username"]).strip()
    if not username:
        return error_response("username must not be empty", "VALIDATION_ERROR")

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

        # TODO: invalidate session and clear cookie in HTTP response layer

        return ok_response(
            data={
                "connections_updated": updated_connections,
            },
            message="Logout successful"
        )
    except ValueError as ex:
        return error_response(str(ex), "BUSINESS_ERROR")
    except Exception as ex:
        return error_response(str(ex), "LOGOUT_FAILED")

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

    # Prepare and launch the RESTful application
    app.prepare_address(ip, port)
    app.run()

