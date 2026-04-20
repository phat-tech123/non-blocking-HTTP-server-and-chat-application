# AsynapRous - Non-blocking HTTP Server & Hybrid Chat Application

## Giới thiệu

Đây là project môn Mạng máy tính, xây dựng một hệ thống server bao gồm:

- HTTP Server sử dụng cơ chế non-blocking
- Ứng dụng chat hybrid (Client-Server + Peer-to-Peer)
- Framework web nhẹ AsynapRous để xây dựng RESTful API

Mục tiêu là giúp hiểu rõ:

- TCP/IP
- HTTP protocol
- Xử lý nhiều kết nối (concurrency)
- Kiến trúc hệ thống mạng

---

## Kiến trúc hệ thống

### 1. Proxy Server

- Nhận request từ client
- Forward đến backend phù hợp
- Hỗ trợ load balancing (round-robin)

### 2. Backend Server

- Xử lý logic chính
- Quản lý HTTP request/response
- Hỗ trợ:
  - Multi-thread
  - Callback (event-driven)
  - Async/await (coroutine)

### 3. WebApp (AsynapRous)

- Framework RESTful đơn giản
- Định nghĩa API bằng decorator

Ví dụ:
app = AsynapRous()

@app.route('/login', methods=['POST'])
def login(headers, body):
return {'message': 'Logged in'}

---

## Non-blocking là gì?

- Socket không chờ I/O hoàn thành
- send()/recv() trả về ngay
- Xử lý được nhiều kết nối cùng lúc

Các cơ chế:

- Multi-thread
- Event-driven (callback)
- AsyncIO (coroutine)

---

## Cấu trúc thư mục

.
├── daemon/
│ ├── proxy.py
│ ├── backend.py
│ ├── httpadapter.py
│ ├── request.py
│ ├── response.py
│ ├── asynaprous.py
│ └── dictionary.py
│
├── apps/
│ └── sampleapp.py
│
├── config/
│ └── proxy.conf
│
├── start_proxy.py
├── start_backend.py
├── start_sampleapp.py
│
├── www/
├── static/
├── db/
└── cert/

---

## Cách chạy

### 1. Backend

python start_backend.py --server-ip 127.0.0.1 --server-port 9000

### 2. WebApp

python start_sampleapp.py --server-ip 127.0.0.1 --server-port 8000

### 3. Proxy

python start_proxy.py --server-ip 127.0.0.1 --server-port 8080

---

## Authentication

Hỗ trợ:

1. HTTP Header
   - WWW-Authenticate
   - Authorization

2. Cookie
   - Set-Cookie
   - Duy trì session

---

## Chat Application

### Giai đoạn Client-Server

- Đăng ký peer
- Lấy danh sách peer
- Tracker quản lý peer

### Giai đoạn Peer-to-Peer

- Gửi tin trực tiếp
- Broadcast message

### Tính năng

- Channel chat
- Gửi/nhận tin nhắn
- Thông báo realtime
- Không sửa/xóa tin

---

## API mẫu

/login
/get-list
/connect-peer
/broadcast-peer
/send-peer

---

## Yêu cầu kỹ thuật

- Chỉ dùng Python standard library
- Không dùng framework (Flask, Django,...)
- Tuân thủ PEP 8, PEP 257
- Bắt buộc non-blocking

---

## Chấm điểm

Demo (7 điểm):

- Authentication: 2
- Chat Client-Server: 1
- Chat P2P: 2
- Non-blocking: 2

Report: 3 điểm

---

## Ghi chú

- Không cần UI đẹp
- Tập trung vào networking và xử lý dữ liệu

---

## Iplementation hybrid chat application

Description Develop a hybrid network application that has a chat system (similar to skype), combining
both client-server and peer-to-peer (P2P) paradigms. The application must support channel management,
and synchronization across distributed peers.
Equipped webapp - AsynapRous The webapp support RESTful (Representational State Transfer) is
an architectural style for designing networked applications. It relies on standard HTTP methods [GET],
[POST], [PUT], [DELETE] to perform operations on resources, which are typically represented as URLs.
RESTful APIs are stateless, scalable, and easy to integrate across platforms. Custom route URLs allow
developers to define meaningful and readable endpoints. These routes improve clarity and make your API
friendly to handle more complex logic including query parameters or nested paths.
The provided framework also support 3 types of non-continous communication multi-thread approaches,
event-driven callbacks, or coroutine.
Core functional requirements the application has these following requirements
Initialization phase (Client-Server paradigm)
• Peer registration: When a new peer joins, it must submit its IP and port to the centralized server.
• Tracker update: The centralized server must maintain a tracking list of active peers.
• Peer discovery: Peers can request the current list of active peers from the server.
• Connection setup: Peers use the tracking list to initiate direct P2P connections.
Peer chatting phase (Peer-to-Peer Paradigm)
• Broadcast connection: A peer must broadcast messages to all connected peers.
• Direct peer communication: Peers exchange messages without routing through the centralized server
during live sessions.
Channel management
• Channel listing: Users can view channels they’ve joined.
• Message display: Each channel has a scrollable message window.
• Message submission: UI must support text input and submission.
• No edit/delete: Messages are immutable once sent.
• Notification system: Users must be notified when new messages arrive.
• Access control (Optional): Channels may define custom access policies.
Task requirements
• Non-blocking communication among multi-daemons. Student can based on callback or coroutine for
each daemon in each peer to communicate with other peers.
– Javascript is only allowed in client-side to perform user update or GUI interaction asynchronously.
– The backend must be implemented using the standard Python library, and the use of JavaScript
or existing web framework is strictly forbidden.
• Client-server process programming
• Protocol design in message communication and the processing procedure
– login API example http://IP:port/login/
– submit-info API example http://IP:port/submit-info/
– add-list API example http://IP:port/add-list/
– get-list API example http://IP:port/get-list/
– connect-peer API example http://IP:port/connect-peer/
– broadcast-peer API example http://IP:port/broadcast-peer/
– send-peer API example http://IP:port/send-peer/
• Concurrency
• Error Handling
Application and protocol design implement the design based on non-blocking protocol is mandatory.
The framework must be built by yourself.
Notice Continuous data flows or streaming processing may result in data being skipped or
truncated if not managed properly, so students are encouraged to consult their lab teacher for
guidance in selecting the most suitable mechanism for their interests and requirements. Stream
processing will be deferred and addressed in a future task as part of the HTTPv3 implementation.
Authentication handling implement the authentication handling and the cookies access control subsystem2.2.
Chat application implement the hybrid chat application.
After you finish the assignment, move your report to source code directory and compress the entire directory
into a single file named assignment STUDENTID.zip and submit to LMS.

## Implement non-blocking mechanisms

The implementation of non-blocking mechanisms relies on operating system services that allow I/O operations to be halted immediately rather than blocking execution. However, the responsibility for correctly managing ongoing communication and ensuring consistency is delegated to the application level. As a result, developers must design and implement appropriate handling logic to guarantee correctness and reliability in non-blocking communication systems.

When a communication is halted, there are multiple processing flows to be handled:

### Multi-thread

- Create a thread to handle the new created processing flows.

### Event-driven

- Relies on registering callbacks that are executed when an operation completes.
- Instead of waiting for I/O, the program continues running, and the event loop triggers the callback once the communication is completed and the data is ready.
- While powerful, it can lead to complex nested code structures, often referred to as "callback hell".

#### Variants:

- Futures / Promises: Allow chaining events by putting a placeholder for an object representing a result that will be available later.
- Pub/Sub Event Loop:
  - Uses a simple loop and sockets to listen for events and dispatch them to handlers.
  - Real implementations wrap low-level send()/receive() operations.

### Coroutine (asyncio, async/await)

- Represents a more readable approach to asynchronous I/O.
- The asyncio event loop schedules and runs these coroutines.
- Coroutines pause when waiting for I/O and resume when the operation completes.

Key points:

- asyncio is the framework for writing concurrent code using async/await syntax.
- StreamReader and StreamWriter are high-level APIs for handling I/O operations.
- Use asyncio.run() to start the event loop and run a coroutine until completion.

### AsyncIO Runner (Example)

class Runner:
def \_lazy_init(self):
if self.\_loop_factory is None:
self.\_loop = events.new_event_loop()
else:
self.\_loop = self.\_loop_factory()

    def run(self, coro, *, context=None):
        self._lazy_init()
        task = self._loop.create_task(coro, context=context)
        try:
            return self._loop.run_until_complete(task)

def run(main, \*, debug=None, loop_factory=None):
with Runner(debug=debug, loop_factory=loop_factory) as runner:
return runner.run(main)

### AsyncIO Event Loop (Example)

class BaseEventLoop(events.AbstractEventLoop):
def run_forever(self):
try:
while True:
self.\_run_once()

    def _run_once(self):
        event_list = self._selector.select(timeout)
        self._process_events(event_list)

### Table: Non-blocking Mechanisms

| Mechanism          | Types                        |
| ------------------ | ---------------------------- |
| Multi-thread       | Thread based                 |
| Callback           | Event-driven                 |
| Asyncio            | Coroutine                    |
| Future / Promise   | Event-driven, allow chaining |
| Pub/Sub Event Loop | Event-driven                 |

### Non-blocking JavaScript backend framework

JavaScript supports asynchronous communication in web frameworks. It allows sending a request to a server and continuing execution while waiting for the response. This approach makes web pages feel faster and more responsive.

### Node.js vs Bun

- Node.js started as a single-threaded runtime relying heavily on callbacks, and later added async/await.
- Bun is designed with multi-threading at its core, offering higher performance but requiring more resource management.

### Node.js vs NestJS

NestJS is a backend framework used to build powerful APIs. It provides a structured architecture that makes applications easier to develop and maintain.

Core components:

- Modules
- Controllers
- Providers (services/business logic)
- Decorators: @Module, @Controller, @Injectable, @Get, @Post
- Middleware

### Express vs Fastify

- Express: Uses a callback-based approach and has a traditional architecture.
- Fastify: Supports async/await, allowing cleaner asynchronous code without complex error handling.

### Important note

- React, Next.js are frontend frameworks and are not the focus.
- The course focuses on communication systems, not UI.
- Students are encouraged to build their own framework using non-blocking mechanisms.

### Framework comparison

| Framework | Types                         |
| --------- | ----------------------------- |
| Express   | Callback                      |
| Fastify   | Callback + coroutine          |
| NestJS    | Coroutine (async/await)       |
| Node.js   | Callback (legacy) + coroutine |

### Provided non-blocking inter-daemon connection

This module implements inter-daemon communication by:

- Accepting socket connections
- Delegating each client to HttpAdapter

Supported strategies:

- Multi-threading
- Callback/event-driven (selectors)
- Coroutine-based async/await

Selectable via the `mode_async` flag.

Supported features:

- Inter-daemon communication
- RESTful API handler

---

## Implement the authentication for HTTP server

### Description

To authenticate a user, there are two common approaches:

### HTTP Headers

- Defined in RFC 2617 and updated in RFC 7235
- Uses:
  - WWW-Authenticate: server requests authentication
  - Authorization: client sends login credentials

### Cookies (RFC 6265)

- Server sends Set-Cookie after successful login
- Browser stores the cookie
- Cookie is automatically included in future requests
- Helps maintain login session

### Notes

- It is recommended to use incognito mode when testing
- Browsers cache HTTP responses by default, which may affect testing

### Task requirements

Implement authentication mechanism based on the following RFCs:

- RFC 2617 – HTTP Authentication: Basic and Digest  
  https://www.rfc-editor.org/rfc/rfc2617

- RFC 7235 – HTTP/1.1 Authentication  
  https://www.rfc-editor.org/rfc/rfc7235

- RFC 6265 – HTTP State Management Mechanism (Cookies)  
  https://www.rfc-editor.org/rfc/rfc6265
