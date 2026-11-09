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

## 2. Bảng phân công thành viên & Trạng thái triển khai

| STT | Thành viên | Vai trò chính | Tiêu chí công nghệ phụ trách | Trọng số | Trạng thái hiện tại |
| :---: | :--- | :--- | :--- | :---: | :---: |
| 1 | **Thành viên A** | Firmware & Phần cứng | **T02** (Modbus RS485), **T06** (ESP-NOW), **T07** (Web ESP32) | 35% | 🟡 Đang chuẩn bị linh kiện & code mẫu |
| 2 | **Thành viên B** | Gateway & Giao diện | **T08** (IoT Gateway), **T10** (Flask Local UI), HTML Web ESP32 | 35% | 🟢 Đã hoàn thành bộ Mock 2 chiều |
| 3 | **Thành viên C** | Cloud & Báo cáo | **T11** (Dashboard), **T12** (RuleChain), **T13** (Notification) | 30% | 🟡 Đang kết nối CoreIOT từ dữ liệu Mock |

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

## 4. Cấu trúc thư mục & Trạng thái tệp tin

```text
smart-room-iot/
├── firmware/
│   ├── node_a_sensor/           # [🟡 Đang phát triển] Firmware đọc Modbus RS485 & gửi ESP-NOW
│   └── node_b_control/          # [🟡 Đang phát triển] Firmware nhận ESP-NOW, host SoftAP Web & Serial
├── gateway/
│   ├── simulator/
│   │   └── mock_node_b.py       # [🟢 ĐÃ HOÀN THÀNH] Trình giả lập Node B (Telemetry + ACK 2 chiều)
│   ├── requirements.txt         # [🟢 ĐÃ HOÀN THÀNH] Khai báo thư viện Python
│   ├── .env.example             # [🟢 ĐÃ HOÀN THÀNH] Mẫu cấu hình cổng COM, MQTT Broker, Token (Bảo mật)
│   ├── main.py                  # [⚪ Dự kiến Tuần 11] Chương trình chính IoT Gateway Python
│   └── app_flask.py             # [⚪ Dự kiến Tuần 12] Web Dashboard cục bộ trên máy tính (T10)
├── coreiot/                     # [⚪ Dự kiến Tuần 11-13] File export Dashboard & RuleChain JSON
├── docs/                        # [⚪ Dự kiến Tuần 14-15] Sơ đồ đấu dây, datasheet cảm biến, tài liệu thiết kế
├── tests/                       # [⚪ Dự kiến Tuần 14] Bảng số liệu thực nghiệm đo đạc (100 gói ESP-NOW, RPC latency)
├── Ke_Hoach_Phan_Cong_BTL_IoT.docx  # [🟢 ĐÃ HOÀN THÀNH] Tài liệu phân công chi tiết 8.0/8.0 điểm
└── README.md                    # [🟢 ĐÃ HOÀN THÀNH] Tài liệu hướng dẫn chung của dự án
```

---

## 5. Chuẩn giao tiếp dữ liệu & Quy ước ACK

* **Tốc độ Serial:** `115200 baud` (mỗi gói kết thúc bằng `\n`)
* **Kênh Wi-Fi:** Cố định cứng `Channel 1` cho cả Node A, Node B và SoftAP
* **Tên trường trạng thái LED (đồng bộ 100%):** `cooling_state` (`true` hoặc `false`)

### 5.1. Dữ liệu cảm biến đẩy lên (Telemetry)
* **Từ Node B sang Gateway (Serial):**
  ```json
  {"type":"telemetry", "seq":12, "temperature":28.5, "humidity":65.2, "cooling_state":false}
  ```
* **Từ Gateway lên CoreIOT (MQTT topic `v1/devices/me/telemetry`):**
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
* **Quy định Timeout & Xử lý lỗi:**
  * Gateway gửi lệnh xuống Node B và chờ tối đa **2000 ms (2 giây)**.
  * Nếu quá 2 giây không nhận được gói ACK có đúng `request_id`, Gateway báo lỗi Timeout về CoreIOT:
    `{"ok": false, "error": "Node B timeout"}` để tránh treo giao diện.

---

## 6. Hướng dẫn thử nghiệm ngay với Bộ giả lập Mock Simulator

Trong Tuần 10, Bạn B và Bạn C có thể bắt đầu lập trình và kiểm thử ngay mà **không cần chờ phần cứng của Bạn A**:

```bash
# 1. Di chuyển vào thư mục simulator
cd gateway/simulator

# 2. Khởi chạy bộ giả lập Node B (2 chiều)
python mock_node_b.py
```

* **Quan sát:** Simulator sẽ tự động in ra chuỗi JSON telemetry mỗi 5 giây.
* **Thử nghiệm gửi lệnh:** Copy và dán dòng JSON sau vào terminal rồi bấm Enter:
  ```json
  {"type":"command", "cmd":"set_cooling", "state":true, "request_id":1}
  ```
* **Kết quả:** Simulator sẽ phản hồi ngay lập tức gói ACK xác nhận và đổi trạng thái `cooling_state` sang `true`.

---

## 7. Quy định làm việc nhóm trên Git & GitHub

1. **Tuyệt đối không push trực tiếp lên nhánh `main`:** Nhánh `main` chỉ dùng để lưu trữ các phiên bản ổn định đã qua kiểm thử.
2. **Quy tắc tạo nhánh (Branching):**
   * Bạn A làm việc trên nhánh: `feature/firmware-modbus-espnow`
   * Bạn B làm việc trên nhánh: `feature/gateway-backend`
   * Bạn C làm việc trên nhánh: `feature/coreiot-rulechain`
3. **Quy trình Merge:** Mỗi khi hoàn thành một chức năng, push code lên nhánh của mình trên GitHub $\rightarrow$ Tạo **Pull Request (PR)** vào `main` $\rightarrow$ Nhờ ít nhất 1 thành viên khác review trước khi Merge.
4. **Bảo mật:** Không bao giờ commit file `.env` chứa token thật lên GitHub (đã được cấu hình trong `.gitignore`).
