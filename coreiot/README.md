# Hướng dẫn triển khai CoreIOT Cloud (Phần C: T11, T12, T13)

Thư mục `coreiot/` chứa các tệp cấu hình nền tảng đám mây CoreIOT (ThingsBoard) cho đề tài **Smart Room IoT**, tương thích hoàn toàn với giao ước MQTT & RPC đã chốt giữa 3 thành viên.

---

## 1. Tạo Device & Bàn giao Access Token an toàn

1. Đăng nhập tài khoản CoreIOT của nhóm.
2. Tạo **Device Profile** mới tên `SmartRoom_Profile` (Transport: `MQTT`).
3. Tạo **Device** mới tên **`SmartRoom_Gateway`**, chọn Device Profile vừa tạo.
4. Vào tab **Credentials** → copy **Access Token**.
5. **Lưu ý bảo mật:**
   * Tuyệt đối **không** commit Access Token thật lên GitHub.
   * Thành viên C tạo file cục bộ `tests/.env` (từ `tests/.env.example`) để tự test T11/T12/T13.
   * Khi bàn giao cho Thành viên B (Gateway thật), gửi Access Token qua kênh riêng tư (Zalo/Messenger) để B đưa vào `.env` của Gateway.

---

## 2. Tự kiểm thử CoreIOT bằng Mock Gateway (không cần chờ A/B)

Trong `tests/`, chạy script giả lập Gateway MQTT để test thông suốt toàn bộ Dashboard, RuleChain và Notification:

```powershell
# 1. Cài đặt thư viện
pip install -r tests/requirements.txt

# 2. Tạo file tests/.env từ mẫu và điền COREIOT_ACCESS_TOKEN thật
copy tests\.env.example tests\.env

# 3. Kịch bản kiểm chứng RuleChain T12 (tự gửi 11 mốc nhiệt độ >32°C và <=30°C)
python tests/coreiot_mock_gateway.py --scenario rulechain

# 4. Hoặc chế độ tương tác để tự test Dashboard T11 và bấm giờ Notification T13
python tests/coreiot_mock_gateway.py --scenario interactive
```

---

## 3. T11 (1.0đ) – Template & Dashboard Giám sát / Điều khiển

* File mẫu: [`dashboard_smart_room.json`](./dashboard_smart_room.json).
* **Cách sử dụng:**
  1. Trên CoreIOT → **Dashboards** → **Import dashboard** → chọn `dashboard_smart_room.json` (hoặc tạo từ Template sẵn có trên CoreIOT rồi đặt cấu hình tương đương).
  2. Mở **Entity Aliases** → chỉnh alias `SmartRoomDevice` trỏ đúng vào Device `SmartRoom_Gateway` của nhóm.
  3. Kiểm tra đủ 6 widget:
     * Thẻ `temperature` (°C), thẻ `humidity` (%), thẻ `cooling_state` (ON/OFF).
     * Biểu đồ chuỗi thời gian (`temperature`, `humidity`).
     * Công tắc Switch RPC: gửi `method: "setCooling"`, `params: {"state": true/false}` và đọc trạng thái hiển thị từ telemetry `cooling_state`.
     * Bảng Alarms (`High Temperature`).

---

## 4. T12 (1.0đ) – RuleChain có nhớ trạng thái & Chống lặp RPC

* File cấu hình: [`rulechain_smart_room_cooling.json`](./rulechain_smart_room_cooling.json)
* Mã script dự phòng (copy-paste nếu dựng tay): [`rulechain_scripts.js`](./rulechain_scripts.js)

### Cơ chế chống lặp lệnh & ưu tiên điều khiển thủ công
1. **Nhánh `HighTemp` (`temperature > 32°C`)** đi qua node **Create Alarm** (`High Temperature`):
   * Lần đầu vượt `32°C` (chưa có Alarm Active): node xuất ra nhánh **`Created`** → nối tới node tạo RPC `setCooling(true)` → tự động bật LED.
   * Các chu kỳ sau (5 giây/lần) nếu nhiệt độ vẫn `> 32°C`: Alarm đã tồn tại nên node xuất ra nhánh **`Updated`** → **KHÔNG nối tiếp** → tuyệt đối không gửi lại `setCooling(true)` mỗi 5s, và nếu người dùng vừa bấm tắt thủ công trên Web ESP32 hoặc Dashboard thì trạng thái thủ công không bị ghi đè lặp lại.
2. **Vùng trễ (`30°C < temperature <= 32°C`):** trả về nhánh `Hysteresis` (không nối), giữ nguyên trạng thái hiện tại để tránh bật/tắt liên tục quanh ngưỡng.
3. **Nhánh `NormalTemp` (`temperature <= 30°C`)** đi qua node **Clear Alarm** (`High Temperature`):
   * Khi Alarm chuyển từ Active sang Clear: node xuất ra nhánh **`Cleared`** → nối tới node tạo RPC `setCooling(false)` → tự động tắt LED.
   * Khi nhiệt độ bình thường lâu dài (không có Alarm): node xuất ra nhánh `False` → không phát lệnh thừa.

### Cách gắn RuleChain trên CoreIOT
1. Vào **Rule Chains** → **Import rule chain** → chọn `rulechain_smart_room_cooling.json` (bật **Debug** trên các node để chụp log minh chứng trước/sau).
2. Vào **Device Profiles** → `SmartRoom_Profile` → đổi **Default rule chain** thành `Smart Room Auto Cooling (T12)` *(hoặc đặt RuleChain này làm rule con được gọi từ Root Rule Chain theo Device Profile)*.
3. **Lưu ý:** Nếu CoreIOT của trường không dùng được JS engine mà dùng TBEL, mở từng node script trên UI và chuyển `scriptLang` sang `TBEL` (đã có sẵn cả `jsScript` và `tbelScript` trong file JSON).

---

## 5. T13 (0.5đ) – Notification trên nền tảng CoreIOT

1. Kiểm tra sớm quyền tài khoản trên CoreIOT (**Notification center** → **Rules**).
2. Tạo **Notification Rule**:
   * **Trigger:** `Alarm` (khi `Alarm type = High Temperature`, trạng thái `Created`).
   * **Delivery methods:** `Web` (hiển thị chuông/popup trực tiếp trên giao diện người dùng CoreIOT).
   * **Recipients:** Chọn tài khoản người dùng đang đăng nhập của nhóm.
   * **Template:** Ví dụ `Cảnh báo phòng học quá nhiệt (>32°C) - Hệ thống đã kích hoạt làm mát`.
3. Tạo **Notification Target** (nếu tài khoản yêu cầu tách Target trước khi tạo Rule).
4. **Phương án dự phòng (theo mục 10 file phân công):** Chỉ chuyển sang Telegram Bot nếu quyền tài khoản CoreIOT bị giới hạn không tạo được Notification Rule và **đã được giảng viên/trợ giảng xác nhận**.

---

## 6. Việc cần làm sau khi test thành công trên tài khoản CoreIOT thật

Các file JSON hiện tại trong thư mục này là bản chuẩn hóa sẵn dùng. Sau khi import và chạy thông suốt trên tài khoản CoreIOT của nhóm, Thành viên C cần:
1. **Export lại JSON thật** (Dashboard + RuleChain) từ giao diện CoreIOT để ghi đè vào `coreiot/` (bảo đảm khớp 100% ID thực tế trên server trường).
2. Chụp đủ ảnh minh chứng (Template/Dashboard, sơ đồ RuleChain + Debug event log `Created`/`Updated`/`Cleared`, và popup/chuông Notification T13) lưu phục vụ báo cáo và cập nhật vào [`docs/evidence_checklist_8pts.md`](../docs/evidence_checklist_8pts.md).
