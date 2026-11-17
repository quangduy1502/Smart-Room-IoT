#pragma once
#include <stdint.h>
#include <stdbool.h>

// Goi tin ESP-NOW dung chung giua Node A (gui) va Node B (nhan)
typedef struct __attribute__((packed)) {
    uint32_t seq;          // So thu tu goi tin tang dan de thong ke mat goi (T06)
    float temperature;     // Nhiet do (°C)
    float humidity;        // Do am (%)
    bool sensor_valid;     // true neu doc Modbus thanh cong
} SensorPacket;
