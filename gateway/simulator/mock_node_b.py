"""
MOCK NODE B SIMULATOR
Dành cho Thành viên B và C kiểm thử kết nối Gateway và CoreIOT từ sớm (Tuần 10).
Tự động phát sinh JSON Telemetry và phản hồi lệnh ACK.
"""

import time
import random
import json

def run_mock():
    seq = 0
    cooling_state = False
    print("==================================================")
    print("🚀 MOCK NODE B SIMULATOR ĐANG CHẠY...")
    print("Phát sinh dữ liệu Telemetry mỗi 5 giây theo chuẩn JSON.")
    print("Bấm Ctrl+C để dừng.")
    print("==================================================")
    
    while True:
        seq += 1
        # Giả lập nhiệt độ phòng dao động 27.0 - 33.5°C
        temp = round(28.0 + random.uniform(-1.5, 3.5), 1)
        hum = round(65.0 + random.uniform(-5.0, 5.0), 1)
        
        # Tạo gói tin đúng chuẩn hợp đồng Mục 5
        payload = {
            "type": "telemetry",
            "seq": seq,
            "temperature": temp,
            "humidity": hum,
            "cooling_state": cooling_state
        }
        
        json_str = json.dumps(payload)
        print(f"[SERIAL OUT] {json_str}")
        time.sleep(5)

if __name__ == "__main__":
    run_mock()
