# Hệ Thống Giám Sát Vi Khí Hậu Phòng Học & Điều Khiển Làm Mát Thông Minh

> **Báo cáo Bài tập lớn môn Internet of Things (IoT) - Học kỳ 261**  
> **Trường Đại học Bách Khoa - ĐHQG TP. Hồ Chí Minh**  
> **Giảng viên hướng dẫn:** TS. Lê Trọng Nhân  
> **Mục tiêu:** 8.0/8.0 Điểm công nghệ cốt lõi

---

## 1. Giới thiệu đề tài
Hệ thống đo đạc nhiệt độ và độ ẩm phòng học theo thời gian thực sử dụng cảm biến công nghiệp Modbus RTU/RS485. Dữ liệu từ Node cảm biến (YoloUNO A) được truyền không dây qua giao thức ESP-NOW sang Node điều khiển (YoloUNO B), sau đó qua cổng USB Serial lên Laptop Gateway (Python). Gateway đóng vai trò tổng hợp dữ liệu, đẩy lên CoreIOT qua MQTT và tiếp nhận lệnh điều khiển 2 chiều (RPC) để bật/tắt thiết bị làm mát (mô phỏng bằng LED).

Hệ thống hỗ trợ giám sát và điều khiển trên 3 giao diện độc lập:
1. **Webserver nhúng trên ESP32 (T07):** Điện thoại kết nối trực tiếp vào Wi-Fi SoftAP của Node B để điều khiển local.
2. **Dashboard trên Laptop Gateway (T10):** Giao diện Flask trên máy tính (`http://localhost:5000`) điều khiển qua cổng USB Serial.
3. **Dashboard Đám mây CoreIOT (T11):** Giám sát đồ thị lịch sử, trạng thái thiết bị và điều khiển từ xa.

---

## 2. Bảng phân công thành viên

| STT | Thành viên | Vai trò chính | Tiêu chí công nghệ phụ trách | Trọng số |
| :---: | :--- | :--- | :--- | :---: |
| 1 | **Thành viên A** | Firmware & Phần cứng | **T02** (Modbus RS485), **T06** (ESP-NOW), **T07** (Web ESP32) | 35% |
| 2 | **Thành viên B** | Gateway & Giao diện | **T08** (IoT Gateway), **T10** (Flask Local UI), HTML Web ESP32 | 35% |
| 3 | **Thành viên C** | Cloud & Báo cáo | **T11** (Dashboard), **T12** (RuleChain), **T13** (Notification) | 30% |

---

## 3. Kiến trúc luồng truyền thông
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

## 4. Khung cấu trúc thư mục (Repository Skeleton)

Từng thành viên chịu trách nhiệm phát triển mã nguồn trong thư mục được phân công:

```text
smart-room-iot/
├── firmware/
│   ├── node_a_sensor/           # [Thành viên A] Mã nguồn đọc cảm biến Modbus RS485 & ESP-NOW phát
│   └── node_b_control/          # [Thành viên A & B] Mã nguồn nhận ESP-NOW, host SoftAP, Webserver & Serial
├── gateway/
│   ├── simulator/               # [Thành viên B] Trình giả lập Node B (Mock 2 chiều phục vụ test sớm)
│   ├── main.py                  # [Thành viên B] Chương trình chính IoT Gateway Python (Serial <-> MQTT)
│   └── app_flask.py             # [Thành viên B] Giao diện Local Dashboard trên máy tính (T10)
├── coreiot/                     # [Thành viên C] File export Dashboard & RuleChain JSON
├── docs/                        # [Cả nhóm] Sơ đồ đấu dây, datasheet cảm biến, tài liệu thiết kế
├── tests/                       # [Thành viên C] Dữ liệu đo đạc thực nghiệm (100 gói ESP-NOW, độ trễ RPC)
├── Ke_Hoach_Phan_Cong_BTL_IoT.docx  # Tài liệu kế hoạch chi tiết BTL 8.0/8.0 điểm
└── README.md                    # Tài liệu đặc tả chung của dự án
```

---

## 5. Chuẩn giao tiếp dữ liệu & Quy ước ACK

* **Tốc độ Serial:** `115200 baud` (mỗi gói kết thúc bằng ký tự `\n`)
* **Kênh Wi-Fi:** Cố định cứng `Channel 1` cho cả Node A, Node B và SoftAP
* **Tên trường trạng thái LED (đồng bộ 100%):** `cooling_state` (`true` hoặc `false`)

### 5.1. Dữ liệu cảm biến đẩy lên (Telemetry)
* **Từ Node B sang Gateway qua USB Serial:**
  ```json
  {"type":"telemetry", "seq":12, "temperature":28.5, "humidity":65.2, "cooling_state":false}
  ```
* **Từ Gateway lên CoreIOT qua MQTT topic `v1/devices/me/telemetry`:**
  ```json
  {"temperature":28.5, "humidity":65.2, "cooling_state":false}
  ```

### 5.2. Lệnh điều khiển & Quy ước ACK (2-Way RPC)
* **Lệnh từ Gateway gửi xuống Node B:**
  ```json
  {"type":"command", "cmd":"set_cooling", "state":true, "request_id":42}
  ```
* **Node B phản hồi xác nhận lệnh (ACK):**
  ```json
  {"type":"ack", "request_id":42, "ok":true, "cooling_state":true}
  ```
* **Gói tin đồng bộ trạng thái tức thời (khi bấm web local):**
  ```json
  {"type":"event", "event":"state_changed", "cooling_state":true}
  ```
* **Quy định Timeout & Xử lý lỗi:**
  * Gateway gửi lệnh xuống Node B và chờ tối đa **2000 ms (2 giây)**.
  * Nếu quá 2 giây không nhận được gói ACK có đúng `request_id`, Gateway báo lỗi Timeout về CoreIOT:
    `{"ok": false, "error": "Node B timeout"}` để tránh treo giao diện.

---

## 6. Quy định làm việc nhóm trên Git & GitHub

1. **Không push trực tiếp lên nhánh `main`:** Nhánh `main` chỉ chứa các bản phát hành ổn định sau khi đã review và kiểm thử.
2. **Quy tắc tạo nhánh (Branching):**
   * Bạn A: `feature/firmware`
   * Bạn B: `feature/gateway`
   * Bạn C: `feature/coreiot`
3. **Quy trình Merge:** Hoàn thành tính năng trên nhánh của mình $\rightarrow$ Tạo **Pull Request (PR)** vào `main` $\rightarrow$ Nhờ thành viên khác review trước khi Merge.
4. **Bảo mật:** Không bao giờ đưa file `.env` chứa token thật lên GitHub (đã có sẵn quy tắc chặn trong `.gitignore`).
