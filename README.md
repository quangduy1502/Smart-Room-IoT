# Hệ Thống Giám Sát Vi Khí Hậu Phòng Học & Điều Khiển Thiết Bị Thông Minh

> ⚠️ **TRẠNG THÁI DỰ ÁN (TUẦN 11):**  
> Dự án đang trong **giai đoạn chuẩn bị, khởi tạo khung dự án và chuẩn bị xây dựng các thành phần**. Kho mã nguồn hiện tại là bộ khung (skeleton) ban đầu. Toàn bộ kiến trúc, chức năng và thông số kỹ thuật mô tả dưới đây là **thiết kế dự kiến**, sẽ được kiểm chứng và hoàn thiện dần trên phần cứng thực tế qua từng tuần.

* **Môn học:** Internet of Things (IoT) – Học kỳ 261  
* **Đơn vị:** Khoa Khoa học và Kỹ thuật Máy tính – Trường Đại học Bách Khoa, ĐHQG TP.HCM  
* **Giảng viên hướng dẫn:** TS. Lê Trọng Nhân  
* **Mục tiêu dự án:** Hướng tới hoàn thành đầy đủ 8/8 tiêu chí công nghệ cốt lõi của môn học (T02, T06, T07, T08, T10, T11, T12, T13).

---

## 1. Giới thiệu đề tài (Thiết kế dự kiến)

Đề tài hướng tới việc xây dựng hệ thống thu thập dữ liệu vi khí hậu phòng học (nhiệt độ, độ ẩm) theo thời gian thực và hỗ trợ điều khiển thiết bị làm mát/thông gió (mô phỏng bằng LED công suất/tải chấp hành).

Hệ thống được thiết kế vận hành theo kiến trúc IoT đa tầng:
* **Tầng thu thập dữ liệu (Sensor Node):** Node cảm biến đọc thông số từ cảm biến công nghiệp Modbus RTU qua giao tiếp RS485, sau đó truyền dữ liệu không dây qua giao thức ESP-NOW sang Node điều khiển.
* **Tầng điều khiển cục bộ (Control Node):** Node điều khiển tiếp nhận gói tin ESP-NOW, host một Webserver nhúng (qua Wi-Fi Access Point độc lập) phục vụ điều khiển tại chỗ, đồng thời xuất luồng dữ liệu qua cổng USB Serial lên máy tính Gateway.
* **Tầng IoT Gateway & Cloud:** Gateway trên máy tính tổng hợp dữ liệu, đẩy lên nền tảng đám mây CoreIOT qua MQTT và tiếp nhận các lệnh điều khiển 2 chiều (RPC).

**Ba giao diện giám sát & điều khiển dự kiến:**
1. **Giao diện Web nhúng trên vi điều khiển (T07):** Truy cập trực tiếp qua mạng Wi-Fi SoftAP do Control Node phát ra.
2. **Giao diện Local Dashboard trên máy tính Gateway (T10):** Ứng dụng Web Flask (`http://localhost:5000`) vận hành độc lập qua cáp USB khi mất kết nối Internet.
3. **Giao diện Đám mây CoreIOT Cloud (T11):** Giám sát từ xa, trực quan hóa biểu đồ lịch sử và tự động hóa cảnh báo.

---

## 2. Phân công trách nhiệm dự án

Dự án phân chia công việc đồng đều giữa 3 thành viên theo các mảng chuyên môn kỹ thuật, đảm bảo khối lượng công việc và mức độ đóng góp ngang nhau:

| STT | Họ và tên | MSSV | Vai trò kỹ thuật | Nhiệm vụ phụ trách chính | Đóng góp dự kiến |
| :---: | :--- | :---: | :--- | :--- | :---: |
| 1 | *[Họ và tên]* | *[MSSV]* | **Embedded & Firmware Engineer** | • Phát triển firmware đọc cảm biến công nghiệp Modbus RTU/RS485.<br>• Hiện thực giao thức truyền nhận không dây ESP-NOW.<br>• Xây dựng Webserver nhúng trên vi điều khiển điều khiển thiết bị tại chỗ. | ~33.3% |
| 2 | *[Họ và tên]* | *[MSSV]* | **IoT Gateway & Backend Engineer** | • Phát triển phần mềm IoT Gateway kết nối 2 chiều USB Serial $\leftrightarrow$ MQTT.<br>• Xây dựng bộ giả lập (Simulator) phục vụ kiểm thử tích hợp sớm.<br>• Thiết kế giao diện Local Dashboard trên máy tính và giao diện Web nhúng. | ~33.3% |
| 3 | *[Họ và tên]* | *[MSSV]* | **Cloud Platform & System Integration** | • Thiết lập thiết bị, Template và Dashboard giám sát trên CoreIOT.<br>• Xây dựng kịch bản tự động hóa RuleChain và cấu hình cảnh báo Notification.<br>• Phụ trách kịch bản kiểm thử đo đạc thực nghiệm (độ trễ, mất gói) và báo cáo. | ~33.3% |

---

## 3. Kiến trúc luồng truyền thông hai chiều

Sơ đồ mô tả luồng thu thập dữ liệu (Telemetry đi lên) và luồng điều khiển chấp hành (RPC đi xuống):

```text
       CHIỀU THU THẬP DỮ LIỆU (TELEMETRY) ────────►
[Cảm biến Modbus] ──(RS485)──► [Sensor Node] ──(ESP-NOW)──► [Control Node] ──(USB Serial)──► [Gateway PC] ──(MQTT)──► [CoreIOT Cloud]
                                                                   ▲                                │
                                                                   └──────── (Lệnh điều khiển) ─────┘
       ◄──────── CHIỀU ĐIỀU KHIỂN CHẤP HÀNH (RPC / COMMAND) ────────
```

---

## 4. Cấu trúc thư mục kho mã nguồn

Repo hiện tại chứa cấu trúc thư mục rỗng ban đầu (được theo dõi bằng `.gitkeep`), từng thành viên sẽ tự tạo file và phát triển mã nguồn trong thư mục được phân công:

```text
smart-room-iot/
├── firmware/
│   ├── node_a_sensor/           # Mã nguồn Node cảm biến: Giao tiếp Modbus RS485 & phát ESP-NOW
│   └── node_b_control/          # Mã nguồn Node điều khiển: Nhận ESP-NOW, host Web SoftAP & USB Serial
├── gateway/
│   ├── simulator/               # Thư mục bộ giả lập (Thành viên B tự code simulator phục vụ test sớm)
│   ├── main.py                  # [Dự kiến] Ứng dụng chính IoT Gateway (Cầu nối Serial <-> MQTT)
│   └── app_flask.py             # [Dự kiến] Giao diện Local Dashboard vận hành trên máy tính
├── coreiot/                     # Tệp tin cấu hình Dashboard và kịch bản tự động hóa RuleChain (JSON)
├── docs/                        # Sơ đồ kết nối phần cứng, tài liệu kỹ thuật cảm biến và thiết kế
├── tests/                       # Dữ liệu đo đạc thực nghiệm (tỷ lệ mất gói ESP-NOW, độ trễ RPC)
├── .gitignore                   # Cấu hình loại trừ các tệp tạm, môi trường ảo và tệp cấu hình
└── README.md                    # Tài liệu tổng quan và đặc tả hệ thống
```

> 💡 **Tài liệu tham khảo bộ giả lập (Simulator):** Thành viên phụ trách Gateway có thể tham khảo thuật toán đa luồng và cấu trúc JSON của bộ giả lập mẫu tại [lịch sử commit trước](https://github.com/quangduy1502/Smart-Room-IoT/commit/0502aa1768a6fcc5981daa9cf83183e996b13aef) để tự xây dựng bộ simulator hoàn chỉnh.

---

## 5. Chuẩn giao thức dữ liệu & Cơ chế phản hồi ACK (Thiết kế dự kiến)

> 💡 **Lưu ý:** Các thông số như *Wi-Fi Channel 1, Timeout 2 giây, ngưỡng nhiệt độ và cơ chế SoftAP kết hợp ESP-NOW* là lựa chọn thiết kế ban đầu của nhóm, sẽ được kiểm chứng và điều chỉnh theo kết quả đo đạc thực tế trên phần cứng.

* **Tốc độ truyền thông Serial:** `115200 baud` (kết thúc mỗi thông điệp bằng ký tự `\n`).
* **Kênh Wi-Fi dự kiến:** Cố định `Channel 1` cho cả kết nối ESP-NOW và Access Point.
* **Định danh trạng thái thiết bị:** Thống nhất duy nhất khóa `cooling_state` (`true` hoặc `false`) trên toàn hệ thống.

### 5.1. Dữ liệu cảm biến đẩy lên (Telemetry)
* **Từ Control Node gửi sang Gateway qua Serial:**
  ```json
  {"type":"telemetry", "seq":12, "temperature":28.5, "humidity":65.2, "cooling_state":false}
  ```
* **Từ Gateway gửi lên Cloud CoreIOT qua MQTT topic `v1/devices/me/telemetry`:**
  ```json
  {"temperature":28.5, "humidity":65.2, "cooling_state":false}
  ```

### 5.2. Lệnh điều khiển & Xác nhận phản hồi (2-Way RPC)
* **Lệnh điều khiển từ Gateway gửi xuống Control Node:**
  * `request_id`: Mã định danh số nguyên dương tăng dần do Gateway sinh ra cho mỗi lệnh để đối chiếu phản hồi.
  ```json
  {"type":"command", "cmd":"set_cooling", "state":true, "request_id":42}
  ```
* **Control Node phản hồi xác nhận lệnh (ACK):**
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

### 5.3. Cơ chế đồng bộ trạng thái giữa các giao diện (Thiết kế dự kiến)
* **Single Source of Truth:** Control Node là nơi quản lý trạng thái vật lý thực tế duy nhất của thiết bị làm mát (`cooling_state`).
* Bất cứ khi nào thiết bị đổi trạng thái (do thao tác từ Web nhúng, giao diện Local hoặc từ CoreIOT Cloud), Control Node sẽ gửi ngay một gói tin sự kiện qua Serial lên Gateway:
  ```json
  {"type":"event", "event":"state_changed", "cooling_state":true}
  ```
* Gateway tiếp nhận sự kiện, cập nhật bộ nhớ trạng thái cục bộ và publish telemetry lên CoreIOT. Giao diện Web nhúng và Flask Dashboard sẽ áp dụng cơ chế tự động làm mới (polling/fetch) để đồng bộ hiển thị theo thời gian thực.
* **Cơ chế tự động hóa dự kiến:** RuleChain cấu hình ngưỡng nhiệt độ (ví dụ vượt 32°C kích hoạt cảnh báo/bật thiết bị, dưới 30°C ngắt thiết bị). Khi có thao tác điều khiển thủ công từ người dùng, lệnh thủ công sẽ được ưu tiên thực thi.

---

## 6. Quy trình phát triển & Quản lý mã nguồn (Git Workflow)

1. **Ý thức tuân thủ nhánh phát triển:**
   * Nhánh chính `main` là nhánh lưu trữ các phiên bản ổn định đã qua tích hợp kiểm thử.
   * **Các thành viên tự giác thống nhất không push trực tiếp lên `main`**, mà làm việc độc lập trên nhánh chức năng của mình:
     * Nhánh phát triển phần cứng & firmware: `feature/firmware`
     * Nhánh phát triển Gateway & giao diện: `feature/gateway`
     * Nhánh phát triển Cloud & tích hợp: `feature/cloud-integration`
2. **Quy trình tích hợp:**
   * Mỗi khi hoàn thành một mô-đun, thành viên tạo **Pull Request (PR)** từ nhánh feature vào nhánh `main`.
   * Các thành viên còn lại review mã nguồn trước khi merge nhằm đảm bảo tính toàn vẹn của hệ thống.
3. **An toàn bảo mật (LƯU Ý QUAN TRỌNG):**
   * File `.gitignore` chỉ có tác dụng bỏ qua các tệp cấu hình được khai báo (như `.env`, `tokens.txt`). 
   * **Thành viên tuyệt đối KHÔNG viết cứng (hardcode) mật khẩu Wi-Fi, Token CoreIOT vào trong mã nguồn C++/Python.** Mọi thông tin nhạy cảm phải được đưa vào file cấu hình môi trường hoặc cấu hình riêng ngoài repo.
