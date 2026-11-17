#pragma once

// ============================================================================
// Cau hinh phan cung & giao thuc cho Node A (Sensor: Modbus RS485 + ESP-NOW)
// ============================================================================

// 1. Che do gia lap cam bien (CHI DUNG DE TEST ESP-NOW KHI CHUA CO CAM BIEN THAT)
//    0 = Doc cam bien Modbus RS485 that (Bat buoc cho T02)
//    1 = Phat so lieu gia lap de test ESP-NOW (T06) giua 2 board YoloUNO
#define USE_MOCK_SENSOR 0

// 2. Cau hinh UART ket noi module UART <-> RS485 (3.3V)
//    Kiem tra lai chan thuc te tren YoloUNO ESP32-S3 truoc khi dau day
#define RS485_RX_PIN    18
#define RS485_TX_PIN    17
#define RS485_DE_RE_PIN -1      // Dat -1 neu dung module RS485 tu dong chuyen huong; hoac so GPIO (vd: 4) neu co chan DE/RE

// 3. Thong so Modbus RTU (CAP NHAT DUNG THEO DATASHEET CAM BIEN THAT)
#define MODBUS_BAUDRATE     9600
#define MODBUS_SLAVE_ID     1
#define MODBUS_FUNC_INPUT   1   // 1 = Read Input Registers (0x04), 0 = Read Holding Registers (0x03)
#define REG_ADDR_TEMP       0x0001  // Vi du thanh ghi nhiet do (kiem tra datasheet!)
#define REG_ADDR_HUMI       0x0002  // Vi du thanh ghi do am (kiem tra datasheet!)
#define REG_SCALE_TEMP      10.0f   // He so chia (vd: 285 -> 28.5 C)
#define REG_SCALE_HUMI      10.0f   // He so chia (vd: 652 -> 65.2 %)

// 4. Cau hinh ESP-NOW & Chu ky gui
#define ESPNOW_WIFI_CHANNEL 1
#define TELEMETRY_INTERVAL_MS 5000
