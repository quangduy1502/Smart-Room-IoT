# Bảng Checklist Nghiệm Thu 8 Điểm Công Nghệ & Minh Chứng BTL IoT

> **Nguyên tắc chấm:** Tuyệt đối **không** đánh dấu `[x]` trước khi hệ thống chạy thật và có đủ code + log gốc + ảnh + video kiểm chứng thực tế.

---

## 1. Bảng theo dõi 8 mã công nghệ (Mục tiêu: 8.0 / 8.0 điểm)

| Mã | Tính năng công nghệ | Điểm | Phụ trách | Trạng thái | Điều kiện & Minh chứng bắt buộc | Nơi lưu minh chứng dự kiến |
| :---: | :--- | :---: | :---: | :---: | :--- | :--- |
| **T02** | Đọc dữ liệu thật từ cảm biến Modbus RTU/RS485 | 1.0 | Thành viên A | `[ ] Chưa nghiệm thu` | Ảnh nối dây thật + Datasheet/model cảm biến + Log 10–50 lần đọc liên tiếp không dùng mock | `docs/`, `tests/logs/` |
| **T06** | ESP-NOW truyền không dây Node A → Node B | 1.5 | Thành viên A | `[ ] Chưa nghiệm thu` | Log gửi/nhận có `seq` + Ảnh 2 board YoloUNO + Video quay thực tế | `tests/logs/`, thư mục video/ảnh nhóm |
| **T07** | Webserver trên Node B (SoftAP) xem & bật/tắt LED | 1.0 | A (firmware) + B (HTML) | `[ ] Chưa nghiệm thu` | Ảnh IP (`192.168.4.1`), giao diện web điện thoại, LED đổi màu + Video thao tác | Thư mục video/ảnh nhóm |
| **T08** | Laptop Gateway Python (Serial ↔ MQTT & RPC 2 chiều) | 1.0 | Thành viên B | `[ ] Chưa nghiệm thu` | Log 2 chiều phân tách Node A/Node B + Video bấm CoreIOT đổi LED qua Gateway | `gateway/`, `tests/logs/` |
| **T10** | Giao diện Local trên Laptop (`localhost:5000`) | 1.0 | Thành viên B | `[ ] Chưa nghiệm thu` | Ảnh trang web local + Video ngắt Internet vẫn xem & bật/tắt LED qua USB | `gateway/`, thư mục video/ảnh nhóm |
| **T11** | Template & Dashboard giám sát/điều khiển CoreIOT | 1.0 | Thành viên C | `[ ] Chưa nghiệm thu` | Ảnh template/widget + File export JSON thật từ CoreIOT + Video thao tác Switch RPC | `coreiot/dashboard_smart_room.json` |
| **T12** | RuleChain tự động: `T > 32°C` → Alarm → bật LED (chống lặp) | 1.0 | Thành viên C | `[ ] Chưa nghiệm thu` | Ảnh sơ đồ RuleChain + Event log trước/sau (`Created`/`Updated`/`Cleared`) + Video LED tự bật | `coreiot/rulechain_smart_room_cooling.json` |
| **T13** | Notification từ nền tảng CoreIOT khi vượt ngưỡng | 0.5 | Thành viên C | `[ ] Chưa nghiệm thu` | Ảnh cấu hình Notification Rule + Ảnh chuông/popup trên CoreIOT + Trạng thái Alarm | Thư mục video/ảnh nhóm |

---

## 2. Danh sách 5 phép thử định lượng cho Chương 4 Báo cáo

| STT | Phép thử | Cách đo chuẩn | Người giữ kết quả | File dữ liệu đầu vào cho `generate_chapter4_report.py` | Trạng thái |
| :---: | :--- | :--- | :---: | :--- | :---: |
| 1 | **Modbus 50 lần** | Đếm lần đọc OK / 50 lần; thống kê timeout `0xE2` / lỗi địa chỉ `0x02` | A & C | `--modbus-log tests/logs/<modbus_50>.log` | `[ ] Chưa đo` |
| 2 | **ESP-NOW 100 gói ở 1m và 5m** | Gửi `seq` tăng dần (5s/gói) khi **điện thoại đang mở Web AP Node B**; tính tỷ lệ mất gói | A & C | `--espnow-1m-log ... --espnow-5m-log ...` | `[ ] Chưa đo` |
| 3 | **Điều khiển RPC 10 lần** | Gửi lệnh `setCooling` 10 lần từ CoreIOT/Gateway; đối chiếu ACK, LED và độ trễ | B & C | `--rpc-csv` hoặc `--rpc-log` (mẫu `tests/templates/rpc_10_trials.template.csv`) | `[ ] Chưa đo` |
| 4 | **Notification 5 lần** | Tạo tình huống `T > 32°C` 5 lần; ghi thời điểm kích hoạt đến lúc nhận thông báo | C | `--notif-csv` (mẫu `tests/templates/notification_5_trials.template.csv`) | `[ ] Chưa đo` |
| 5 | **Mất Internet / rút cáp USB** | Ngắt Internet test T10 offline; rút/cắm lại USB kiểm tra Gateway tự phục hồi | B & A | Ghi nhận nhật ký kiểm thử + quay clip minh chứng | `[ ] Chưa đo` |

---

## 3. Kịch bản quay Video Demo ngắn (5 – 7 phút)

1. **Giới thiệu mô hình (1 phút):** Giới thiệu 2 board YoloUNO ESP32-S3, cảm biến Modbus RS485, module RS485, nguồn riêng và luồng truyền ESP-NOW.
2. **Demo Webserver Node B – T07 (1 phút):** Điện thoại kết nối Wi-Fi `SmartRoom_NodeB`, mở `http://192.168.4.1`, xem số đo và bật/tắt LED NeoPixel trực tiếp.
3. **Demo Local Gateway – T10 (1.5 phút):** Ngắt Wi-Fi/Internet trên laptop, mở `http://localhost:5000`, xem thông số và bật/tắt LED qua USB Serial.
4. **Demo CoreIOT RPC – T08 & T11 (1.5 phút):** Bật lại Internet, bấm công tắc Switch `setCooling` trên Dashboard CoreIOT, quay đồng thời LED đổi trạng thái và log ACK trên Gateway.
5. **Demo RuleChain & Notification – T12 & T13 (1.5 phút):** Làm ấm cảm biến vượt `32°C` để chứng minh RuleChain tự sinh Alarm `High Temperature`, tự phát RPC bật LED (không lặp lại lệnh khi giữ nhiệt độ cao), hiển thị thông báo Notification trên CoreIOT, và tự tắt LED khi hạ về `<= 30°C`.
