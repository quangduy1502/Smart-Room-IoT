# Sơ đồ nối dây & Cấu hình GPIO (Phần cứng - Thành viên A)

## 1. Node A – YoloUNO ESP32-S3 (Cảm biến Modbus RS485 + Phát ESP-NOW)

| Thiết bị / Chân | Chân trên YoloUNO ESP32-S3 | Ghi chú |
| :--- | :--- | :--- |
| **Module UART ↔ RS485 (3.3V)** `VCC` | `3V3` | Bắt buộc dùng mức 3.3V tương thích ESP32-S3 |
| **Module UART ↔ RS485** `GND` | `GND` | Nối chung mass (GND) với cả YoloUNO và nguồn cảm biến |
| **Module UART ↔ RS485** `TXD` (hoặc `RO`) | `GPIO 18` (`RS485_RX_PIN`) | Có thể đổi trong `include/config.h` |
| **Module UART ↔ RS485** `RXD` (hoặc `DI`) | `GPIO 17` (`RS485_TX_PIN`) | Có thể đổi trong `include/config.h` |
| **Module UART ↔ RS485** `DE/RE` | Không nối (`-1`) nếu auto-direction | Nếu module có chân `DE/RE`, nối chung vào 1 GPIO và khai báo `RS485_DE_RE_PIN` |
| **Cảm biến Modbus** `A+` / `B-` | Nối vào `A+` / `B-` của module RS485 | Đấu đúng cực A với A, B với B |
| **Cảm biến Modbus** `VCC` / `GND` | Nguồn riêng theo datasheet (5V–12V) | **Bắt buộc** nối chung `GND` với YoloUNO A |

---

## 2. Node B – YoloUNO ESP32-S3 (Nhận ESP-NOW + Webserver SoftAP + USB Serial)

| Thiết bị / Chân | Chân trên YoloUNO ESP32-S3 | Ghi chú |
| :--- | :--- | :--- |
| **LED RGB NeoPixel (WS2812B)** | `GPIO 45` (`NEOPIXEL_PIN`) | Trên YoloUNO (OhStem) thường là `GPIO 45`; kiểm tra lại nếu dùng board khác (`GPIO 48`) |
| **USB-C (Native USB / UART)** | Cổng USB trên board | Kết nối Laptop Gateway ở tốc độ `115200 baud` |

---

## 3. Quy trình chạy thử nhanh (Bring-up Checklist)

1. **Tạo file cấu hình riêng (không commit lên Git):**
   - Trong `firmware/node_b_control/include/`: copy `secrets.example.h` → `secrets.h` (đổi SSID/Password nếu muốn).
   - Nạp firmware cho **Node B**, mở Serial Monitor (`115200`) để lấy dòng:
     `[DEBUG] [NODE B] STA MAC Address (Copy sang Node A): XX:XX:XX:XX:XX:XX`
   - Trong `firmware/node_a_sensor/include/`: copy `secrets.example.h` → `secrets.h` và điền 6 byte MAC của Node B vào `NODE_B_MAC_ADDR`.
2. **Test ESP-NOW (T06) khi chưa có cảm biến thật:**
   - Tạm đặt `#define USE_MOCK_SENSOR 1` trong `firmware/node_a_sensor/include/config.h` để test truyền nhận `seq` giữa Node A và Node B.
   - *(Lưu ý: Khi có cảm biến Modbus thật, bắt buộc trả `USE_MOCK_SENSOR` về `0` và cập nhật `MODBUS_BAUDRATE`, `MODBUS_SLAVE_ID`, `REG_ADDR_TEMP`, `REG_ADDR_HUMI`, `REG_SCALE_*` đúng theo datasheet).*
3. **Test Webserver SoftAP (T07) + ESP-NOW đồng thời:**
   - Dùng điện thoại kết nối Wi-Fi `SmartRoom_NodeB`, mở trình duyệt truy cập `http://192.168.4.1`.
   - Bấm nút **BẬT / TẮT LÀM MÁT**, quan sát LED NeoPixel trên Node B đổi trạng thái và Serial Monitor in ra gói `{"type":"event","event":"state_changed","cooling_state":...}` đồng thời vẫn nhận đều gói `seq` từ Node A.
