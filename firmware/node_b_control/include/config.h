#pragma once

// ============================================================================
// Cau hinh phan cung & giao thuc cho Node B (Control: ESP-NOW + SoftAP + Web + Serial)
// ============================================================================

// 1. LED RGB NeoPixel (WS2812B) tich hop tren YoloUNO ESP32-S3
//    Luu y: YoloUNO (OhStem) thuong dung GPIO 45; mot so kit ESP32-S3 dung GPIO 48.
//    Kiem tra lai chan thuc te tren board cua ban va cap nhat tai day.
#define NEOPIXEL_PIN    45
#define NEOPIXEL_COUNT  1

// 2. Kenh Wi-Fi chung cho ESP-NOW va SoftAP (phai khop voi Node A)
#define ESPNOW_WIFI_CHANNEL 1

// 3. Toc do USB Serial giao tiep voi Laptop Gateway
#define SERIAL_BAUD     115200
