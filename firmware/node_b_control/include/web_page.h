#pragma once
#include <pgmspace.h>

// Giao dien web nhung gon nhe tren Node B (T07)
// Khong phu thuoc thu vien ngoai Internet; Thanh vien B co the thay the file nay sau.
const char INDEX_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Node B - Điều khiển cục bộ</title>
  <style>
    body { font-family: system-ui, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 20px; display: flex; justify-content: center; }
    .card { background: #1e293b; border-radius: 14px; padding: 24px; max-width: 400px; width: 100%; box-shadow: 0 8px 24px rgba(0,0,0,0.35); }
    h1 { font-size: 1.25rem; margin: 0 0 16px; color: #38bdf8; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 18px; }
    .metric { background: #0f172a; padding: 14px; border-radius: 10px; text-align: center; }
    .label { font-size: 0.8rem; color: #94a3b8; }
    .val { font-size: 1.6rem; font-weight: 700; margin-top: 4px; }
    .status { font-size: 0.85rem; color: #cbd5e1; margin-bottom: 16px; display: flex; justify-content: space-between; }
    button { width: 100%; padding: 14px; border: none; border-radius: 10px; font-size: 1rem; font-weight: 600; cursor: pointer; transition: 0.2s; }
    .on { background: #22c55e; color: #052e16; }
    .off { background: #ef4444; color: #fff; }
    .meta { font-size: 0.75rem; color: #64748b; margin-top: 12px; text-align: center; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Smart Room - Node B (Local AP)</h1>
    <div class="grid">
      <div class="metric">
        <div class="label">Nhiệt độ</div>
        <div class="val" id="temp">-- °C</div>
      </div>
      <div class="metric">
        <div class="label">Độ ẩm</div>
        <div class="val" id="humi">-- %</div>
      </div>
    </div>
    <div class="status">
      <span>Trạng thái làm mát (LED):</span>
      <strong id="stateText">ĐANG TẮT</strong>
    </div>
    <button id="toggleBtn" class="on" onclick="toggleCooling()">BẬT LÀM MÁT</button>
    <div class="meta">Gói tin ESP-NOW seq: <span id="seq">0</span></div>
  </div>
  <script>
    let currentState = false;
    async function fetchStatus() {
      try {
        const res = await fetch('/api/status');
        const data = await res.json();
        document.getElementById('temp').textContent = data.sensor_valid ? data.temperature.toFixed(1) + ' °C' : 'N/A';
        document.getElementById('humi').textContent = data.sensor_valid ? data.humidity.toFixed(1) + ' %' : 'N/A';
        document.getElementById('seq').textContent = data.seq;
        currentState = !!data.cooling_state;
        updateButton();
      } catch (e) {}
    }
    function updateButton() {
      const btn = document.getElementById('toggleBtn');
      const txt = document.getElementById('stateText');
      if (currentState) {
        txt.textContent = 'ĐANG BẬT';
        btn.textContent = 'TẮT LÀM MÁT';
        btn.className = 'off';
      } else {
        txt.textContent = 'ĐANG TẮT';
        btn.textContent = 'BẬT LÀM MÁT';
        btn.className = 'on';
      }
    }
    async function toggleCooling() {
      const next = !currentState;
      const res = await fetch('/api/control', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({state: next})
      });
      const data = await res.json();
      if (data.ok) {
        currentState = !!data.cooling_state;
        updateButton();
      }
    }
    fetchStatus();
    setInterval(fetchStatus, 2000);
  </script>
</body>
</html>
)rawliteral";
