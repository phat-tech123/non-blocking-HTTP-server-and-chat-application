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
        # LỖI 4 FIX: Khai báo biến self.auth để chuẩn hóa OOP
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
            # LỖI 2 FIX: Trả về đủ 3 giá trị None để không bị ValueError unpack
            return None, None, None
             
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

        # Prepare the request line from the request header
        print("[Request] prepare request msg:\n{}".format(request.splitlines()[0] if request else "EMPTY"))
        
        # Split header and body
        raw_headers, raw_body = self.fetch_headers_body(request)
        self._raw_headers = raw_headers
        self._raw_body = raw_body

        # Extract request line
        self.method, self.path, self.version = self.extract_request_line(request)
        print("[Request] {} path {} version {}".format(self.method, self.path, self.version))

        # Prepare headers
        header_dict = self.prepare_headers(self._raw_headers)
        self.headers = CaseInsensitiveDict(header_dict)
        
        # Gán Body
        self.body = self._raw_body

        self.cookies = self.parse_cookies(self.headers.get('cookie', ''))
        self.prepare_auth()

        # @bksysnet Preapring the webapp hook with AsynapRous instance
        # The default behaviour with HTTP server is empty routed
        if routes and routes != {}:
            self.routes = routes
            print("[Request] Routing METHOD {} path {}".format(self.method, self.path))
            self.hook = routes.get((self.method, self.path))
            print("[Request] Hook mapped for request")
            
        return
    
    def parse_cookies(self, cookie_header):
        cookies = {}
        if not cookie_header:
            return cookies

        pairs = cookie_header.split(";")
        for pair in pairs:
            if "=" in pair:
                key, value = pair.strip().split("=", 1)
                cookies[key] = value
        return cookies

    def prepare_body(self, data, files=None, json=None):
        self.body = data
        self.prepare_content_length(self.body)
        return

    def prepare_content_length(self, body):
        if body:
            # LỖI 3 FIX: Đếm dung lượng Bytes thay vì đếm số ký tự (len of chars)
            length = len(body.encode('utf-8')) if isinstance(body, str) else len(body)
            self.headers["Content-Length"] = str(length)
        else:
            self.headers["Content-Length"] = "0"
        return

    # LỖI 1 FIX: Thêm tham số mặc định auth=None để chống văng lỗi TypeError
    def prepare_auth(self, auth=None, url=""):
        auth_header = self.headers.get('Authorization')
        if auth_header and auth_header.startswith('Basic '):
            try:
                encoded_credentials = auth_header.split(' ', 1)[1]
                decoded = base64.b64decode(encoded_credentials).decode('utf-8')
                if ':' in decoded:
                    user, pwd = decoded.split(':', 1)
                    self.auth = {'username': user, 'password': pwd}
            except Exception:
                self.auth = None
        return

    def prepare_cookies(self, cookies):
        self.headers["Cookie"] = cookies
