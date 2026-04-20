#
# Copyright (C) 2026 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course.
#
# AsynapRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course
#

"""
daemon.httpadapter
~~~~~~~~~~~~~~~~~

This module provides a http adapter object to manage and persist 
http settings (headers, bodies). The adapter supports both
raw URL paths and RESTful route definitions, and integrates with
Request and Response objects to handle client-server communication.
"""

from .request import Request
from .response import Response
from .dictionary import CaseInsensitiveDict

import asyncio
import inspect
import socket

class HttpAdapter:
    """
    A mutable :class:`HTTP adapter <HTTP adapter>` for managing client connections
    and routing requests.

    The `HttpAdapter` class encapsulates the logic for receiving HTTP requests,
    dispatching them to appropriate route handlers, and constructing responses.
    It supports RESTful routing via hooks and integrates with :class:`Request <Request>` 
    and :class:`Response <Response>` objects for full request lifecycle management.

    Attributes:
        ip (str): IP address of the client.
        port (int): Port number of the client.
        conn (socket): Active socket connection.
        connaddr (tuple): Address of the connected client.
        routes (dict): Mapping of route paths to handler functions.
        request (Request): Request object for parsing incoming data.
        response (Response): Response object for building and sending replies.
    """

    __attrs__ = [
        "ip",
        "port",
        "conn",
        "connaddr",
        "routes",
        "request",
        "response",
    ]

    def __init__(self, ip, port, conn, connaddr, routes):
        """
        Initialize a new HttpAdapter instance.

        :param ip (str): IP address of the client.
        :param port (int): Port number of the client.
        :param conn (socket): Active socket connection.
        :param connaddr (tuple): Address of the connected client.
        :param routes (dict): Mapping of route paths to handler functions.
        """

        #: IP address.
        self.ip = ip
        #: Port.
        self.port = port
        #: Connection
        self.conn = conn
        #: Conndection address
        self.connaddr = connaddr
        #: Routes
        self.routes = routes
        #: Request
        self.request = Request()
        #: Response
        self.response = Response()

    def handle_client(self, conn, addr, routes):
        """
        Handle an incoming client connection.

        This method reads the request from the socket, prepares the request object,
        invokes the appropriate route handler if available, builds the response,
        and sends it back to the client.

        :param conn (socket): The client socket connection.
        :param addr (tuple): The client's address.
        :param routes (dict): The route mapping for dispatching requests.
        """

        # Connection handler.
        self.conn = conn        
        # Connection address.
        self.connaddr = addr
        # Request handler
        req = self.request
        # Response handler
        resp = self.response

        # Handle the request
        #msg = conn.recv(1024).decode()
        #----------------------------------------------------------------------------------------------------
        # non-blocking
        conn.setblocking(False)
        
        raw_data = bytearray()
        import time
        timeout = 5.0 
        start_time = time.time()
        header_end = None
        expected_total = None

        while True:
            # 1. against Slowloris Attack
            if time.time() - start_time > timeout:
                print("[HttpAdapter] Timeout: Client send data too slow.")
                break
                
            try:
                # 2. try to read data
                chunk = conn.recv(4096)
                
                if not chunk:
                    break
                    
                raw_data.extend(chunk)
                start_time = time.time() 

                # Determine header end and expected total bytes (Content-Length) once headers are complete.
                if header_end is None:
                    idx = raw_data.find(b"\r\n\r\n")
                    delim_len = 4
                    if idx == -1:
                        idx = raw_data.find(b"\n\n")
                        delim_len = 2

                    if idx != -1:
                        header_end = idx + delim_len
                        header_bytes = bytes(raw_data[:idx])
                        header_text = header_bytes.decode("latin-1", errors="ignore")
                        content_length = 0
                        for line in header_text.splitlines():
                            if line.lower().startswith("content-length:"):
                                try:
                                    content_length = int(line.split(":", 1)[1].strip() or "0")
                                except Exception:
                                    content_length = 0
                                break

                        expected_total = header_end + max(0, content_length)

                        # For requests without body (or Content-Length: 0), we can finish once headers are present.
                        if expected_total == header_end:
                            break

                # If we know total bytes expected, stop when full request is received.
                if expected_total is not None and len(raw_data) >= expected_total:
                    break
                    
            except BlockingIOError:
                # 4. buffer is empty
                time.sleep(0.01)
                continue
            except socket.error as e:
                print(f"[HttpAdapter] socket error: {e}")
                break
            
        if not bytes(raw_data).strip():
            print("[HttpAdapter] no data, disconnect.")
            conn.close()
            return 

        # Decode raw data into string
        msg = bytes(raw_data).decode("utf-8", errors="ignore")
        #----------------------------------------------------------------------------------------------------

        #req.prepare(msg, routes)
        try:
            req.prepare(msg, routes)
        except ValueError:
            print("[HttpAdapter] Client gửi HTTP Request sai định dạng (thiếu Method/Path/Version).")
            conn.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\n")
            conn.close()
            return

        # Ensure app handlers can infer client source IP if no proxy header is present.
        if isinstance(addr, tuple) and len(addr) > 0 and addr[0]:
            req.headers.setdefault("Remote-Addr", str(addr[0]))

        print("[HttpAdapter] Invoke handle_client connection {}".format(addr))

        if req.method == "OPTIONS":
            print("[HttpAdapter] Intercepted OPTIONS preflight request for CORS")
            cors_response = (
                "HTTP/1.1 204 No Content\r\n"
                "Access-Control-Allow-Origin: *\r\n"
                "Access-Control-Allow-Methods: POST, GET, PUT, OPTIONS, DELETE\r\n"
                "Access-Control-Allow-Headers: Content-Type, Authorization, Cookie\r\n"
                "\r\n"
            ).encode('utf-8')
            conn.sendall(cors_response)
            conn.close()
            return

        # Handle request hook
        if req.hook:
            # Chạy hàm chức năng (App Hook) tương ứng với Route
            # (Phần này Thành viên 3 và 4 sẽ viết logic bên trong hook)
            if inspect.iscoroutinefunction(req.hook):
                hook_data = asyncio.run(req.hook(headers=req.headers, body=req.body))
            else:
                hook_data = req.hook(headers=req.headers, body=req.body)

            resp.headers["Content-Type"] = "application/json"

            if isinstance(hook_data, dict) and "body" in hook_data:
                body = hook_data.get("body", b"")
                status_code = hook_data.get("status_code", 200)
                reason = hook_data.get("reason", "OK")
                headers = hook_data.get("headers", {})
                cookies = hook_data.get("cookies", {})

                try:
                    resp.status_code = int(status_code)
                except (TypeError, ValueError):
                    resp.status_code = 200

                if reason:
                    resp.reason = str(reason)

                if isinstance(headers, dict):
                    for key, value in headers.items():
                        if key:
                            resp.headers[str(key)] = str(value)

                if isinstance(cookies, dict):
                    for key, value in cookies.items():
                        if key:
                            resp.cookies[str(key)] = str(value)

                response_bytes = resp.build_response(req, envelop_content=body)
            else:
                response_bytes = resp.build_response(req, envelop_content=hook_data)
        else:
            # Nếu không khớp route nào, build response mặc định (VD: 404 Not Found)
            response_bytes = resp.build_response(req)

        # Gửi dữ liệu trả về cho client
        if response_bytes:
            try:
                conn.sendall(response_bytes)
            except BlockingIOError:
                # Xử lý an toàn: Nếu buffer ghi TCP của HĐH bị đầy, bỏ qua hoặc thiết lập vòng lặp send
                pass
            except socket.error as e:
                print(f"[HttpAdapter] Lỗi khi gửi dữ liệu: {e}")
                
        # Hoàn thành 1 chu kỳ request-response, đóng kết nối
        conn.close()

    async def handle_client_coroutine(self, reader, writer):
        """
        Handle an incoming client connection using stream reader writer asynchronously.

        This method reads the request from the socket, prepares the request object,
        invokes the appropriate route handler if available, builds the response,
        and sends it back to the client.

        :param conn (socket): The client socket connection.
        :param addr (tuple): The client's address.
        :param routes (dict): The route mapping for dispatching requests.
        """
        # Request handler
        req = self.request
        # Response handler
        resp = self.response

        print("[HttpAdapter] Invoke handle_client_coroutine connection {})".format(addr))
        addr = writer.get_extra_info("peername")

        # TODO Handle the request asynchronously
        msg = await reader.read(1024)


        req.prepare(msg.decode("utf-8"), routes={})

        # Handle request hook
        if req.hook:
            #
            # TODO: handle for App hook here
            #
            response = ""

        # Build response
        #print("[HttpAdapter] Start **ASYNC** build_response with type {}".format(type(req)))
        response = resp.build_response(req)

        # Send all the response asynchronously
        writer.write(response)
        await writer.drain()

    def extract_cookies(self, req, resp=None):
        """
        Build cookies from the :class:`Request <Request>` headers.

        :param req:(Request) The :class:`Request <Request>` object.
        :param resp: (Response) The res:class:`Response <Response>` object.
        :rtype: cookies - A dictionary of cookie key-value pairs.
        """
        cookies = {}
        headers = getattr(req, "headers", {}) or {}
        raw_cookie = ""
        if isinstance(headers, dict):
            raw_cookie = headers.get("Cookie", headers.get("cookie", ""))

        if raw_cookie:
            for pair in str(raw_cookie).split(";"):
                item = pair.strip()
                if not item or "=" not in item:
                    continue
                key, value = item.split("=", 1)
                cookies[key.strip()] = value.strip()
        return cookies

    def build_response(self, req, resp):
        """Builds a :class:`Response <Response>` object 

        :param req: The :class:`Request <Request>` used to generate the response.
        :param resp: The  response object.
        :rtype: Response
        """
        response = Response()

        # Set encoding.
        response.encoding = "utf-8"
        response.raw = resp
        response.reason = response.raw.reason

        if isinstance(req.url, bytes):
            response.url = req.url.decode("utf-8")
        else:
            response.url = req.url

        # Add new cookies from the server.
        response.cookies = self.extract_cookies(req)

        # Give the Response some context.
        response.request = req
        response.connection = self

        return response

    def build_json_response(self, req, resp):
        """Builds a :class:`Response <Response>` object from JSON data

        :param req: The :class:`Request <Request>` used to generate the response.
        :param resp: The  response object.
        :rtype: Response
        """
        response = Response(req)

        # Set encoding.
        response.raw = resp

        if isinstance(req.url, bytes):
            response.url = req.url.decode("utf-8")
        else:
            response.url = req.url

        # Give the Response some context.
        response.request = req
        response.connection = self

        return response


    # def get_connection(self, url, proxies=None):
        # """Returns a url connection for the given URL. 

        # :param url: The URL to connect to.
        # :param proxies: (optional) A Requests-style dictionary of proxies used on this request.
        # :rtype: int
        # """

        # proxy = select_proxy(url, proxies)

        # if proxy:
            # proxy = prepend_scheme_if_needed(proxy, "http")
            # proxy_url = parse_url(proxy)
            # if not proxy_url.host:
                # raise InvalidProxyURL(
                    # "Please check proxy URL. It is malformed "
                    # "and could be missing the host."
                # )
            # proxy_manager = self.proxy_manager_for(proxy)
            # conn = proxy_manager.connection_from_url(url)
        # else:
            # # Only scheme should be lower case
            # parsed = urlparse(url)
            # url = parsed.geturl()
            # conn = self.poolmanager.connection_from_url(url)

        # return conn


    def add_headers(self, request):
        """
        Add headers to the request.

        This method is intended to be overridden by subclasses to inject
        custom headers. It does nothing by default.

        
        :param request: :class:`Request <Request>` to add headers to.
        """
        pass

    def build_proxy_headers(self, proxy):
        """Returns a dictionary of the headers to add to any request sent
        through a proxy. 

        :class:`HttpAdapter <HttpAdapter>`.

        :param proxy: The url of the proxy being used for this request.
        :rtype: dict
        """
        headers = {}
        #
        # TODO: build your authentication here
        #       username, password =...
        # we provide dummy auth here
        #
        username, password = ("user1", "password")

        if username and password:
            #headers["Proxy-Authorization"] = (username, password)
            import base64
            credential = f"{username}:{password}"
            
            encoded_credential = base64.b64encode(credential.encode('utf-8')).decode('utf-8')
            
            headers["Proxy-Authorization"] = f"Basic {encoded_credential}"

        return headers
