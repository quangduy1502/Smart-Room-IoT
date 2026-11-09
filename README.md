# Hệ Thống Giám Sát Vi Khí Hậu Phòng Học & Điều Khiển Làm Mát Thông Minh

> **Báo cáo Bài tập lớn môn Internet of Things (IoT) - Học kỳ 261**  
> **Trường Đại học Bách Khoa - ĐHQG TP. Hồ Chí Minh**  
> **Giảng viên hướng dẫn:** TS. Lê Trọng Nhân  


---

## 1. Giới thiệu đề tài
Hệ thống đo đạc nhiệt độ và độ ẩm phòng học theo thời gian thực sử dụng cảm biến công nghiệp Modbus RTU/RS485. Dữ liệu từ Node cảm biến (YoloUNO A) được truyền không dây qua giao thức ESP-NOW sang Node điều khiển (YoloUNO B), sau đó qua cổng USB Serial lên Laptop Gateway (Python). Gateway đóng vai trò tổng hợp dữ liệu, đẩy lên CoreIOT qua MQTT và tiếp nhận lệnh điều khiển 2 chiều (RPC) để bật/tắt thiết bị làm mát (mô phỏng bằng LED).

Hệ thống hỗ trợ giám sát và điều khiển trên 3 giao diện độc lập:
1. **Webserver nhúng trên ESP32 (T07):** Điện thoại kết nối trực tiếp vào Wi-Fi SoftAP của Node B để điều khiển local.
2. **Dashboard trên Laptop Gateway (T10):** Giao diện Flask trên máy tính (`http://localhost:5000`) điều khiển qua cổng USB Serial.
3. **Dashboard Đám mây CoreIOT (T11):** Giám sát đồ thị lịch sử, trạng thái thiết bị và điều khiển từ xa.

---

## 2. Bảng phân công thành viên

| STT | Họ và tên | MSSV | Vai trò chính | Tiêu chí công nghệ phụ trách | Tỷ lệ |
| :---: | :--- | :---: | :--- | :--- | :---: |
| 1 | Pan Yi Ting | 2414089 | Firmware & Phần cứng | **T02** (Modbus RS485), **T06** (ESP-NOW), **T07** (Web ESP32) | 35% |
| 2 | Dương Gia Huy | 2211155 | Gateway & Giao diện | **T08** (IoT Gateway), **T10** (Flask Local UI), HTML Web ESP32 | 35% |
| 3 | Bùi Quang Duy | 2410482 | Cloud & Kiểm thử | **T11** (Dashboard), **T12** (RuleChain), **T13** (Notification) | 30% |

---

## 3. Kiến trúc hệ thống
```text
[Cảm biến Modbus RS485]
          │ (UART RS485)
          ▼
   [YoloUNO Node A]  ──(ESP-NOW Channel 1)──►  [YoloUNO Node B]
                                                      │ (USB Serial 115200)
                                                      ▼
                                              [Laptop Gateway]
                                                      │ (MQTT Internet)
                                                      ▼
                                              [Server CoreIOT]
```

---

## 4. Cấu trúc thư mục kho mã nguồn
```text
.
├── firmware/
│   ├── node_a_sensor/       # Mã nguồn Node A: Modbus RS485 & ESP-NOW phát
│   └── node_b_control/      # Mã nguồn Node B: ESP-NOW nhận, SoftAP, Webserver & Serial
├── gateway/
│   ├── simulator/           # Trình giả lập Node B (mock_node_b.py) phục vụ test sớm
│   ├── main.py              # Chương trình chính IoT Gateway
│   ├── app_flask.py         # Web dashboard cục bộ trên Laptop (T10)
│   ├── requirements.txt     # Danh sách thư viện Python (pyserial, paho-mqtt, flask)
│   └── .env.example         # File mẫu cấu hình cổng COM, MQTT Broker, Token
├── coreiot/                 # File export cấu hình Dashboard, RuleChain JSON
├── docs/                    # Sơ đồ đấu dây, datasheet cảm biến, tài liệu thiết kế
├── tests/                   # Bảng số liệu thực nghiệm (độ trễ, tỷ lệ mất gói 100 gói)
└── README.md
```

---

## 5. Chuẩn giao tiếp dữ liệu (Quy ước chung)

* **Baudrate Serial:** `115200`
* **Wi-Fi Channel:** Cố định `Channel 1`
* **Tên trường trạng thái LED đồng bộ 100%:** `cooling_state` (`true` / `false`)

### Gói tin Serial Telemetry (Node B -> Gateway):
```json
{"type":"telemetry", "seq":12, "temperature":28.5, "humidity":65.2, "cooling_state":false}
```

### Lệnh điều khiển Serial Command (Gateway -> Node B):
```json
{"type":"command", "cmd":"set_cooling", "state":true, "request_id":42}
```

### Lệnh MQTT Telemetry (Gateway -> CoreIOT):
* **Topic:** `v1/devices/me/telemetry`
* **Payload:** `{"temperature":28.5, "humidity":65.2, "cooling_state":false}`

---

## 6. Hướng dẫn cài đặt & Khởi chạy nhanh

### Khởi chạy Simulator giả lập:
```bash
cd gateway/simulator
python mock_node_b.py
```

### Cài đặt môi trường Gateway:
```bash
cd gateway
pip install -r requirements.txt
cp .env.example .env
# Chỉnh sửa COM port và Access Token trong file .env
python main.py
```
