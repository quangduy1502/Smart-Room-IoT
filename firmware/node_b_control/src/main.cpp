#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include <Adafruit_NeoPixel.h>
#include <ArduinoJson.h>

#include "config.h"
#include "espnow_protocol.h"
#include "web_page.h"

#if __has_include("secrets.h")
  #include "secrets.h"
#else
  #warning "Khong tim thay include/secrets.h! Dang dung SSID/Password mau trong secrets.example.h."
  #include "secrets.example.h"
#endif

Adafruit_NeoPixel strip(NEOPIXEL_COUNT, NEOPIXEL_PIN, NEO_GRB + NEO_KHZ800);
WebServer server(80);

// Du lieu moi nhat tu Node A
static SensorPacket latestData = {0, 0.0f, 0.0f, false};
static SensorPacket rxBuffer = {};
static volatile bool hasNewPacket = false;
static uint8_t lastSenderMac[6] = {0};
static portMUX_TYPE rxMux = portMUX_INITIALIZER_UNLOCKED;

// Trang thai thiet bi lam mat (Single Source of Truth)
static bool coolingState = false;
static unsigned long lastRxMs = 0;

// Bo dem nhan lenh USB Serial tu Laptop Gateway
static String serialLineBuf = "";

// Cap nhat LED NeoPixel va tuy chon phat event dong bo trang thai
void applyCoolingState(bool newState, bool emitEvent) {
    bool changed = (coolingState != newState);
    coolingState = newState;

    if (coolingState) {
        strip.setPixelColor(0, strip.Color(0, 150, 255)); // Xanh duong sang (Cooling ON)
    } else {
        strip.setPixelColor(0, strip.Color(0, 0, 0));     // Tat LED (Cooling OFF)
    }
    strip.show();

    if (emitEvent && changed) {
        JsonDocument doc;
        doc["type"] = "event";
        doc["event"] = "state_changed";
        doc["cooling_state"] = coolingState;
        serializeJson(doc, Serial);
        Serial.println();
    }
}

void sendTelemetryJson(const SensorPacket &pkt) {
    JsonDocument doc;
    doc["type"] = "telemetry";
    doc["seq"] = pkt.seq;
    doc["temperature"] = roundf(pkt.temperature * 100.0f) / 100.0f;
    doc["humidity"] = roundf(pkt.humidity * 100.0f) / 100.0f;
    doc["cooling_state"] = coolingState;
    serializeJson(doc, Serial);
    Serial.println();
}

void sendAckJson(long requestId, bool ok, const char *errMsg = nullptr) {
    JsonDocument doc;
    doc["type"] = "ack";
    doc["request_id"] = requestId;
    doc["ok"] = ok;
    if (ok) {
        doc["cooling_state"] = coolingState;
    } else if (errMsg != nullptr) {
        doc["error"] = errMsg;
    }
    serializeJson(doc, Serial);
    Serial.println();
}

// Callback nhan ESP-NOW (chi copy du lieu nhanh, khong xu ly nang trong ISR)
#if ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(5, 0, 0)
void onEspNowRecv(const esp_now_recv_info_t *info, const uint8_t *incomingData, int len) {
    const uint8_t *mac = info->src_addr;
#else
void onEspNowRecv(const uint8_t *mac, const uint8_t *incomingData, int len) {
#endif
    if (len != sizeof(SensorPacket)) return;
    portENTER_CRITICAL_ISR(&rxMux);
    memcpy(&rxBuffer, incomingData, sizeof(SensorPacket));
    memcpy(lastSenderMac, mac, 6);
    hasNewPacket = true;
    portEXIT_CRITICAL_ISR(&rxMux);
}

// --- Webserver Handlers (T07) ---
void handleRoot() {
    server.send_P(200, "text/html", INDEX_HTML);
}

void handleApiStatus() {
    JsonDocument doc;
    doc["temperature"] = roundf(latestData.temperature * 100.0f) / 100.0f;
    doc["humidity"] = roundf(latestData.humidity * 100.0f) / 100.0f;
    doc["cooling_state"] = coolingState;
    doc["seq"] = latestData.seq;
    doc["sensor_valid"] = latestData.sensor_valid;
    doc["last_rx_ms"] = (lastRxMs > 0) ? (millis() - lastRxMs) : 0;

    String out;
    serializeJson(doc, out);
    server.send(200, "application/json", out);
}

void handleApiControl() {
    if (!server.hasArg("plain")) {
        server.send(400, "application/json", "{\"ok\":false,\"error\":\"missing_body\"}");
        return;
    }

    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, server.arg("plain"));
    if (err || !doc["state"].is<bool>()) {
        server.send(400, "application/json", "{\"ok\":false,\"error\":\"invalid_json\"}");
        return;
    }

    bool targetState = doc["state"].as<bool>();
    Serial.printf("[DEBUG] [WEB] Nhan lenh doi cooling_state -> %s\n", targetState ? "true" : "false");
    applyCoolingState(targetState, true);

    JsonDocument resp;
    resp["ok"] = true;
    resp["cooling_state"] = coolingState;
    String out;
    serializeJson(resp, out);
    server.send(200, "application/json", out);
}

void initWifiAndEspNow() {
    WiFi.mode(WIFI_AP_STA);
    WiFi.softAP(AP_SSID, AP_PASSWORD, ESPNOW_WIFI_CHANNEL);
    esp_wifi_set_channel(ESPNOW_WIFI_CHANNEL, WIFI_SECOND_CHAN_NONE);

    Serial.print("[DEBUG] [NODE B] STA MAC Address (Copy sang Node A): ");
    Serial.println(WiFi.macAddress());
    Serial.printf("[DEBUG] [NODE B] SoftAP SSID: %s | IP: %s | Channel: %d\n",
                  AP_SSID, WiFi.softAPIP().toString().c_str(), ESPNOW_WIFI_CHANNEL);

    if (esp_now_init() != ESP_OK) {
        Serial.println("[DEBUG] [ESP-NOW] Loi khoi tao esp_now_init()");
        return;
    }
    esp_now_register_recv_cb(onEspNowRecv);
    Serial.println("[DEBUG] [ESP-NOW] San sang nhan goi tin tu Node A");
}

void processSerialLine(const String &line) {
    if (line.length() == 0) return;

    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, line);
    if (err) {
        Serial.printf("[DEBUG] [SERIAL] Bo qua dong khong phai JSON hop le: %s\n", line.c_str());
        return;
    }

    const char *type = doc["type"] | "";
    if (strcmp(type, "command") != 0) {
        Serial.printf("[DEBUG] [SERIAL] Khong phai command: %s\n", type);
        return;
    }

    long requestId = doc["request_id"] | -1;
    const char *cmd = doc["cmd"] | "";

    if (strcmp(cmd, "set_cooling") == 0 && doc["state"].is<bool>() && requestId >= 0) {
        bool targetState = doc["state"].as<bool>();
        Serial.printf("[DEBUG] [SERIAL] Thuc thi set_cooling=%s (request_id=%ld)\n",
                      targetState ? "true" : "false", requestId);
        applyCoolingState(targetState, true);
        sendAckJson(requestId, true);
    } else {
        Serial.printf("[DEBUG] [SERIAL] Lenh khong hop le (request_id=%ld)\n", requestId);
        sendAckJson(requestId, false, "invalid_command");
    }
}

void pollSerialCommands() {
    while (Serial.available() > 0) {
        char c = (char)Serial.read();
        if (c == '\n') {
            serialLineBuf.trim();
            processSerialLine(serialLineBuf);
            serialLineBuf = "";
        } else if (c != '\r') {
            serialLineBuf += c;
            if (serialLineBuf.length() > 512) {
                serialLineBuf = ""; // Chong tran bo dem neu rac
            }
        }
    }
}

void setup() {
    Serial.begin(SERIAL_BAUD);
    delay(1500);
    Serial.println("\n[DEBUG] === KHOI DONG NODE B (CONTROL + WEBSERVER + SERIAL) ===");

    strip.begin();
    strip.setBrightness(60);
    applyCoolingState(false, false);

    initWifiAndEspNow();

    server.on("/", HTTP_GET, handleRoot);
    server.on("/api/status", HTTP_GET, handleApiStatus);
    server.on("/api/control", HTTP_POST, handleApiControl);
    server.begin();
    Serial.println("[DEBUG] [WEB] HTTP Server da khoi dong tai port 80");
}

void loop() {
    server.handleClient();
    pollSerialCommands();

    if (hasNewPacket) {
        SensorPacket pkt;
        uint8_t mac[6];
        portENTER_CRITICAL(&rxMux);
        pkt = rxBuffer;
        memcpy(mac, lastSenderMac, 6);
        hasNewPacket = false;
        portEXIT_CRITICAL(&rxMux);

        latestData = pkt;
        lastRxMs = millis();

        Serial.printf("[DEBUG] [ESP-NOW] Nhan tu %02X:%02X:%02X:%02X:%02X:%02X | seq=%lu | valid=%s | T=%.2f | H=%.2f\n",
                      mac[0], mac[1], mac[2], mac[3], mac[4], mac[5],
                      (unsigned long)pkt.seq,
                      pkt.sensor_valid ? "true" : "false",
                      pkt.temperature,
                      pkt.humidity);

        if (pkt.sensor_valid) {
            sendTelemetryJson(pkt);
        }
    }
}
