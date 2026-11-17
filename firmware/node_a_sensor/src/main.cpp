#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include <ModbusMaster.h>

#include "config.h"
#include "espnow_protocol.h"

#if __has_include("secrets.h")
  #include "secrets.h"
#else
  #warning "Khong tim thay include/secrets.h! Dang dung MAC mau trong secrets.example.h."
  #include "secrets.example.h"
#endif

HardwareSerial RS485Serial(1);
ModbusMaster modbusNode;

static uint32_t packetSeq = 0;
static uint32_t espNowOkCount = 0;
static uint32_t espNowFailCount = 0;
static uint32_t modbusOkCount = 0;
static uint32_t modbusErrCount = 0;
static unsigned long lastSendMs = 0;

// Dieukhien chan DE/RE neu dung module RS485 khong tu dong chuyen huong
void preTransmission() {
    if (RS485_DE_RE_PIN >= 0) {
        digitalWrite(RS485_DE_RE_PIN, HIGH);
        delayMicroseconds(50);
    }
}

void postTransmission() {
    if (RS485_DE_RE_PIN >= 0) {
        delayMicroseconds(50);
        digitalWrite(RS485_DE_RE_PIN, LOW);
    }
}

// Callback ket qua gui ESP-NOW (tuong thich ca ESP-IDF v4 va v5)
#if ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(5, 0, 0)
void onEspNowSent(const wifi_tx_info_t *info, esp_now_send_status_t status) {
#else
void onEspNowSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
#endif
    if (status == ESP_NOW_SEND_SUCCESS) {
        espNowOkCount++;
        Serial.printf("[DEBUG] [ESP-NOW] Gui thanh cong (OK=%lu, FAIL=%lu)\n",
                      (unsigned long)espNowOkCount, (unsigned long)espNowFailCount);
    } else {
        espNowFailCount++;
        Serial.printf("[DEBUG] [ESP-NOW] Gui THAT BAI (OK=%lu, FAIL=%lu)\n",
                      (unsigned long)espNowOkCount, (unsigned long)espNowFailCount);
    }
}

bool initEspNow() {
    WiFi.mode(WIFI_STA);
    WiFi.disconnect();
    esp_wifi_set_channel(ESPNOW_WIFI_CHANNEL, WIFI_SECOND_CHAN_NONE);

    Serial.print("[DEBUG] [NODE A] STA MAC Address: ");
    Serial.println(WiFi.macAddress());
    Serial.printf("[DEBUG] [NODE A] Wi-Fi Channel: %d\n", ESPNOW_WIFI_CHANNEL);

    if (esp_now_init() != ESP_OK) {
        Serial.println("[DEBUG] [ESP-NOW] Loi khoi tao esp_now_init()");
        return false;
    }

    esp_now_register_send_cb(onEspNowSent);

    esp_now_peer_info_t peerInfo = {};
    memcpy(peerInfo.peer_addr, NODE_B_MAC_ADDR, 6);
    peerInfo.channel = ESPNOW_WIFI_CHANNEL;
    peerInfo.encrypt = false;

    if (esp_now_add_peer(&peerInfo) != ESP_OK) {
        Serial.println("[DEBUG] [ESP-NOW] Loi them peer Node B");
        return false;
    }

    Serial.printf("[DEBUG] [ESP-NOW] Da them Node B MAC: %02X:%02X:%02X:%02X:%02X:%02X\n",
                  NODE_B_MAC_ADDR[0], NODE_B_MAC_ADDR[1], NODE_B_MAC_ADDR[2],
                  NODE_B_MAC_ADDR[3], NODE_B_MAC_ADDR[4], NODE_B_MAC_ADDR[5]);
    return true;
}

bool readModbusSensor(float &tempOut, float &humiOut) {
#if USE_MOCK_SENSOR
    // CHI DUNG DE TEST ESP-NOW KHI CHUA CO CAM BIEN THAT
    tempOut = 27.5f + (random(-20, 60) / 10.0f);
    humiOut = 62.0f + (random(-50, 50) / 10.0f);
    Serial.printf("[DEBUG] [MOCK] Temp=%.1f C, Humi=%.1f %% (KHONG DUNG CHO T02!)\n",
                  tempOut, humiOut);
    return true;
#else
    uint8_t resTemp;
    uint8_t resHumi;

    // Doc thanh ghi nhiet do
    if (MODBUS_FUNC_INPUT) {
        resTemp = modbusNode.readInputRegisters(REG_ADDR_TEMP, 1);
    } else {
        resTemp = modbusNode.readHoldingRegisters(REG_ADDR_TEMP, 1);
    }

    if (resTemp != modbusNode.ku8MBSuccess) {
        modbusErrCount++;
        Serial.printf("[DEBUG] [MODBUS] Loi doc nhiet do: 0x%02X (OK=%lu, ERR=%lu)\n",
                      resTemp, (unsigned long)modbusOkCount, (unsigned long)modbusErrCount);
        return false;
    }
    int16_t rawTemp = (int16_t)modbusNode.getResponseBuffer(0);
    tempOut = rawTemp / REG_SCALE_TEMP;
    delay(20);

    // Doc thanh ghi do am
    if (MODBUS_FUNC_INPUT) {
        resHumi = modbusNode.readInputRegisters(REG_ADDR_HUMI, 1);
    } else {
        resHumi = modbusNode.readHoldingRegisters(REG_ADDR_HUMI, 1);
    }

    if (resHumi != modbusNode.ku8MBSuccess) {
        modbusErrCount++;
        Serial.printf("[DEBUG] [MODBUS] Loi doc do am: 0x%02X (OK=%lu, ERR=%lu)\n",
                      resHumi, (unsigned long)modbusOkCount, (unsigned long)modbusErrCount);
        return false;
    }
    uint16_t rawHumi = modbusNode.getResponseBuffer(0);
    humiOut = rawHumi / REG_SCALE_HUMI;

    modbusOkCount++;
    Serial.printf("[DEBUG] [MODBUS] OK #%lu: Temp=%.2f C, Humi=%.2f %% (ERR=%lu)\n",
                  (unsigned long)modbusOkCount, tempOut, humiOut, (unsigned long)modbusErrCount);
    return true;
#endif
}

void setup() {
    Serial.begin(115200);
    delay(1500);
    Serial.println("\n[DEBUG] === KHOI DONG NODE A (SENSOR + ESP-NOW) ===");

    if (RS485_DE_RE_PIN >= 0) {
        pinMode(RS485_DE_RE_PIN, OUTPUT);
        digitalWrite(RS485_DE_RE_PIN, LOW);
    }

    RS485Serial.begin(MODBUS_BAUDRATE, SERIAL_8N1, RS485_RX_PIN, RS485_TX_PIN);
    modbusNode.begin(MODBUS_SLAVE_ID, RS485Serial);
    modbusNode.preTransmission(preTransmission);
    modbusNode.postTransmission(postTransmission);

    Serial.printf("[DEBUG] [MODBUS] UART1 RX=%d, TX=%d, DE/RE=%d, Baud=%d, SlaveID=%d\n",
                  RS485_RX_PIN, RS485_TX_PIN, RS485_DE_RE_PIN, MODBUS_BAUDRATE, MODBUS_SLAVE_ID);

    initEspNow();
    lastSendMs = millis() - TELEMETRY_INTERVAL_MS; // Gui ngay lan dau
}

void loop() {
    unsigned long now = millis();
    if (now - lastSendMs >= TELEMETRY_INTERVAL_MS) {
        lastSendMs = now;

        float temp = 0.0f;
        float humi = 0.0f;
        bool valid = readModbusSensor(temp, humi);

        packetSeq++;
        SensorPacket pkt = {};
        pkt.seq = packetSeq;
        pkt.temperature = temp;
        pkt.humidity = humi;
        pkt.sensor_valid = valid;

        esp_err_t err = esp_now_send(NODE_B_MAC_ADDR, (uint8_t *)&pkt, sizeof(pkt));
        Serial.printf("[DEBUG] [NODE A] Gui seq=%lu | valid=%s | T=%.2f | H=%.2f | esp_now_send=%s\n",
                      (unsigned long)pkt.seq,
                      pkt.sensor_valid ? "true" : "false",
                      pkt.temperature,
                      pkt.humidity,
                      (err == ESP_OK) ? "OK" : "ERR");
    }
}
