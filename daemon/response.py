#
# Copyright (C) 2026 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course.
#
# AsynApRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course
#

"""
daemon.response
~~~~~~~~~~~~~~~~~

This module provides a :class: `Response <Response>` object to manage and persist 
response settings (cookies, auth, proxies), and to construct HTTP responses
based on incoming requests. 

The current version supports MIME type detection, content loading and header formatting
"""
import datetime
import os
import mimetypes
from .dictionary import CaseInsensitiveDict

# Thư mục gốc chứa web/static files. Để rỗng "" tức là thư mục hiện tại.
BASE_DIR = ""

class Response():   
    """The :class:`Response <Response>` object, which contains a
    server's response to an HTTP request.

    Instances are generated from a :class:`Request <Request>` object, and
    should not be instantiated manually; doing so may produce undesirable
    effects.

    :class:`Response <Response>` object encapsulates headers, content, 
    status code, cookies, and metadata related to the request-response cycle.
    It is used to construct and serve HTTP responses in a custom web server.
    """

    __attrs__ = [
        "_content",
        "_header",
        "status_code",
        "method",
        "headers",
        "url",
        "history",
        "encoding",
        "reason",
        "cookies",
        "elapsed",
        "request",
        "body"
    ]


    def __init__(self, request=None):
        """
        Initializes a new :class:`Response <Response>` object.

        : params request : The originating request object.
        """

        self._content = b"" # Khởi tạo là byte rỗng thay vì False
        self._header = b""
        self._content_consumed = False
        self._next = None

        #: Integer Code of responded HTTP Status, e.g. 404 or 200.
        self.status_code = 200

        #: Case-insensitive Dictionary of Response Headers.
        self.headers = CaseInsensitiveDict()

        #: URL location of Response.
        self.url = None

        #: Encoding to decode with when accessing response text.
        self.encoding = "utf-8"

        #: A list of :class:`Response <Response>` objects from
        #: the history of the Request.
        self.history = []

        #: Textual reason of responded HTTP Status, e.g. "Not Found" or "OK".
        self.reason = "OK"

        #: A dictionary of Cookies to send in the response headers.
        self.cookies = {}

        #: The amount of time elapsed between sending the request
        self.elapsed = datetime.timedelta(0)

        #: The :class:`PreparedRequest <PreparedRequest>` object to which this
        #: is a response.
        self.request = request


    def get_mime_type(self, path):
        """
        Determines the MIME type of a file based on its path.

        "params path (str): Path to the file.

        :rtype str: MIME type string (e.g., 'text/html', 'image/png').
        """
        try:
            mime_type, _ = mimetypes.guess_type(path)
        except Exception:
            return 'application/octet-stream'
        return mime_type or 'application/octet-stream'


    def prepare_content_type(self, mime_type='text/html'):
        """
        Prepares the Content-Type header and determines the base directory
        for serving the file based on its MIME type.
        """
        base_dir = BASE_DIR

        if not hasattr(self, "headers") or self.headers is None:
            self.headers = CaseInsensitiveDict()

        main_type, sub_type = mime_type.split('/', 1)
        print("[Response] Processing main_type={} sub_type={}".format(main_type,sub_type))
        
        if main_type == 'text':
            self.headers['Content-Type']='text/{}'.format(sub_type)
            if sub_type in ['plain', 'css']:
                base_dir = os.path.join(BASE_DIR, "static/")
            elif sub_type == 'html':
                base_dir = os.path.join(BASE_DIR, "www/")
        elif main_type == 'image':
            base_dir = os.path.join(BASE_DIR, "static/")
            self.headers['Content-Type']='image/{}'.format(sub_type)
        elif main_type == 'application':
            base_dir = os.path.join(BASE_DIR, "apps/")
            self.headers['Content-Type']='application/{}'.format(sub_type)
        else:
            self.headers['Content-Type'] = mime_type # Fallback an toàn

        return base_dir


    def build_content(self, path, base_dir):
        """
        Loads the objects file from storage space.
        """
        filepath = os.path.join(base_dir, path.lstrip('/'))
        print("[Response] Serving the object at location {}".format(filepath))
        
        try:
            # Sửa lỗi chặn: Đọc file an toàn dưới dạng byte
            if not os.path.exists(filepath):
                print("[Response] File not found.")
                return -1, b""
                
            with open(filepath, "rb") as f:
                content = f.read()
            return len(content), content
        except Exception as e:
            print("[Response] build_content exception: {}".format(e))
            return -1, b""


    def build_response_header(self, request):
        """
        Constructs the HTTP response headers based on the class:`Request <Request>`
        and internal attributes.
        """
        # 1. Khởi tạo dòng trạng thái (Status Line)
        status_line = f"HTTP/1.1 {self.status_code} {self.reason}\r\n"
        
        # 2. Xây dựng các Header bắt buộc
        headers = {
            "Content-Type": self.headers.get('Content-Type', 'text/html'),
            "Content-Length": str(len(self._content)),
            "Date": datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT"),
            "Server": "AsynapRous/1.0",
            "Connection": "close"
        }
        
        # Nếu có gài mã 401 Unauthorized từ bên ngoài, tự động thêm header đòi pass
        if self.status_code == 401:
            headers["WWW-Authenticate"] = 'Basic realm="AsynapRous_Secure_Area"'

        # 3. Ép kiểu dictionary thành chuỗi đúng chuẩn HTTP
        header_lines = ""
        for k, v in headers.items():
            header_lines += f"{k}: {v}\r\n"
            
        # 4. Nhét Cookie vào nếu có (Thực thi RFC 6265)
        if self.cookies:
            for k, v in self.cookies.items():
                header_lines += f"Set-Cookie: {k}={v}; Path=/\r\n"

        # 5. Chốt sổ bằng một dòng trống (\r\n) để phân cách Header và Body
        final_header_str = status_line + header_lines + "\r\n"
        
        # Lưu vào thuộc tính class
        self._header = final_header_str.encode('utf-8')
        return self._header


    def build_notfound(self):
        """
        Constructs a standard 404 Not Found HTTP response.
        """
        self.status_code = 404
        self.reason = "Not Found"
        self._content = b"<h1>404 Not Found</h1><p>The requested URL was not found on this server.</p>"
        self.headers['Content-Type'] = 'text/html'
        self.build_response_header(self.request)
        return self._header + self._content

    def build_unauthorized(self):
        """
        Constructs a standard 401 Unauthorized HTTP response.
        (Mới thêm: Dành cho test Basic Auth)
        """
        self.status_code = 401
        self.reason = "Unauthorized"
        self._content = b"<h1>401 Unauthorized</h1><p>Authentication is required to access this resource.</p>"
        self.headers['Content-Type'] = 'text/html'
        self.build_response_header(self.request)
        return self._header + self._content

    def build_response(self, request, envelop_content=None):
        """
        Builds a full HTTP response including headers and content based on the request.
        """
        print("[Response] Start build response with req path {}".format(request.path))
        self.request = request
        path = request.path

        # Mặc định trỏ về file index nếu chỉ gõ IP/
        if path == '/' or path == '':
            path = '/index.html'

        mime_type = self.get_mime_type(path)
        base_dir = self.prepare_content_type(mime_type)

        # Đọc nội dung file
        length, content = self.build_content(path, base_dir)
        
        if length == -1:
            return self.build_notfound()
            
        self._content = content
        
        # Đóng gói header
        self.build_response_header(request)

        # Ghép header và body (cả 2 đều là dạng bytes)
        return self._header + self._content
