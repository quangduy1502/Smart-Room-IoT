# Hệ Thống Giám Sát Nhiệt Độ, Độ Ẩm Phòng Học & Điều Khiển LED

* **Môn học:** Internet of Things (IoT) – Học kỳ 261  
* **Đơn vị:** Khoa Khoa học và Kỹ thuật Máy tính – Trường Đại học Bách Khoa, ĐHQG TP.HCM  
* **Giảng viên hướng dẫn:** TS. Lê Trọng Nhân  
* **Lớp / Nhóm:** L02 / Nhóm 04  

---

## 1. Giới thiệu đề tài

Hệ thống thu thập dữ liệu nhiệt độ và độ ẩm phòng học theo thời gian thực sử dụng cảm biến công nghiệp Modbus RTU/RS485 và tự động điều khiển thiết bị làm mát (mô phỏng bằng LED trên board hoặc LED rời).

Hệ thống vận hành theo kiến trúc IoT đa tầng:
* **Tầng thu thập dữ liệu (Node A - Sensor):** Đọc thông số nhiệt ẩm từ cảm biến Modbus RTU qua giao tiếp RS485 (UART), sau đó đóng gói và truyền không dây qua giao thức ESP-NOW sang Node B.
* **Tầng điều khiển cục bộ (Node B - Control):** Tiếp nhận gói tin ESP-NOW, host một Webserver nhúng (qua Wi-Fi Access Point độc lập) phục vụ điều khiển tại chỗ, đồng thời xuất luồng dữ liệu qua cổng USB Serial lên máy tính Gateway.
* **Tầng IoT Gateway & Cloud:** Gateway trên máy tính tiếp nhận dữ liệu từ Serial, tổng hợp và đẩy lên nền tảng đám mây CoreIOT qua MQTT; đồng thời tiếp nhận các lệnh điều khiển 2 chiều (RPC) để phân phối xuống Node B.

**Hệ thống hỗ trợ giám sát và điều khiển trên 3 giao diện độc lập:**
1. **Webserver nhúng trên ESP32 (T07):** Điện thoại kết nối trực tiếp vào Wi-Fi SoftAP của Node B để điều khiển cục bộ.
2. **Dashboard trên Laptop Gateway (T10):** Giao diện Flask trên máy tính (`http://localhost:5000`) điều khiển qua cổng USB Serial độc lập khi mất Internet.
3. **Dashboard Đám mây CoreIOT (T11):** Giám sát biểu đồ lịch sử và điều khiển từ xa qua mạng Internet.

---

## 2. Bảng phân công trách nhiệm thành viên

Công việc được phân chia cụ thể theo đúng kế hoạch kỹ thuật đã thống nhất:

| STT | Họ và tên | MSSV | Vai trò phụ trách | Nội dung công việc chi tiết | Tỷ lệ đóng góp |
| :---: | :--- | :---: | :--- | :--- | :---: |
| 1 | **Pan Yi Ting** | **2414089** | **Phần A: Firmware & Phần cứng** | • Kiểm tra 2 mạch YoloUNO ESP32-S3, đấu nối phần cứng và tra cứu datasheet cảm biến Modbus RS485.<br>• Viết firmware Node A đọc 2 thanh ghi nhiệt độ, độ ẩm qua UART/RS485 (**T02**).<br>• Cấu hình truyền không dây ESP-NOW từ Node A sang Node B có trường `seq` (**T06**).<br>• Lập trình Node B: nhận ESP-NOW, xuất JSON Serial, host Wi-Fi SoftAP và Webserver nhúng xem số đo, điều khiển LED (**T07**).<br>• Gửi gói tin cập nhật trạng thái `cooling_state` lên Gateway khi có thay đổi từ bất kỳ đâu.<br>• Phối hợp cùng Bùi Quang Duy đo đạc 100 gói ESP-NOW tại 1m và 5m. | **35%** |
| 2 | **Dương Gia Huy** | **2211155** | **Phần B: Gateway & Giao diện** | • Xây dựng bộ giả lập `mock_node_b.py` 2 chiều phục vụ kiểm thử tích hợp sớm.<br>• Viết phần mềm IoT Gateway Python: cầu nối 2 chiều USB Serial $\leftrightarrow$ MQTT (**T08**).<br>• Quản lý trạng thái cục bộ (State Manager), phân biệt rõ dữ liệu từ Node A và Node B, lưu log riêng biệt.<br>• Tiếp nhận lệnh RPC `setCooling` từ CoreIOT, gửi command JSON xuống Node B, chờ ACK và publish về topic RPC response.<br>• Xây dựng giao diện Local Dashboard bằng Flask trên máy tính (`http://localhost:5000`) (**T10**).<br>• Thiết kế giao diện HTML/JS gọn nhẹ cho trang web nhúng của Node B bàn giao cho Pan Yi Ting. | **35%** |
| 3 | **Bùi Quang Duy** | **2410482** | **Phần C: Cloud Platform & Báo cáo** | • Khởi tạo thiết bị trên CoreIOT, quản lý Access Token cung cấp an toàn cho Dương Gia Huy.<br>• Thiết kế Dashboard CoreIOT (**T11**): Thẻ nhiệt độ, độ ẩm, biểu đồ chuỗi thời gian và công tắc Switch gửi RPC `setCooling`.<br>• Xây dựng RuleChain thông minh (**T12**): Nhớ trạng thái qua Alarm, tự động phát lệnh bật LED khi nhiệt độ > 32°C (chống lặp lệnh) và tắt LED khi $\le$ 30°C; ưu tiên lệnh điều khiển thủ công.<br>• Cấu hình cảnh báo Notification trực tiếp trên nền tảng CoreIOT khi vượt ngưỡng (**T13**).<br>• Viết script đo đạc độ trễ RPC và tỷ lệ mất gói ESP-NOW phục vụ số liệu Chương 4.<br>• Tổng hợp mã nguồn GitHub, quản lý tài liệu và biên tập video demo 5–7 phút. | **30%** |

---

## 3. Kiến trúc hệ thống & Luồng truyền thông hai chiều

Hệ thống phân định rõ ràng hai luồng truyền thông độc lập:

### Sơ đồ 1: Luồng thu thập dữ liệu cảm biến (Telemetry đi lên)
```text
[Cảm biến Modbus RS485]
          │ (UART RS485 - Mỗi 5 giây)
          ▼
   [Node A: Sensor]
          │ (ESP-NOW không dây - Channel 1)
          ▼
   [Node B: Control] ──────────► [Web nhúng SoftAP (T07) - Điện thoại xem trực tiếp]
          │ (USB Serial 115200 - JSON)
          ▼
   [Laptop Gateway]  ──────────► [Local Dashboard Flask (T10) - Máy tính xem local]
          │ (MQTT Publish - v1/devices/me/telemetry)
          ▼
   [CoreIOT Cloud]   ──────────► [Cloud Dashboard (T11) - Giám sát từ xa]
```

### Sơ đồ 2: Luồng điều khiển chấp hành hai chiều (RPC / Command đi xuống)
```text
┌────────────────────────────────────────────────────────────────────────┐
│                   3 NƠI PHÁT LỆNH ĐIỀU KHIỂN:                           │
│  1. Cloud Dashboard / RuleChain tự động  (MQTT RPC: setCooling)       │
│  2. Local Dashboard trên máy tính         (Gửi lệnh qua Gateway)        │
│  3. Web nhúng SoftAP trên điện thoại      (HTTP POST: /api/control)    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
                          [Laptop Gateway Python]
                                    │ (Gửi USB Serial: {"type":"command", "cmd":"set_cooling", ...})
                                    ▼
                           [Node B: ESP32-S3]
                                    │
                   ┌────────────────┴────────────────┐
                   ▼                                 ▼
         [Bật / Tắt LED thật]             [Trả gói tin ACK Serial]
                                                     │
                                                     ▼
                                          [Laptop Gateway Python]
                                                     │ (MQTT Publish: v1/devices/me/rpc/response/{id})
                                                     ▼
                                              [CoreIOT Cloud]
```

---

## 4. Cấu trúc thư mục kho mã nguồn

Toàn bộ mã nguồn dự án được tổ chức phân tầng rõ ràng theo từng thành phần hệ thống:

```text
smart-room-iot/
├── firmware/
│   ├── node_a_sensor/           # Mã nguồn Node cảm biến: Giao tiếp Modbus RS485 & phát ESP-NOW
│   └── node_b_control/          # Mã nguồn Node điều khiển: Nhận ESP-NOW, host Web SoftAP & USB Serial
├── gateway/
│   ├── simulator/               # Thư mục bộ giả lập (mock_node_b.py phục vụ kiểm thử tích hợp sớm)
│   ├── main.py                  # [Dự kiến] Ứng dụng chính IoT Gateway (Cầu nối Serial <-> MQTT)
│   └── app_flask.py             # [Dự kiến] Giao diện Local Dashboard vận hành trên máy tính
├── coreiot/                     # Tệp tin cấu hình Dashboard và kịch bản tự động hóa RuleChain (JSON)
├── docs/                        # Sơ đồ kết nối phần cứng, tài liệu kỹ thuật cảm biến và thiết kế
├── tests/                       # Dữ liệu đo đạc thực nghiệm (tỷ lệ mất gói ESP-NOW, độ trễ RPC)
├── .gitignore                   # Cấu hình loại trừ các tệp tạm, môi trường ảo và tệp cấu hình
└── README.md                    # Tài liệu tổng quan và đặc tả hệ thống
```

---

## 5. Chuẩn giao thức dữ liệu & Quy ước phản hồi ACK (Thiết kế chuẩn)

* **Tốc độ truyền thông Serial:** `115200 baud` (kết thúc mỗi thông điệp bằng ký tự `\n`).
* **Kênh Wi-Fi dự kiến:** Cố định `Channel 1` cho cả kết nối ESP-NOW và Access Point.
* **Định danh trạng thái thiết bị:** Thống nhất duy nhất khóa `cooling_state` (`true` hoặc `false`) trên toàn hệ thống.

### 5.1. Dữ liệu cảm biến đẩy lên (Telemetry)
* **Từ Node B gửi sang Gateway qua Serial:**
  ```json
  {"type":"telemetry", "seq":12, "temperature":28.5, "humidity":65.2, "cooling_state":false}
  ```
* **Từ Gateway gửi lên Cloud CoreIOT qua MQTT topic `v1/devices/me/telemetry`:**
  ```json
  {"temperature":28.5, "humidity":65.2, "cooling_state":false}
  ```

### 5.2. Lệnh điều khiển & Xác nhận phản hồi (2-Way RPC)
* **Lệnh điều khiển từ Gateway gửi xuống Node B:**
  * `request_id`: Mã định danh số nguyên dương tăng dần do Gateway sinh ra cho mỗi lệnh để đối chiếu phản hồi.
  ```json
  {"type":"command", "cmd":"set_cooling", "state":true, "request_id":42}
  ```
* **Node B phản hồi xác nhận lệnh (ACK):**
  * *Trường hợp thành công:*
    ```json
    {"type":"ack", "request_id":42, "ok":true, "cooling_state":true}
    ```
  * *Trường hợp thất bại (lệnh sai hoặc lỗi tham số):*
    ```json
    {"type":"ack", "request_id":42, "ok":false, "error":"invalid_command"}
    ```
* **Xử lý Timeout dự kiến:**
  * Gateway chờ ACK tối đa **2000 ms (2 giây)**. Nếu quá thời gian này không nhận được phản hồi hợp lệ, Gateway ghi nhận sự cố timeout và phản hồi về Cloud (`{"ok": false, "error": "timeout"}`) nhằm tránh treo widget giao diện.

### 5.3. Cơ chế đồng bộ trạng thái giữa các giao diện
* **Single Source of Truth:** Node B là nơi quản lý trạng thái vật lý thực tế duy nhất của thiết bị làm mát (`cooling_state`).
* Bất cứ khi nào thiết bị đổi trạng thái (do thao tác từ Web nhúng, giao diện Local hoặc từ CoreIOT Cloud), Node B sẽ gửi ngay một gói tin sự kiện qua Serial lên Gateway:
  ```json
  {"type":"event", "event":"state_changed", "cooling_state":true}
  ```
* Gateway tiếp nhận sự kiện, cập nhật bộ nhớ trạng thái cục bộ và publish telemetry lên CoreIOT. Giao diện Web nhúng và Flask Dashboard sẽ áp dụng cơ chế tự động làm mới để đồng bộ hiển thị theo thời gian thực.
* **Cơ chế tự động hóa:** RuleChain cấu hình tự động bật thiết bị khi nhiệt độ > 32°C và tắt khi $\le$ 30°C. Khi có thao tác điều khiển thủ công từ người dùng, lệnh thủ công sẽ được ưu tiên thực thi ngay lập tức.

---

## 6. Quy trình phát triển & Quản lý mã nguồn (Git Workflow)

1. **Ý thức tuân thủ nhánh phát triển:**
   * Nhánh chính `main` là nhánh lưu trữ các phiên bản ổn định đã qua tích hợp kiểm thử.
   * Các thành viên tự giác thống nhất không push trực tiếp lên `main`, mà làm việc độc lập trên nhánh chức năng của mình:
     * Nhánh phát triển phần cứng & firmware (Pan Yi Ting): `feature/firmware`
     * Nhánh phát triển Gateway & giao diện (Dương Gia Huy): `feature/gateway`
     * Nhánh phát triển Cloud & tích hợp (Bùi Quang Duy): `feature/cloud-integration`
2. **Quy trình tích hợp:**
   * Mỗi khi hoàn thành một mô-đun, thành viên tạo **Pull Request (PR)** từ nhánh feature vào nhánh `main`.
   * Các thành viên còn lại review mã nguồn trước khi merge nhằm đảm bảo tính toàn vẹn của hệ thống.
3. **An toàn bảo mật (LƯU Ý QUAN TRỌNG):**
   * File `.gitignore` chỉ có tác dụng bỏ qua các tệp cấu hình được khai báo (như `.env`, `tokens.txt`). 
   * **Thành viên tuyệt đối KHÔNG viết cứng (hardcode) mật khẩu Wi-Fi, Token CoreIOT vào trong mã nguồn C++/Python.** Mọi thông tin nhạy cảm phải được đưa vào file cấu hình môi trường hoặc cấu hình riêng ngoài repo.
