# Non-blocking HTTP Server and Chat Application

Tài liệu này dùng cho tất cả thành viên trong nhóm.

Mục tiêu của README:

- Phần 1: Hướng dẫn chạy đầy đủ frontend và backend theo thứ tự phù hợp, kèm cách truy cập test trên máy thật cùng mạng LAN.
- Phần 2: Hướng dẫn test ở server với 2 loại môi trường: nhiều máy ảo trên cùng 1 máy và các máy thực cùng mạng LAN.

## Điều kiện chung

- Windows (khuyến nghị PowerShell).
- Python 3.13 trở lên.
- Node.js 18+ nếu frontend dùng React.
- Quyền chạy script PowerShell.

Ví dụ đường dẫn project (chỉ là ví dụ):

```powershell
D:/duong-dan-den-project/non-blocking-HTTP-server-and-chat-application
```

---

## PHẦN 1 - Hướng dẫn chạy đầy đủ frontend và backend

### 1) Thiết lập môi trường backend

Di chuyển vào thư mục project:

```powershell
cd D:/duong-dan-den-project/non-blocking-HTTP-server-and-chat-application
```

Tạo và kích hoạt virtual environment:

```powershell
python -m venv .venv-1
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv-1\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

### 2) Khởi động backend

Để người dùng mới dễ làm quen, phần này chỉ chạy **1 backend server** trên 1 máy.

Ví dụ chạy backend ở máy A:

```powershell
python start_sampleapp.py --server-ip 0.0.0.0 --server-port 2026
```

Lưu ý:

- Chạy `0.0.0.0` để máy khác trong LAN có thể truy cập.
- Test luồng peer-to-peer nhiều server được trình bày chi tiết ở PHẦN 2.

### 3) Khởi động frontend

```powershell
python -m http.server 5500
```

Truy cập:

```text
http://127.0.0.1:5500
```

Khi mở URL trên, trang sẽ tự chuyển đến login:

```text
http://127.0.0.1:5500/www/login.html
```

### 4) Truy cập test trên máy thật cùng mạng LAN

Giả sử backend chạy trên máy A:

- IP LAN máy A: `192.168.1.10`
- Port backend: `2026`

Từ máy B (hoặc máy bất kỳ trong cùng LAN), truy cập web app bằng browser:

1. Mở trình duyệt trên máy B.
2. Nhập URL frontend nếu frontend tĩnh chạy ở máy A cổng 5500:

```text
http://192.168.1.10:5500
```

Trang sẽ tự chuyển đến:

```text
http://192.168.1.10:5500/www/login.html
```

3. Đăng ký/đăng nhập trực tiếp trên giao diện web.
4. Nếu frontend có cấu hình API base URL, đặt thành:

```text
http://192.168.1.10:2026
```

Không cần dùng lệnh cmd/PowerShell khi chỉ muốn mở và dùng web app qua browser.

Yêu cầu:

- Mở firewall cho các cổng dùng để test (ít nhất `2026` và `5500` nếu có frontend).

---

## PHẦN 2 - Hướng dẫn test ở server

### A) Test với nhiều máy ảo trên cùng 1 máy

Áp dụng khi bạn dùng VMware/VirtualBox/Hyper-V hoặc container có IP riêng.

#### A.1 Chuẩn bị

- Tạo tối thiểu 2 VM: VM-A và VM-B.
- Đảm bảo VM-A và VM-B ping được nhau.
- Mỗi VM clone code và setup môi trường Python giống nhau.

#### A.2 Cấu hình ví dụ

- VM-A:
  - IP: `10.10.10.21`
  - HTTP: `2026`
  - Stream: `3126`
- VM-B:
  - IP: `10.10.10.22`
  - HTTP: `2027`
  - Stream: `3127`

#### A.3 Chạy service

Trên VM-A:

```powershell
python start_sampleapp.py --server-ip 0.0.0.0 --server-port 2026
```

Trên VM-B:

```powershell
python start_sampleapp.py --server-ip 0.0.0.0 --server-port 2027
```

#### A.4 Test luồng chính

Từ VM-A (hoặc máy test thứ ba), gọi lần lượt:

1. `/register` cho user A với `port=3126` qua IP VM-A.
2. `/register` cho user B với `port=3127` qua IP VM-B.
3. `/login` A và B.
4. `/peers/connect` từ A sang B.
5. `/messages/direct` từ A sang B.

Kỳ vọng:

- `runtime_connect.ok = true`
- `connection.status = CONNECTED`
- `delivery_mode = realtime_and_stored`

### B) Test với các máy thực cùng mạng LAN

#### B.1 Điều kiện

- Máy A và máy B cùng subnet LAN.
- Mỗi máy cài môi trường như phần 1.
- Mở firewall cho các cổng test.

#### B.2 Cấu hình ví dụ

- Máy A:
  - IP: `192.168.1.10`
  - HTTP: `2026`
  - Stream: `3126`
- Máy B:
  - IP: `192.168.1.11`
  - HTTP: `2027`
  - Stream: `3127`

#### B.3 Chạy service trên từng máy

Máy A:

```powershell
python start_sampleapp.py --server-ip 0.0.0.0 --server-port 2026
```

Máy B:

```powershell
python start_sampleapp.py --server-ip 0.0.0.0 --server-port 2027
```

#### B.4 Test API qua IP LAN

Ví dụ đăng ký nhanh:

```powershell
Invoke-RestMethod -Method POST -Uri http://192.168.1.10:2026/register -ContentType application/json -Body '{"username":"alice_lan","password":"123456","port":3126,"display_name":"Alice LAN"}'
Invoke-RestMethod -Method POST -Uri http://192.168.1.11:2027/register -ContentType application/json -Body '{"username":"bob_lan","password":"123456","port":3127,"display_name":"Bob LAN"}'
```

Sau đó login, connect, reconnect-active, direct message tương tự phần A.

### C) Checklist lỗi thường gặp

- `bind_failed`:
  - Stream port trùng HTTP port.
  - Port đã bị process khác sử dụng.
- `handshake_failed` hoặc `socket_error`:
  - Sai IP/port peer.
  - Firewall chặn.
  - Máy đích chưa chạy listener stream.
- `stored_only` thay vì realtime:
  - Chưa có connection `CONNECTED`.
  - Stream connection chưa establish thành công.

---

## API chính

- POST /register
- POST /login
- POST /logout
- GET /peers/active
- POST /peers/connect
- POST /peers/reconnect-active
- POST /connections/list
- POST /connections/update-status
- POST /messages/direct
- POST /notifications/list
- POST /notifications/read

## Chạy proxy và backend riêng (tùy chọn)

Backend:

```powershell
python start_backend.py --server-ip 0.0.0.0 --server-port 9000
```

Proxy:

```powershell
python start_proxy.py --server-ip 0.0.0.0 --server-port 8080
```

Lưu ý: `config/proxy.conf` đang có host/IP tĩnh, cần chỉnh theo môi trường thật trước khi dùng.
