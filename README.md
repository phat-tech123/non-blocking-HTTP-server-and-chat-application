# Non-blocking HTTP Server and Chat Application

Tài liệu này dùng cho tất cả thành viên trong nhóm.

Mục tiêu của README:

- Hướng dẫn chạy đầy đủ frontend và backend theo thứ tự phù hợp.
- Hướng dẫn cấu hình `env.js` cho frontend.
- Hướng dẫn chạy proxy cùng backend và frontend theo luồng thực tế.

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

### 3) Khởi động frontend

```powershell
python -m http.server 5500
```

Thiết lập `env.js` trước khi mở web app:

1. Tạo file `www/env.js` từ file mẫu:

```powershell
Copy-Item .\www\env.example.js .\www\env.js
```

2. Mở `www/env.js` và chỉnh `API_BASE` theo backend thực tế. Ví dụ:

```javascript
window.APP_CONFIG = {
  API_BASE: "http://192.168.1.10:2026",
};
```

Ghi chú:

- Frontend hiện đọc API URL từ `www/env.js` (không dùng `localStorage` cho API base nữa).
- Nếu `env.js` thiếu `API_BASE`, frontend sẽ fallback về `http://<host-hien-tai>:2026`.

Truy cập:

```text
http://127.0.0.1:5500
```

Khi mở URL trên, trang sẽ tự chuyển đến login:

```text
http://127.0.0.1:5500/www/login.html
```

### 4) Truy cập từ máy khác trong cùng mạng LAN

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
4. Đặt API backend trong `www/env.js` thành:

```text
http://192.168.1.10:2026
```

Không cần dùng lệnh cmd/PowerShell khi chỉ muốn mở và dùng web app qua browser.

Yêu cầu:

- Mở firewall cho các cổng dùng để test (ít nhất `2026` và `5500` nếu có frontend).

### 5) (Tùy chọn) Chạy proxy với backend và frontend

Mục này là luồng chạy thực tế trên browser:

- Frontend gọi API qua Proxy.
- Proxy forward request đến backend app (`start_sampleapp.py`).

#### 5.1 Chạy backend app

Mở terminal 1:

```powershell
python start_sampleapp.py --server-ip 0.0.0.0 --server-port 2026
```

#### 5.2 Cấu hình proxy trỏ tới backend app

Sửa `config/proxy.conf` theo IP máy chạy backend/proxy. Ví dụ IP máy là `192.168.1.10`:

```text
host "192.168.1.10:8080" {
  proxy_pass http://192.168.1.10:2026;
}
```

Ghi chú:

- Chỉ cần 1 host mapping là đủ cho frontend dùng qua proxy.
- Nếu test local trên cùng máy, có thể dùng:

```text
host "127.0.0.1:8080" {
  proxy_pass http://127.0.0.1:2026;
}
```

#### 5.3 Chạy proxy

Mở terminal 2:

```powershell
python start_proxy.py --server-ip 0.0.0.0 --server-port 8080
```

#### 5.4 Cấu hình frontend gọi qua proxy

Mở `www/env.js`, đặt `API_BASE` là URL proxy (không trỏ trực tiếp backend):

```javascript
window.APP_CONFIG = {
  API_BASE: "http://192.168.1.10:8080",
};
```

#### 5.5 Chạy frontend và truy cập browser

Mở terminal 3:

```powershell
python -m http.server 5500
```

Mở browser:

```text
http://192.168.1.10:5500/www/login.html
```

Khi đăng ký/đăng nhập/chat trên giao diện web, request sẽ đi theo luồng:

`Frontend (5500) -> Proxy (8080) -> Backend app (2026)`

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
