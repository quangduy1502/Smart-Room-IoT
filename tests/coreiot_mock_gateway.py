"""Gia lap IoT Gateway MQTT 2 chieu de Thanh vien C tu test CoreIOT (T11, T12, T13).

Chuc nang chinh:
- Publish telemetry len v1/devices/me/telemetry theo giao uoc:
  {"temperature": ..., "humidity": ..., "cooling_state": ...}
- Subscribe v1/devices/me/rpc/request/+ de nhan lenh setCooling, cap nhat trang thai,
  tra response len v1/devices/me/rpc/response/{requestId} va dong bo lai telemetry.
- Kich ban --scenario rulechain: chay 11 moc nhiet do kiem chung T12 chong lap RPC.
- Kich ban --scenario interactive: gui dinh ky moi 5s + lenh ban phim + bam gio T13 (notif).
- Che do --dry-run: kiem thu noi bo logic xu ly RPC va kich ban T12 khong can broker that.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import paho.mqtt.client as mqtt
except ImportError:  # pragma: no cover
    mqtt = None

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

TELEMETRY_TOPIC = "v1/devices/me/telemetry"
RPC_REQUEST_SUB = "v1/devices/me/rpc/request/+"
RPC_RESPONSE_FMT = "v1/devices/me/rpc/response/{request_id}"

RULECHAIN_TEMPS = [28.5, 29.2, 33.1, 33.8, 34.2, 33.5, 31.5, 31.0, 29.8, 29.2, 28.9]


def now_str() -> str:
    """Return local timestamp formatted to milliseconds."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def mask_token(token: str | None) -> str:
    """Mask access token before printing to console or log."""
    if not token:
        return "<none>"
    if len(token) <= 8:
        return "***"
    return f"{token[:3]}***{token[-3:]}"


def load_env_file(env_path: Path) -> dict[str, str]:
    """Parse key=value pairs from a .env file without external dependencies."""
    values: dict[str, str] = {}
    if not env_path.exists():
        return values
    for raw_line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key:
            values[key] = val
    return values


class SimulatedCoreIOTRuleEngine:
    """Mirrors CoreIOT RuleChain T12 (Create Alarm Created-only / Clear Alarm Cleared-only)."""

    def __init__(self) -> None:
        self.alarm_active = False

    def evaluate(self, temperature: float) -> tuple[str, bool | None]:
        """Return (branch_label, optional_rpc_state) for given temperature."""
        if temperature > 32.0:
            if not self.alarm_active:
                self.alarm_active = True
                return "Created", True
            return "Updated", None
        if temperature <= 30.0:
            if self.alarm_active:
                self.alarm_active = False
                return "Cleared", False
            return "False", None
        return "Hysteresis", None


class MockCoreIOTGateway:
    """Two-way MQTT Gateway mock compatible with CoreIOT and paho-mqtt 2.x."""

    def __init__(
        self,
        host: str,
        port: int,
        token: str | None,
        dry_run: bool,
        log_path: Path,
    ) -> None:
        self.host = host
        self.port = port
        self.token = token
        self.dry_run = dry_run
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_fp = self.log_path.open("w", encoding="utf-8", buffering=1)

        self.state_lock = threading.Lock()
        self.file_lock = threading.Lock()
        self.connected_event = threading.Event()
        self.stop_event = threading.Event()

        self.temperature = 28.5
        self.humidity = 65.0
        self.cooling_state = False

        self.tx_telemetry_count = 0
        self.rpc_history: list[dict[str, Any]] = []
        self.current_step_rpcs: list[dict[str, Any]] = []
        self.client: Any = None
        self.sim_engine = SimulatedCoreIOTRuleEngine()
        self._sim_req_seq = 100

    def log(self, message: str, console: bool = True) -> None:
        """Write timestamped line to log file and optionally stdout."""
        line = f"[{now_str()}] {message}"
        with self.file_lock:
            self.log_fp.write(line + "\n")
        if console:
            print(line)

    def _create_mqtt_client(self) -> Any:
        if mqtt is None:
            raise RuntimeError(
                "Chưa cài paho-mqtt. Chạy: pip install -r tests/requirements.txt"
            )
        client_id = f"smartroom-mock-gw-{int(time.time())}"
        if hasattr(mqtt, "CallbackAPIVersion"):
            client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=client_id,
            )
            client.on_connect = self._on_connect_v2
            client.on_disconnect = self._on_disconnect_v2
        else:
            client = mqtt.Client(client_id=client_id)
            client.on_connect = self._on_connect_v1
            client.on_disconnect = self._on_disconnect_v1
        client.on_message = self._on_message
        client.username_pw_set(self.token)
        return client

    def _on_connect_v2(
        self,
        client: Any,
        userdata: Any,
        flags: Any,
        reason_code: Any,
        properties: Any,
    ) -> None:
        del userdata, flags, properties
        is_ok = (reason_code == 0) or (getattr(reason_code, "value", None) == 0)
        self._handle_connect_result(client, is_ok, str(reason_code))

    def _on_connect_v1(
        self, client: Any, userdata: Any, flags: Any, rc: int
    ) -> None:
        del userdata, flags
        self._handle_connect_result(client, rc == 0, str(rc))

    def _handle_connect_result(self, client: Any, is_ok: bool, rc_text: str) -> None:
        if is_ok:
            self.log(f"[MQTT] Đã kết nối {self.host}:{self.port} (token={mask_token(self.token)})")
            client.subscribe(RPC_REQUEST_SUB, qos=1)
            self.log(f"[MQTT] Đã subscribe {RPC_REQUEST_SUB}")
            self.connected_event.set()
        else:
            self.log(f"[MQTT LỖI] Kết nối thất bại, reason_code={rc_text}")

    def _on_disconnect_v2(
        self,
        client: Any,
        userdata: Any,
        disconnect_flags: Any,
        reason_code: Any,
        properties: Any,
    ) -> None:
        del client, userdata, disconnect_flags, properties
        self.connected_event.clear()
        if not self.stop_event.is_set():
            self.log(f"[MQTT] Ngắt kết nối (reason_code={reason_code})")

    def _on_disconnect_v1(self, client: Any, userdata: Any, rc: int) -> None:
        del client, userdata
        self.connected_event.clear()
        if not self.stop_event.is_set():
            self.log(f"[MQTT] Ngắt kết nối (rc={rc})")

    def _on_message(self, client: Any, userdata: Any, msg: Any) -> None:
        del client, userdata
        topic = str(msg.topic)
        payload_str = msg.payload.decode("utf-8", errors="replace")
        if topic.startswith("v1/devices/me/rpc/request/"):
            request_id = topic.rsplit("/", 1)[-1]
            self.handle_rpc_payload(request_id, payload_str)

    def _publish_json(self, topic: str, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, separators=(",", ":"))
        if self.dry_run:
            self.log(f"[DRY-RUN TX] {topic} <- {raw}")
            return
        if self.client is None or not self.connected_event.is_set():
            self.log(f"[MQTT CẢNH BÁO] Chưa kết nối, bỏ qua publish tới {topic}")
            return
        info = self.client.publish(topic, raw, qos=1)
        info.wait_for_publish(timeout=3.0)
        self.log(f"[MQTT TX] {topic} <- {raw}")

    def publish_telemetry(self) -> None:
        """Publish current temperature, humidity, cooling_state snapshot."""
        with self.state_lock:
            payload = {
                "temperature": round(self.temperature, 2),
                "humidity": round(self.humidity, 2),
                "cooling_state": self.cooling_state,
            }
            self.tx_telemetry_count += 1
        self._publish_json(TELEMETRY_TOPIC, payload)

    def handle_rpc_payload(self, request_id: str, payload_str: str) -> dict[str, Any]:
        """Parse RPC request, apply setCooling, publish response and state telemetry."""
        self.log(f"[RPC RX] request_id={request_id} payload={payload_str}")
        try:
            doc = json.loads(payload_str)
        except json.JSONDecodeError:
            resp = {"ok": False, "error": "invalid_json"}
            self._publish_json(RPC_RESPONSE_FMT.format(request_id=request_id), resp)
            return resp

        method = doc.get("method")
        params = doc.get("params")
        if method != "setCooling":
            resp = {"ok": False, "error": "unsupported_method"}
            self._publish_json(RPC_RESPONSE_FMT.format(request_id=request_id), resp)
            return resp

        target_state: bool | None = None
        if isinstance(params, dict) and isinstance(params.get("state"), bool):
            target_state = params["state"]
        elif isinstance(params, bool):
            self.log(
                "[RPC CẢNH BÁO] Nhận params kiểu boolean trần thay vì {'state': bool} — vẫn xử lý tương thích."
            )
            target_state = params

        if target_state is None:
            resp = {"ok": False, "error": "invalid_params"}
            self._publish_json(RPC_RESPONSE_FMT.format(request_id=request_id), resp)
            return resp

        with self.state_lock:
            self.cooling_state = target_state
            rec = {
                "timestamp": now_str(),
                "request_id": request_id,
                "method": method,
                "target_state": target_state,
                "ok": True,
            }
            self.rpc_history.append(rec)
            self.current_step_rpcs.append(rec)

        resp = {"ok": True, "cooling_state": target_state}
        self._publish_json(RPC_RESPONSE_FMT.format(request_id=request_id), resp)
        self.publish_telemetry()
        return resp

    def connect(self) -> None:
        """Connect to CoreIOT MQTT broker unless in dry-run mode."""
        if self.dry_run:
            self.log("[DRY-RUN] Chạy mô phỏng cục bộ (không kết nối MQTT broker).")
            return
        if not self.token or "PASTE_YOUR" in self.token:
            raise ValueError(
                "Thiếu COREIOT_ACCESS_TOKEN hợp lệ. Hãy tạo tests/.env từ tests/.env.example hoặc truyền --token."
            )
        self.client = self._create_mqtt_client()
        self.client.connect(self.host, self.port, keepalive=60)
        self.client.loop_start()
        if not self.connected_event.wait(timeout=10.0):
            raise TimeoutError(
                f"Hết thời gian chờ kết nối MQTT tới {self.host}:{self.port}"
            )

    def close(self) -> None:
        """Stop MQTT loop and close log file cleanly."""
        self.stop_event.set()
        if self.client is not None:
            try:
                self.client.loop_stop()
                self.client.disconnect()
            except Exception:
                pass
        with self.file_lock:
            self.log_fp.close()

    def run_rulechain_scenario(self, interval: float) -> int:
        """Run 11-step temperature sequence verifying T12 anti-repeat RPC behavior."""
        self.log("=== BẮT ĐẦU KỊCH BẢN KIỂM CHỨNG RULECHAIN T12 (11 MỐC NHIỆT ĐỘ) ===")
        step_records: list[dict[str, Any]] = []

        for idx, temp in enumerate(RULECHAIN_TEMPS):
            if self.stop_event.is_set():
                break
            with self.state_lock:
                self.current_step_rpcs.clear()
                self.temperature = temp
            self.log(f"--- Bước {idx + 1}/{len(RULECHAIN_TEMPS)}: T = {temp:.1f}°C ---")
            self.publish_telemetry()

            if self.dry_run:
                branch, rpc_state = self.sim_engine.evaluate(temp)
                self.log(f"[DRY-RUN RULE] Nhánh RuleChain: {branch}")
                if rpc_state is not None:
                    self._sim_req_seq += 1
                    rpc_payload = json.dumps(
                        {"method": "setCooling", "params": {"state": rpc_state}}
                    )
                    self.handle_rpc_payload(str(self._sim_req_seq), rpc_payload)

            deadline = time.monotonic() + interval
            while time.monotonic() < deadline and not self.stop_event.is_set():
                time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))

            with self.state_lock:
                rpcs = list(self.current_step_rpcs)
            step_records.append({"step": idx + 1, "temp": temp, "rpcs": rpcs})

        if len(step_records) < len(RULECHAIN_TEMPS):
            self.log("[CẢNH BÁO] Kịch bản bị dừng sớm trước khi hoàn tất 11 bước.")
            return 1

        rpc_on_created = sum(
            1 for r in step_records[2]["rpcs"] if r["ok"] and r["target_state"] is True
        )
        rpc_dup_gt32 = sum(len(step_records[i]["rpcs"]) for i in (3, 4, 5))
        rpc_hysteresis = sum(len(step_records[i]["rpcs"]) for i in (6, 7))
        rpc_off_cleared = sum(
            1 for r in step_records[8]["rpcs"] if r["ok"] and r["target_state"] is False
        )
        rpc_unexpected_normal = sum(len(step_records[i]["rpcs"]) for i in (0, 1, 9, 10))

        passed = (
            rpc_on_created == 1
            and rpc_dup_gt32 == 0
            and rpc_hysteresis == 0
            and rpc_off_cleared == 1
            and rpc_unexpected_normal == 0
        )

        report_lines = [
            "",
            "### Báo cáo kiểm chứng RuleChain T12 (Chống lặp lệnh RPC)",
            "",
            "| Bước | Nhiệt độ | Vai trò kiểm thử | Số RPC nhận | Chi tiết |",
            "| :---: | :---: | :--- | :---: | :--- |",
        ]
        labels = [
            "Bình thường (khởi tạo)",
            "Bình thường",
            "Vượt ngưỡng > 32°C (Created -> ON)",
            "Duy trì > 32°C (Updated - chống lặp)",
            "Duy trì > 32°C (Updated - chống lặp)",
            "Duy trì > 32°C (Updated - chống lặp)",
            "Vùng trễ 30 < T <= 32 (giữ nguyên)",
            "Vùng trễ 30 < T <= 32 (giữ nguyên)",
            "Hạ <= 30°C (Cleared -> OFF)",
            "Duy trì <= 30°C (False - không lặp)",
            "Duy trì <= 30°C (False - không lặp)",
        ]
        for rec, lbl in zip(step_records, labels):
            detail = (
                ", ".join(
                    f"setCooling({'true' if r['target_state'] else 'false'})"
                    for r in rec["rpcs"]
                )
                or "Không phát RPC"
            )
            report_lines.append(
                f"| {rec['step']} | {rec['temp']:.1f}°C | {lbl} | {len(rec['rpcs'])} | {detail} |"
            )

        report_lines.extend(
            [
                "",
                f"- RPC bật ở nhánh `Created` (>32°C): **{rpc_on_created}** (kỳ vọng: 1)",
                f"- RPC lặp khi duy trì >32°C (`Updated`): **{rpc_dup_gt32}** (kỳ vọng: 0)",
                f"- RPC trong vùng trễ (30 < T <= 32°C): **{rpc_hysteresis}** (kỳ vọng: 0)",
                f"- RPC tắt ở nhánh `Cleared` (<=30°C): **{rpc_off_cleared}** (kỳ vọng: 1)",
                f"- RPC bất thường ở ngưỡng bình thường: **{rpc_unexpected_normal}** (kỳ vọng: 0)",
                f"- **KẾT QUẢ KIỂM CHỨNG T12: {'PASS' if passed else 'FAIL'}**",
                "",
            ]
        )
        print("\n".join(report_lines))
        return 0 if passed else 1

    def _append_notification_trial(
        self,
        trigger_time_str: str,
        trigger_temp: float,
        received_time_str: str,
        latency_ms: float,
        channel: str,
        note: str,
    ) -> Path:
        csv_path = self.log_path.parent / "notification_5_trials.csv"
        write_header = not csv_path.exists()
        trial_num = 1
        if csv_path.exists():
            with csv_path.open("r", encoding="utf-8") as fh:
                rows = list(csv.reader(fh))
                trial_num = max(1, len(rows))
        with csv_path.open("a", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            if write_header:
                writer.writerow(
                    [
                        "trial",
                        "trigger_time",
                        "trigger_temp_c",
                        "received_time",
                        "latency_ms",
                        "channel",
                        "alarm_created",
                        "note",
                    ]
                )
            writer.writerow(
                [
                    trial_num,
                    trigger_time_str,
                    f"{trigger_temp:.1f}",
                    received_time_str,
                    f"{latency_ms:.1f}",
                    channel,
                    "true",
                    note,
                ]
            )
        return csv_path

    def run_interactive_scenario(self, interval: float) -> int:
        """Background telemetry loop + interactive CLI for T11/T12/T13 testing."""
        if self.dry_run:
            self.log("[DRY-RUN] Chế độ interactive không gửi mạng; chỉ xác nhận lệnh nội bộ.")

        def telemetry_worker() -> None:
            while not self.stop_event.is_set():
                self.publish_telemetry()
                if self.stop_event.wait(timeout=interval):
                    break

        worker = threading.Thread(target=telemetry_worker, daemon=True)
        worker.start()

        print(
            "\n--- Lệnh điều khiển Mock CoreIOT Gateway ---\n"
            "  temp <giá trị>  : Đặt nhiệt độ mới (vd: temp 33.5) và đẩy ngay lên CoreIOT\n"
            "  humi <giá trị>  : Đặt độ ẩm mới (vd: humi 68.0)\n"
            "  state on|off    : Giả lập đổi cooling_state cục bộ và đồng bộ lên CoreIOT\n"
            "  notif [nhiệt]   : Đẩy T>32°C & bấm giờ đo Notification T13 (lưu CSV)\n"
            "  stats           : Xem trạng thái hiện tại và lịch sử RPC nhận được\n"
            "  quit            : Thoát\n"
        )

        while not self.stop_event.is_set():
            try:
                raw_cmd = input().strip()
            except EOFError:
                break
            if not raw_cmd:
                continue
            parts = raw_cmd.split()
            verb = parts[0].lower()

            if verb in {"quit", "exit", "q"}:
                break
            if verb == "help":
                print("Lệnh hỗ trợ: temp <số>, humi <số>, state on|off, notif [nhiệt], stats, quit")
            elif verb == "temp" and len(parts) == 2:
                try:
                    val = float(parts[1])
                except ValueError:
                    print("[CẢNH BÁO] Giá trị nhiệt độ không hợp lệ.")
                    continue
                with self.state_lock:
                    self.temperature = val
                self.publish_telemetry()
            elif verb == "humi" and len(parts) == 2:
                try:
                    val = float(parts[1])
                except ValueError:
                    print("[CẢNH BÁO] Giá trị độ ẩm không hợp lệ.")
                    continue
                with self.state_lock:
                    self.humidity = val
                self.publish_telemetry()
            elif verb == "state" and len(parts) == 2 and parts[1].lower() in {"on", "off"}:
                new_state = parts[1].lower() == "on"
                with self.state_lock:
                    self.cooling_state = new_state
                self.publish_telemetry()
            elif verb == "notif":
                test_temp = 33.5
                if len(parts) == 2:
                    try:
                        test_temp = float(parts[1])
                    except ValueError:
                        print("[CẢNH BÁO] Nhiệt độ không hợp lệ.")
                        continue
                with self.state_lock:
                    self.temperature = test_temp
                trigger_time_str = now_str()
                t0 = time.perf_counter()
                self.publish_telemetry()
                ack = input(
                    f"[T13] Đã gửi T={test_temp:.1f}°C lúc {trigger_time_str}. "
                    "Nhấn ENTER ngay khi thấy Notification trên CoreIOT (hoặc gõ 'cancel'): "
                ).strip()
                if ack.lower() == "cancel":
                    print("[T13] Đã hủy lượt đo này.")
                    continue
                latency_ms = (time.perf_counter() - t0) * 1000.0
                received_time_str = now_str()
                csv_path = self._append_notification_trial(
                    trigger_time_str=trigger_time_str,
                    trigger_temp=test_temp,
                    received_time_str=received_time_str,
                    latency_ms=latency_ms,
                    channel="CoreIOT Web",
                    note="mock_gateway",
                )
                print(
                    f"[T13 ĐÃ GHI] Độ trễ Notification: {latency_ms:.1f} ms -> {csv_path}"
                )
            elif verb == "stats":
                with self.state_lock:
                    print(
                        f"[STATS] T={self.temperature:.2f}°C | H={self.humidity:.2f}% | "
                        f"cooling_state={self.cooling_state} | TX={self.tx_telemetry_count} | "
                        f"RPC_RX={len(self.rpc_history)}"
                    )
                    for idx, rec in enumerate(self.rpc_history, start=1):
                        print(
                            f"  #{idx} [{rec['timestamp']}] req_id={rec['request_id']} "
                            f"-> setCooling({rec['target_state']})"
                        )
            else:
                print(f"[CẢNH BÁO] Lệnh không hợp lệ: '{raw_cmd}'. Gõ 'help' để xem hướng dẫn.")
        return 0


def build_arg_parser() -> argparse.ArgumentParser:
    """Create CLI argument parser."""
    tests_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Gia lap CoreIOT MQTT Gateway kiem thu T11, T12, T13."
    )
    parser.add_argument("--host", type=str, default=None, help="CoreIOT MQTT host.")
    parser.add_argument("--port", type=int, default=None, help="CoreIOT MQTT port.")
    parser.add_argument("--token", type=str, default=None, help="CoreIOT Device Access Token.")
    parser.add_argument(
        "--env-file",
        type=Path,
        default=tests_dir / ".env",
        help="Đường dẫn file .env (mặc định tests/.env).",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Chu kỳ gửi telemetry giữa các bước (giây, mặc định 5.0).",
    )
    parser.add_argument(
        "--scenario",
        choices=["interactive", "rulechain"],
        default="interactive",
        help="Kịch bản chạy: interactive hoặc rulechain (test T12 11 mốc).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chạy mô phỏng cục bộ không cần MQTT broker / token.",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=tests_dir / "logs",
        help="Thư mục lưu file log và CSV.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for mock CoreIOT Gateway."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    env_vals = load_env_file(args.env_file)
    host = args.host or os.environ.get("COREIOT_HOST") or env_vals.get("COREIOT_HOST") or "app.coreiot.io"
    port_raw = (
        str(args.port)
        if args.port is not None
        else os.environ.get("COREIOT_PORT") or env_vals.get("COREIOT_PORT") or "1883"
    )
    port = int(port_raw)
    token = (
        args.token
        or os.environ.get("COREIOT_ACCESS_TOKEN")
        or env_vals.get("COREIOT_ACCESS_TOKEN")
    )

    ts_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = args.log_dir / f"{ts_tag}_mock_{args.scenario}.log"

    gw = MockCoreIOTGateway(
        host=host,
        port=port,
        token=token,
        dry_run=args.dry_run,
        log_path=log_path,
    )
    try:
        gw.connect()
        if args.scenario == "rulechain":
            return gw.run_rulechain_scenario(interval=args.interval)
        return gw.run_interactive_scenario(interval=args.interval)
    except KeyboardInterrupt:
        print("\n[INFO] Dừng Mock Gateway theo Ctrl+C.")
        return 0
    finally:
        gw.close()
        print(f"[ĐÃ LƯU LOG] {log_path}")


if __name__ == "__main__":
    raise SystemExit(main())
