"""
MOCK NODE B SIMULATOR (2-WAY RPC & TELEMETRY)
Phiên bản 2 chiều:
1. Luồng phát Telemetry: Định kỳ mỗi 5 giây in chuỗi JSON telemetry.
2. Luồng nhận Command: Lắng nghe qua standard input (mô phỏng nhận từ Serial), 
   parse JSON lệnh set_cooling, cập nhật trạng thái và trả ngay chuỗi ACK kèm request_id.
"""

import time
import random
import json
import threading
import sys

# Trạng thái toàn cục mô phỏng của Node B
state = {
    "seq": 0,
    "temperature": 28.5,
    "humidity": 65.0,
    "cooling_state": False,
    "running": True
}

def telemetry_thread():
    """Luồng phát Telemetry chu kỳ 5 giây"""
    while state["running"]:
        state["seq"] += 1
        # Giả lập nhiệt độ dao động ngẫu nhiên quanh 28 - 32 độ C
        state["temperature"] = round(28.0 + random.uniform(-1.0, 4.0), 1)
        state["humidity"] = round(65.0 + random.uniform(-5.0, 5.0), 1)
        
        payload = {
            "type": "telemetry",
            "seq": state["seq"],
            "temperature": state["temperature"],
            "humidity": state["humidity"],
            "cooling_state": state["cooling_state"]
        }
        
        # In chuỗi JSON (kết thúc bằng \n) mô phỏng đẩy qua Serial
        sys.stdout.write(json.dumps(payload) + "\n")
        sys.stdout.flush()
        time.sleep(5)

def command_listener_thread():
    """Luồng lắng nghe lệnh Command (mô phỏng nhận từ Serial) và trả về ACK"""
    while state["running"]:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            
            # Thử parse JSON lệnh
            try:
                cmd_data = json.loads(line)
                if cmd_data.get("type") == "command" and cmd_data.get("cmd") == "set_cooling":
                    new_state = bool(cmd_data.get("state", False))
                    req_id = cmd_data.get("request_id", 0)
                    
                    # Cập nhật trạng thái quạt/LED
                    state["cooling_state"] = new_state
                    
                    # Trả về gói ACK đúng chuẩn hợp đồng Mục 5
                    ack_payload = {
                        "type": "ack",
                        "request_id": req_id,
                        "ok": True,
                        "cooling_state": state["cooling_state"]
                    }
                    sys.stdout.write(json.dumps(ack_payload) + "\n")
                    sys.stdout.flush()
                    
                    # Gửi thêm gói đồng bộ trạng thái ngay lập tức
                    sync_payload = {
                        "type": "event",
                        "event": "state_changed",
                        "cooling_state": state["cooling_state"]
                    }
                    sys.stdout.write(json.dumps(sync_payload) + "\n")
                    sys.stdout.flush()
            except json.JSONDecodeError:
                # Bỏ qua nếu không phải JSON
                pass
        except Exception:
            break

def main():
    sys.stderr.write("==================================================\n")
    sys.stderr.write("🚀 MOCK NODE B SIMULATOR (2 CHIỀU) ĐÃ SẴN SÀNG!\n")
    sys.stderr.write("• Telemetry tự động gửi mỗi 5 giây.\n")
    sys.stderr.write("• Nhập thử lệnh JSON sau vào terminal để kiểm tra ACK:\n")
    sys.stderr.write('  {"type":"command", "cmd":"set_cooling", "state":true, "request_id":1}\n')
    sys.stderr.write("• Bấm Ctrl+C để dừng.\n")
    sys.stderr.write("==================================================\n")
    
    t1 = threading.Thread(target=telemetry_thread, daemon=True)
    t2 = threading.Thread(target=command_listener_thread, daemon=True)
    
    t1.start()
    t2.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        state["running"] = False
        sys.stderr.write("\nĐã dừng simulator.\n")

if __name__ == "__main__":
    main()
