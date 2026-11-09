# Hệ Thống Giám Sát Nhiệt Độ, Độ Ẩm Phòng Học & Điều Khiển LED

> ⚠️ **TRẠNG THÁI DỰ ÁN (TUẦN 11):**  
> Dự án đang trong **Tuần 11 (Giai đoạn hiện thực & kiểm chứng phần cứng cốt lõi)**: Đọc cảm biến Modbus RS485 thật trên Node A, truyền nhận không dây ESP-NOW sang Node B, và xây dựng cầu nối Serial $\leftrightarrow$ MQTT lên máy chủ CoreIOT. Các thông số và kiến trúc dưới đây là thiết kế chuẩn đang được triển khai.

* **Môn học:** Internet of Things (IoT) – Học kỳ 261  
* **Trường:** Đại học Bách Khoa - ĐHQG TP. Hồ Chí Minh  
* **Giảng viên hướng dẫn:** TS. Lê Trọng Nhân  
* **Mục tiêu:** 8.0/8.0 Điểm công nghệ cốt lõi (T02, T06, T07, T08, T10, T11, T12, T13)

---

## 1. Giới thiệu đề tài (Thiết kế dự kiến)

Đề tài hướng tới việc xây dựng hệ thống thu thập dữ liệu nhiệt độ và độ ẩm phòng học qua cảm biến công nghiệp Modbus RTU/RS485. 
* Dữ liệu từ Node cảm biến (**Node A**) được truyền không dây sang Node điều khiển (**Node B**) bằng giao thức ESP-NOW.
* Node B chuyển tiếp dữ liệu qua cổng USB Serial lên **Laptop Gateway** (chạy Python).
* Gateway tổng hợp dữ liệu, đẩy lên nền tảng đám mây **CoreIOT** qua MQTT và tiếp nhận lệnh điều khiển 2 chiều (RPC) để bật/tắt thiết bị làm mát (mô phỏng bằng LED).

**Hệ thống dự kiến hỗ trợ giám sát và điều khiển trên 3 giao diện:**
1. **Webserver nhúng trên ESP32 (T07):** Điện thoại kết nối trực tiếp vào Wi-Fi SoftAP của Node B để điều khiển cục bộ.
2. **Dashboard trên Laptop Gateway (T10):** Giao diện Flask trên máy tính (`http://localhost:5000`) điều khiển qua cổng USB Serial độc lập khi mất Internet.
3. **Dashboard Đám mây CoreIOT (T11):** Giám sát biểu đồ lịch sử và điều khiển từ xa.

---

## 2. Bảng phân công vai trò thành viên

| Vai trò | Họ và tên | MSSV | GitHub Username | Tiêu chí công nghệ phụ trách | Trọng số |
| :---: | :--- | :---: | :---: | :--- | :---: |
| **Thành viên A** | *[Điền tên]* | *[Điền MSSV]* | *@[github]* | **T02** (Modbus RS485), **T06** (ESP-NOW), **T07** (Web ESP32) | 35% |
| **Thành viên B** | *[Điền tên]* | *[Điền MSSV]* | *@[github]* | **T08** (IoT Gateway), **T10** (Flask Local UI), HTML Web ESP32 | 35% |
| **Thành viên C** | *[Điền tên]* | *[Điền MSSV]* | *@[github]* | **T11** (Dashboard), **T12** (RuleChain), **T13** (Notification) | 30% |

*(Các thành viên trong nhóm thống nhất vai trò theo bảng trên để tự chủ động phát triển phần việc của mình).*

---

## 3. Kiến trúc hệ thống & Luồng dữ liệu

```text
[Cảm biến Modbus RS485]
          │ (UART RS485)
          ▼
   [YoloUNO Node A]  ──(ESP-NOW - Thiết kế Channel 1)──►  [YoloUNO Node B]
                                                                  │ (USB Serial 115200)
                                                                  ▼
                                                          [Laptop Gateway]
                                                                  │ (MQTT Internet)
                                                                  ▼
                                                          [Server CoreIOT]
```

---

## 4. Cấu trúc thư mục kho mã nguồn

Repo hiện tại chứa cấu trúc thư mục rỗng chuẩn mực (được giữ bằng `.gitkeep`), từng thành viên sẽ tự tạo file và code vào thư mục của mình:

```text
smart-room-iot/
├── firmware/
│   ├── node_a_sensor/           # [Thành viên A] Mã nguồn đọc Modbus RS485 & ESP-NOW phát
│   └── node_b_control/          # [Thành viên A & B] Mã nguồn nhận ESP-NOW, host SoftAP Web & Serial
├── gateway/
│   ├── simulator/               # [Thành viên B] Trình giả lập Node B (mock_node_b.py) phục vụ test sớm
│   ├── main.py                  # [Thành viên B - Dự kiến] Chương trình chính IoT Gateway Python
│   └── app_flask.py             # [Thành viên B - Dự kiến] Web Dashboard cục bộ trên máy tính (T10)
├── coreiot/                     # [Thành viên C] File export Dashboard & RuleChain JSON
├── docs/                        # [Cả nhóm] Sơ đồ đấu dây, datasheet cảm biến, tài liệu thiết kế
├── tests/                       # [Thành viên C] Bảng số liệu thực nghiệm (100 gói ESP-NOW, độ trễ RPC)
├── .gitignore                   # Chặn các file rác .pio, .vscode, .env
└── README.md                    # Tài liệu đặc tả chung của dự án
```

---

## 5. Chuẩn giao tiếp dữ liệu & Quy ước ACK (Thiết kế ban đầu)

> 💡 **Lưu ý:** Các thông số như *Wi-Fi Channel 1, Timeout 2 giây, và cơ chế SoftAP kết hợp ESP-NOW* là lựa chọn thiết kế ban đầu của nhóm. Trong quá trình thực hiện ở Tuần 11-13, các thông số này có thể được điều chỉnh nếu kết quả đo đạc thực tế yêu cầu.

* **Tốc độ Serial:** `115200 baud` (mỗi gói kết thúc bằng `\n`)
* **Kênh Wi-Fi dự kiến:** Cố định `Channel 1`
* **Tên trường trạng thái LED (thống nhất 100%):** `cooling_state` (`true` hoặc `false`)

### 5.1. Dữ liệu cảm biến đẩy lên (Telemetry)
* **Từ Node B sang Gateway (Serial JSON):**
  ```json
  {"type":"telemetry", "seq":12, "temperature":28.5, "humidity":65.2, "cooling_state":false}
  ```
* **Từ Gateway lên CoreIOT (MQTT topic `v1/devices/me/telemetry`):**
  ```json
  {"temperature":28.5, "humidity":65.2, "cooling_state":false}
  ```

### 5.2. Lệnh điều khiển & Quy ước ACK (2-Way RPC)
* **Lệnh từ Gateway gửi xuống Node B:**
  * `request_id`: Số nguyên dương tự tăng do Gateway sinh ra cho mỗi lệnh gửi.
  ```json
  {"type":"command", "cmd":"set_cooling", "state":true, "request_id":42}
  ```
* **Node B phản hồi xác nhận lệnh (ACK):**
  * **Trường hợp thành công:**
    ```json
    {"type":"ack", "request_id":42, "ok":true, "cooling_state":true}
    ```
  * **Trường hợp lỗi (sai lệnh / tham số không hợp lệ):**
    ```json
    {"type":"ack", "request_id":42, "ok":false, "error":"invalid_command"}
    ```
* **Xử lý Timeout:**
  * Gateway chờ ACK tối đa **2000 ms (2 giây)**. Nếu quá thời gian này không nhận được phản hồi, Gateway đánh dấu lệnh thất bại và gửi thông báo lỗi lên CoreIOT (`{"ok": false, "error": "timeout"}`) để tránh treo giao diện.
  * *Thành viên A và B sẽ thống nhất thêm chi tiết xử lý thử lại (retry) khi tích hợp thực tế.*

### 5.3. Nguyên lý đồng bộ trạng thái giữa 3 giao diện
* **Single Source of Truth:** Node B là nơi nắm giữ trạng thái vật lý thực tế duy nhất của thiết bị làm mát (`cooling_state`).
* Bất cứ khi nào thiết bị đổi trạng thái (do bấm nút trên Web ESP32, bấm trên Laptop Local hay do RPC từ CoreIOT), Node B sẽ gửi ngay một gói tin qua Serial lên Gateway:
  ```json
  {"type":"event", "event":"state_changed", "cooling_state":true}
  ```
* Gateway nhận được sẽ cập nhật bộ nhớ trạng thái cục bộ và lập tức publish telemetry lên CoreIOT để giao diện đám mây và giao diện máy tính cùng đồng bộ trạng thái mới.

---

## 6. Quy định làm việc nhóm trên Git & GitHub

1. **Quy tắc tạo nhánh (Branching):**
   * Bạn A làm việc trên nhánh: `feature/firmware`
   * Bạn B làm việc trên nhánh: `feature/gateway`
   * Bạn C làm việc trên nhánh: `feature/coreiot`
2. **Quy tắc Merge:** Mỗi khi hoàn thành một chức năng, tạo **Pull Request (PR)** từ nhánh feature vào nhánh `main` và nhờ thành viên khác review trước khi merge.
3. **Ý thức tuân thủ:** Nhóm thống nhất **tự giác tuân thủ không push đè trực tiếp lên `main`** trong giai đoạn đầu; nhóm có thể thiết lập *Branch Protection Rules* trên GitHub Settings sau nếu cần thiết.
4. **Bảo mật:** Không đưa file `.env` chứa token thật lên GitHub (đã được cấu hình trong `.gitignore`).
