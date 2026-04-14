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
daemon.request
~~~~~~~~~~~~~~~~~

This module provides a Request object to manage and persist 
request settings (cookies, auth, proxies).
"""
from .dictionary import CaseInsensitiveDict
import base64

class Request():
    """The fully mutable "class" `Request <Request>` object,
    containing the exact bytes that will be sent to the server.

    Instances are generated from a "class" `Request <Request>` object, and
    should not be instantiated manually; doing so may produce undesirable
    effects.

    Usage::

      >>> import deamon.request
      >>> req = request.Request()
      ## Incoming message obtain aka. incoming_msg
      >>> r = req.prepare(incoming_msg)
      >>> r
      <Request>
    """
    __attrs__ = [
        "method",
        "url",
        "headers",
        "body",
        "_raw_headers",
        "_raw_body",
        "reason",
        "cookies",
        "routes",
        "hook",
        "auth"
    ]

    def __init__(self):
        #: HTTP verb to send to the server.
        self.method = None
        #: HTTP URL to send the request to.
        self.url = None
        #: dictionary of HTTP headers.
        self.headers = CaseInsensitiveDict()
        #: HTTP path
        self.path = None        
        # The cookies set used to create Cookie header
        self.cookies = {}
        #: request body to send to the server.
        self.body = None
        # The raw header
        self._raw_headers = ""
        #: The raw body
        self._raw_body = ""
        #: Routes
        self.routes = {}
        #: Hook point for routed mapped-path
        self.hook = None
        #: Authentication tuple (username, password)
        self.auth = None

    def extract_request_line(self, request):
        try:
            lines = request.splitlines()
            if not lines:
                return None, None, None
            first_line = lines[0]
            
            # An toàn hơn: Tách dựa trên khoảng trắng và kiểm tra số lượng phần tử
            parts = first_line.split()
            if len(parts) == 3:
                method, path, version = parts
            elif len(parts) == 2:
                method, path = parts
                version = "HTTP/1.1" # Default fallback
            else:
                raise ValueError("Malformed request line")

            if path == '/':
                path = '/index.html'
                
            return method, path, version
        except Exception as e:
            print(f"[Request Error] extract_request_line: {e}")
            raise ValueError("not enough values to unpack")
             
    def prepare_headers(self, raw_headers):
        """Prepares the given HTTP headers."""
        lines = raw_headers.split('\r\n')
        headers = {}
        # Bỏ qua dòng đầu tiên vì nó là Request Line (GET / HTTP/1.1)
        for line in lines[1:]:
            if ': ' in line:
                key, val = line.split(': ', 1)
                # Lưu ý: Không cần .lower() ở đây vì CaseInsensitiveDict sẽ tự lo
                headers[key] = val
        return headers

    def fetch_headers_body(self, request):
        """Prepares the given HTTP headers."""
        # Split request into header section and body section
        # HTTP quy định kết thúc header bằng 2 dấu ngắt dòng liên tiếp
        parts = request.split("\r\n\r\n", 1)  

        _headers = parts[0]
        _body = parts[1] if len(parts) > 1 else ""
        return _headers, _body

    def prepare(self, request, routes=None):
        """Prepares the entire request with the given parameters."""

        # 1. Prepare the request line from the request header
        print("[Request] prepare request msg:\n{}".format(request.splitlines()[0] if request else "EMPTY"))
        self.method, self.path, self.version = self.extract_request_line(request)
        print("[Request] {} path {} version {}".format(self.method, self.path, self.version))

        # 2. Tách Header và Body
        self._raw_headers, self._raw_body = self.fetch_headers_body(request)
        
        # 3. Phân tích Headers và nạp vào CaseInsensitiveDict (Sửa lỗi NoneType)
        header_dict = self.prepare_headers(self._raw_headers)
        self.headers = CaseInsensitiveDict(header_dict)

        # 4. Gán Body
        self.body = self._raw_body

        # @bksysnet Preapring the webapp hook with AsynapRous instance
        # The default behaviour with HTTP server is empty routed
        if routes and routes != {}:
            self.routes = routes
            print("[Request] Routing METHOD {} path {}".format(self.method, self.path))
            self.hook = routes.get((self.method, self.path))
            print("[Request] Hook mapped for request")

        # 5. Phân tích Cookie (RFC 6265)
        raw_cookie = self.headers.get('cookie', '')
        if raw_cookie:
            # Tách các cặp cookie cách nhau bằng dấu chấm phẩy
            cookie_pairs = raw_cookie.split(';')
            for pair in cookie_pairs:
                if '=' in pair:
                    k, v = pair.strip().split('=', 1)
                    self.cookies[k] = v

        # 6. Phân tích Authentication (RFC 2617 - Basic Auth)
        raw_auth = self.headers.get('authorization', '')
        if raw_auth.lower().startswith('basic '):
            # Lấy phần chuỗi đã mã hóa Base64 phía sau chữ "Basic "
            encoded_str = raw_auth.split(' ', 1)[1]
            try:
                # Giải mã Base64 ra chuỗi "user:pass"
                decoded_str = base64.b64decode(encoded_str).decode('utf-8')
                if ':' in decoded_str:
                    username, password = decoded_str.split(':', 1)
                    self.auth = (username, password)
                    print(f"[Request] Basic Auth decoded for user: {username}")
            except Exception as e:
                print(f"[Request] Error decoding Basic Auth: {e}")

        return

    def prepare_body(self, data, files=None, json=None):
        self.body = data
        self.prepare_content_length(self.body)
        return

    def prepare_content_length(self, body):
        if body:
            # Nếu body là string, tính len encode utf-8. Nếu là bytes, tính trực tiếp.
            length = len(body.encode('utf-8')) if isinstance(body, str) else len(body)
            self.headers["Content-Length"] = str(length)
        else:
            self.headers["Content-Length"] = "0"
        return

    def prepare_auth(self, auth, url=""):
        """Dùng cho Proxy/Client: Đóng gói user/pass thành header Basic Auth"""
        if isinstance(auth, tuple) and len(auth) == 2:
            credential = f"{auth[0]}:{auth[1]}"
            encoded_credential = base64.b64encode(credential.encode('utf-8')).decode('utf-8')
            self.headers["Authorization"] = f"Basic {encoded_credential}"
            self.auth = auth
        return

    def prepare_cookies(self, cookies):
        """Đóng gói Dict cookie thành chuỗi header hợp lệ"""
        if isinstance(cookies, dict) and cookies:
            cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
            self.headers["Cookie"] = cookie_str
