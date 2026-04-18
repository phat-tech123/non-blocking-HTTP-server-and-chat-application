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

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class Response():   
    """The :class:`Response <Response>` object, which contains a
    server's response to an HTTP request.

    Instances are generated from a :class:`Request <Request>` object, and
    should not be instantiated manually; doing so may produce undesirable
    effects.

    :class:`Response <Response>` object encapsulates headers, content, 
    status code, cookies, and metadata related to the request-response cycle.
    It is used to construct and serve HTTP responses in a custom web server.

    :attrs status_code (int): HTTP status code (e.g., 200, 404).
    :attrs headers (dict): dictionary of response headers.
    :attrs url (str): url of the response.
    :attrsencoding (str): encoding used for decoding response content.
    :attrs history (list): list of previous Response objects (for redirects).
    :attrs reason (str): textual reason for the status code (e.g., "OK", "Not Found").
    :attrs cookies (CaseInsensitiveDict): response cookies.
    :attrs elapsed (datetime.timedelta): time taken to complete the request.
    :attrs request (PreparedRequest): the original request object.

    Usage::

      >>> import Response
      >>> resp = Response()
      >>> resp.build_response(req)
      >>> resp
      <Response>
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
        "body",
        "reason",
    ]

    def __init__(self, request=None):
        """
        Initializes a new :class:`Response <Response>` object.

        : params request : The originating request object.
        """

        self._content = False
        self._content_consumed = False
        self._next = None

        #: Integer Code of responded HTTP Status, e.g. 404 or 200.
        self.status_code = None

        #: Case-insensitive Dictionary of Response Headers.
        #: For example, ``headers['content-type']`` will return the
        #: value of a ``'Content-Type'`` response header.
        self.headers = {}

        #: URL location of Response.
        self.url = None

        #: Encoding to decode with when accessing response text.
        self.encoding = None

        #: A list of :class:`Response <Response>` objects from
        #: the history of the Request.
        self.history = []

        #: Textual reason of responded HTTP Status, e.g. "Not Found" or "OK".
        self.reason = None

        #: A of Cookies the response headers.
        self.cookies = CaseInsensitiveDict()

        #: The amount of time elapsed between sending the request
        self.elapsed = datetime.timedelta(0)

        #: The :class:`PreparedRequest <PreparedRequest>` object to which this
        #: is a response.
        self.request = None

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

        :params mime_type (str): MIME type of the requested resource.

        :rtype str: Base directory path for locating the resource.

        :raises ValueError: If the MIME type is unsupported.
        """
        
        base_dir = ""

        # Validate header attr existence
        if not hasattr(self, "headers") or self.headers is None:
            self.headers = {}

        # Processing mime_type based on main_type and sub_type
        main_type, sub_type = mime_type.split('/', 1)
        print("[Response] Processing main_type={} sub_type={}".format(main_type,sub_type))
        if main_type == 'text':
            self.headers['Content-Type'] = 'text/{}'.format(sub_type)
            if sub_type == 'plain' or sub_type == 'css' or sub_type == 'csv' or sub_type == 'xml':
                base_dir = os.path.join(BASE_DIR, "static")
            elif sub_type == 'html':
                base_dir = os.path.join(BASE_DIR, "www")
            else:
                base_dir = os.path.join(BASE_DIR, "www")

        elif main_type == 'image':
            self.headers['Content-Type'] = 'image/{}'.format(sub_type)
            base_dir = os.path.join(BASE_DIR, "static")

        elif main_type == 'application':
            self.headers['Content-Type'] = 'application/{}'.format(sub_type)
            if sub_type == 'json' or sub_type == 'xml':
                base_dir = os.path.join(BASE_DIR, "apps")
            elif sub_type == 'zip':
                base_dir = os.path.join(BASE_DIR, "static")
            else:
                base_dir = os.path.join(BASE_DIR, "apps")
        
        elif main_type == 'video':
            self.headers['Content-Type'] = 'video/{}'.format(sub_type)

            if sub_type == 'mp4' or sub_type == 'mpeg':
                base_dir = os.path.join(BASE_DIR, "static")
            else:
                base_dir = os.path.join(BASE_DIR, "static")

        else:
            raise ValueError("Invalid MEME type: main_type={} sub_type={}".format(main_type,sub_type))

        return base_dir

    def build_content(self, path, base_dir):
        """
        Loads the objects file from storage space.

        :params path (str): relative path to the file.
        :params base_dir (str): base directory where the file is located.

        :rtype tuple: (int, bytes) representing content length and content data.
        """

        filepath = os.path.join(base_dir, os.path.normpath(path).lstrip("/\\"))

        #Prevent directory traversal
        if ".." in path or path.startswith("\\"):
            print("[Response] Security violation:", filepath)
            return -1, b""
        
        if not os.path.isfile(filepath):
            print("[Response] File not found:", filepath)
            return -1, b""

        print("[Response] Serving the object at location {}".format(filepath))
        try:
            with open(filepath, "rb") as f:
               content = f.read()
        except Exception as e:
            print("[Response] build_content exception: {}".format(e))
            return -1, b""
        return len(content), content

    def build_response_header(self, request):
        """
        Constructs the HTTP response headers based on the class:`Request <Request>
        and internal attributes.

        :params request (class:`Request <Request>`): incoming request object.

        :rtypes bytes: encoded HTTP response header.
        """
        code = self.status_code or 200
        reason = self.reason or "OK"
        status_line = f"HTTP/1.1 {code} {reason}\r\n"

        reqhdr = request.headers

        headers = {
            "Date": datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT"),
            "Server": "AsynapRous-Custom-Server",
            "Connection": "close",
        }

        if isinstance(self.headers, dict):
            for key, value in self.headers.items():
                headers[str(key)] = str(value)

        headers.setdefault("Content-Type", "text/html")
        headers["Content-Length"] = str(len(self._content or b""))

        header_lines = ""
        for key, value in headers.items():
            header_lines += f"{key}: {value}\r\n"
        if self.cookies:
            for key, value in self.cookies.items():
                header_lines += f"Set-Cookie: {key}={value}; Path=/; HttpOnly\r\n"
        
        full_header = status_line + header_lines + "\r\n"

        return full_header.encode('utf-8')

    def build_notfound(self):
        """
        Constructs a standard 404 Not Found HTTP response.

        :rtype bytes: Encoded 404 response.
        """

        return (
                "HTTP/1.1 404 Not Found\r\n"
                "Accept-Ranges: bytes\r\n"
                "Content-Type: text/html\r\n"
                "Content-Length: 13\r\n"
                "Cache-Control: max-age=86000\r\n"
                "Connection: close\r\n"
                "\r\n"
                "404 Not Found"
            ).encode('utf-8')

    def build_response(self, request, envelop_content=None):
        """
        Builds a full HTTP response including headers and content based on the request.

        :params request (class:`Request <Request>`): incoming request object.

        :rtype bytes: complete HTTP response using prepared headers and content.
        """
        print("[Response] Start build response with req {}".format(request))

        if envelop_content:
            self._content = envelop_content if isinstance(envelop_content, bytes) else str(envelop_content).encode('utf-8')
            self.headers["Content-Length"] = str(len(self._content))
            self._header = self.build_response_header(request)
            return self._header + self._content

        path = request.path
        if path == "/":
            path = "/index.html"

        mime_type = self.get_mime_type(path)
        print("[Response] {} path {} mime_type {}".format(request.method, request.path, mime_type))

        try:
            base_dir = self.prepare_content_type(mime_type)
        except Exception as e:
            print("[Response] MIME error:", e)
            return self.build_notfound()
        
        length, content = self.build_content(path, base_dir)
        if length == -1:
            return self.build_notfound()
        
        self._content = content
        self.headers["Content-Length"] = str(length)
        self._header = self.build_response_header(request)

        return self._header + self._content
