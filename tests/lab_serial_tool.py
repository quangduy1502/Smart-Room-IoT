"""Cong cu ho tro test Serial, luu log goc va thong ke so lieu Chuong 4 cho Smart Room IoT.

Phu hop voi firmware Node A (Modbus + ESP-NOW) va Node B (ESP-NOW + SoftAP + USB Serial JSON):
- Mode node_b: Theo doi goi telemetry co seq (tinh ty le mat goi), gui lenh set_cooling
  (on / off / test10), loc event state_changed va khop ACK dung request_id (timeout 2000 ms).
- Mode node_a: Theo doi so lan doc Modbus OK/Loi (0xE2, 0x02...) va ty le gui ESP-NOW.
- Ho tro phan tich offline file .log da luu (--analyze) de xuat bang Markdown cho bao cao.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import serial
    from serial.tools import list_ports
except ImportError:  # pragma: no cover - handled gracefully at runtime
    serial = None
    list_ports = None

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_BAUD = 115200
RPC_TIMEOUT_SEC = 2.0

TS_PREFIX_RE = re.compile(
    r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?)\]\s*(.*)$"
)
RE_MODBUS_OK = re.compile(
    r"\[MODBUS\] OK #(\d+): Temp=([-+]?\d+(?:\.\d+)?) C, Humi=([-+]?\d+(?:\.\d+)?) %"
)
RE_MODBUS_ERR = re.compile(
    r"\[MODBUS\] Loi doc (nhiet do|do am): (0x[0-9A-Fa-f]+)"
)
RE_MOCK = re.compile(
    r"\[MOCK\] Temp=([-+]?\d+(?:\.\d+)?) C, Humi=([-+]?\d+(?:\.\d+)?) %"
)
RE_ESPNOW_TX = re.compile(r"\[ESP-NOW\] Gui (thanh cong|THAT BAI)")


def now_timestamp_str() -> str:
    """Return local timestamp formatted as YYYY-MM-DD HH:MM:SS.mmm."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def sanitize_label(label: str) -> str:
    """Sanitize test label for safe file naming."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", label.strip())
    return cleaned.strip("_") or "session"


def parse_log_line(raw_line: str) -> tuple[float | None, str]:
    """Strip optional '[YYYY-MM-DD HH:MM:SS.mmm] ' prefix and return (epoch_sec, payload)."""
    stripped = raw_line.rstrip("\r\n")
    match = TS_PREFIX_RE.match(stripped)
    if not match:
        return None, stripped
    ts_str, payload = match.group(1), match.group(2)
    try:
        dt = datetime.fromisoformat(ts_str)
        return dt.timestamp(), payload
    except ValueError:
        return None, payload


def format_numeric_summary(values: list[float], unit: str) -> str:
    """Return 'min / avg / max unit' or 'N/A' when empty."""
    if not values:
        return "N/A"
    v_min = min(values)
    v_avg = sum(values) / len(values)
    v_max = max(values)
    return f"{v_min:.2f} / {v_avg:.2f} / {v_max:.2f} {unit}"


@dataclass
class SeqSegment:
    """Contiguous sequence-number tracking segment for ESP-NOW telemetry."""

    first_seq: int
    max_seq: int
    last_seq: int
    seen_seqs: set[int] = field(default_factory=set)
    total_rx: int = 0


@dataclass
class PendingRpc:
    """Pending set_cooling command waiting for matching ACK by request_id."""

    request_id: int
    target_state: bool
    sent_ts: float
    done_event: threading.Event | None = None
    result: dict[str, Any] | None = None


class NodeBStats:
    """Tracks ESP-NOW packet loss (via seq), sensor stats, events, and RPC ACK latency."""

    def __init__(self) -> None:
        self.segments: list[SeqSegment] = []
        self.duplicate_count = 0
        self.out_of_order_count = 0
        self.reset_events = 0
        self.temps: list[float] = []
        self.humis: list[float] = []
        self.last_cooling_state: bool | None = None
        self.last_seq: int | None = None
        self.events: list[dict[str, Any]] = []
        self.pending_cmds: dict[int, PendingRpc] = {}
        self.rpc_records: list[dict[str, Any]] = []
        self.debug_lines = 0
        self.invalid_json_lines = 0
        self.target_alerted = False

    def reset(self) -> None:
        """Clear accumulated counters while preserving pending state cleanly."""
        self.segments.clear()
        self.duplicate_count = 0
        self.out_of_order_count = 0
        self.reset_events = 0
        self.temps.clear()
        self.humis.clear()
        self.last_seq = None
        self.events.clear()
        self.pending_cmds.clear()
        self.rpc_records.clear()
        self.debug_lines = 0
        self.invalid_json_lines = 0
        self.target_alerted = False

    def register_command(
        self,
        request_id: int,
        target_state: bool,
        sent_ts: float,
        done_event: threading.Event | None = None,
    ) -> PendingRpc:
        """Register an outgoing set_cooling command to match its future ACK."""
        pending = PendingRpc(
            request_id=request_id,
            target_state=target_state,
            sent_ts=sent_ts,
            done_event=done_event,
        )
        self.pending_cmds[request_id] = pending
        return pending

    def _record_seq(self, seq: int) -> None:
        if not self.segments:
            self.segments.append(SeqSegment(first_seq=seq, max_seq=seq, last_seq=seq))
        else:
            cur = self.segments[-1]
            is_reboot = seq < cur.last_seq and (
                seq in cur.seen_seqs or (cur.max_seq - seq) > 5 or seq == 1
            )
            if is_reboot:
                self.reset_events += 1
                self.segments.append(
                    SeqSegment(first_seq=seq, max_seq=seq, last_seq=seq)
                )

        cur = self.segments[-1]
        cur.total_rx += 1
        if seq in cur.seen_seqs:
            self.duplicate_count += 1
        else:
            if cur.seen_seqs and seq < cur.last_seq:
                self.out_of_order_count += 1
            cur.seen_seqs.add(seq)
            cur.first_seq = min(cur.first_seq, seq)
            cur.max_seq = max(cur.max_seq, seq)
            cur.last_seq = seq
        self.last_seq = seq

    def telemetry_metrics(self) -> dict[str, Any]:
        """Compute packet reception and loss metrics across all segments."""
        expected_span = sum(seg.max_seq - seg.first_seq + 1 for seg in self.segments)
        received_unique = sum(len(seg.seen_seqs) for seg in self.segments)
        total_rx = sum(seg.total_rx for seg in self.segments)
        lost_count = expected_span - received_unique
        loss_rate = (lost_count / expected_span * 100.0) if expected_span > 0 else 0.0

        missing_seqs: list[str] = []
        multi_seg = len(self.segments) > 1
        for idx, seg in enumerate(self.segments, start=1):
            for seq_num in range(seg.first_seq, seg.max_seq + 1):
                if seq_num not in seg.seen_seqs:
                    label = f"s{idx}:{seq_num}" if multi_seg else str(seq_num)
                    missing_seqs.append(label)

        return {
            "expected_span": expected_span,
            "received_unique": received_unique,
            "total_rx": total_rx,
            "lost_count": lost_count,
            "loss_rate": loss_rate,
            "missing_seqs": missing_seqs,
        }

    def sample_count(self) -> int:
        """Return number of unique telemetry packets received."""
        return sum(len(seg.seen_seqs) for seg in self.segments)

    def expire_timeouts(
        self, now_ts: float, timeout_sec: float = RPC_TIMEOUT_SEC
    ) -> list[dict[str, Any]]:
        """Expire any pending RPC commands exceeding timeout_sec."""
        expired_ids = [
            req_id
            for req_id, item in self.pending_cmds.items()
            if (now_ts - item.sent_ts) >= timeout_sec
        ]
        expired_records: list[dict[str, Any]] = []
        for req_id in expired_ids:
            item = self.pending_cmds.pop(req_id)
            rec = {
                "request_id": req_id,
                "target_state": item.target_state,
                "status": "TIMEOUT",
                "latency_ms": timeout_sec * 1000.0,
                "ok": False,
                "actual_state": None,
                "error": f"timeout >{int(timeout_sec * 1000)} ms",
            }
            self.rpc_records.append(rec)
            item.result = rec
            if item.done_event is not None:
                item.done_event.set()
            expired_records.append(rec)
        return expired_records

    def finalize_pending_offline(self) -> None:
        """Mark remaining pending commands at EOF as NO_ACK during offline analysis."""
        for req_id in list(self.pending_cmds.keys()):
            item = self.pending_cmds.pop(req_id)
            rec = {
                "request_id": req_id,
                "target_state": item.target_state,
                "status": "NO_ACK",
                "latency_ms": None,
                "ok": False,
                "actual_state": None,
                "error": "missing_ack_at_eof",
            }
            self.rpc_records.append(rec)

    def process_line(
        self, payload: str, event_ts: float | None = None
    ) -> tuple[str, str]:
        """Parse one Node B line and return (kind, formatted_console_message)."""
        if not payload:
            return "empty", ""

        if payload.startswith("[TX] "):
            tx_json_str = payload[5:].strip()
            try:
                tx_doc = json.loads(tx_json_str)
            except json.JSONDecodeError:
                return "tx_raw", payload
            if (
                isinstance(tx_doc, dict)
                and tx_doc.get("type") == "command"
                and tx_doc.get("cmd") == "set_cooling"
            ):
                req_id = tx_doc.get("request_id")
                state = tx_doc.get("state")
                if isinstance(req_id, int) and isinstance(state, bool):
                    ts = event_ts if event_ts is not None else time.perf_counter()
                    if req_id not in self.pending_cmds:
                        self.register_command(req_id, state, ts)
                    return "tx", (
                        f"[TX] set_cooling={str(state).lower()} (request_id={req_id})"
                    )
            return "tx_raw", payload

        if payload.startswith("[DEBUG]"):
            self.debug_lines += 1
            return "debug", payload

        if not payload.startswith("{"):
            self.invalid_json_lines += 1
            return "raw", payload

        try:
            doc = json.loads(payload)
        except json.JSONDecodeError:
            self.invalid_json_lines += 1
            return "raw", payload

        if not isinstance(doc, dict):
            self.invalid_json_lines += 1
            return "raw", payload

        msg_type = doc.get("type", "")
        if msg_type == "telemetry":
            seq = doc.get("seq")
            temp = doc.get("temperature")
            humi = doc.get("humidity")
            cooling = doc.get("cooling_state")

            if isinstance(seq, int) and not isinstance(seq, bool):
                self._record_seq(seq)
            if isinstance(temp, (int, float)) and not isinstance(temp, bool):
                self.temps.append(float(temp))
            if isinstance(humi, (int, float)) and not isinstance(humi, bool):
                self.humis.append(float(humi))
            if isinstance(cooling, bool):
                self.last_cooling_state = cooling

            m = self.telemetry_metrics()
            t_str = f"{float(temp):.2f}°C" if isinstance(temp, (int, float)) else "N/A"
            h_str = f"{float(humi):.2f}%" if isinstance(humi, (int, float)) else "N/A"
            c_str = "ON" if cooling is True else ("OFF" if cooling is False else "?")
            return "telemetry", (
                f"[TELEMETRY] seq={seq} | T={t_str} H={h_str} | cooling={c_str} | "
                f"RX={m['received_unique']}/{m['expected_span']} "
                f"(lost {m['lost_count']}, {m['loss_rate']:.2f}%)"
            )

        if msg_type == "event":
            ev_name = doc.get("event", "")
            cooling = doc.get("cooling_state")
            if isinstance(cooling, bool):
                self.last_cooling_state = cooling
            self.events.append({"event": ev_name, "cooling_state": cooling})
            c_str = "ON" if cooling is True else ("OFF" if cooling is False else str(cooling))
            return "event", f"[EVENT] {ev_name} -> cooling_state={c_str}"

        if msg_type == "ack":
            req_id = doc.get("request_id")
            ok = bool(doc.get("ok"))
            actual_state = doc.get("cooling_state")
            if isinstance(actual_state, bool):
                self.last_cooling_state = actual_state
            err_msg = doc.get("error")

            if isinstance(req_id, int) and not isinstance(req_id, bool):
                pending = self.pending_cmds.pop(req_id, None)
            else:
                pending = None

            if pending is not None:
                latency_ms: float | None = None
                if event_ts is not None:
                    latency_ms = max(0.0, (event_ts - pending.sent_ts) * 1000.0)
                if not ok:
                    status = "ERROR"
                elif actual_state == pending.target_state:
                    status = "OK"
                else:
                    status = "MISMATCH"
                rec = {
                    "request_id": req_id,
                    "target_state": pending.target_state,
                    "status": status,
                    "latency_ms": latency_ms,
                    "ok": ok,
                    "actual_state": actual_state,
                    "error": err_msg,
                }
                self.rpc_records.append(rec)
                pending.result = rec
                if pending.done_event is not None:
                    pending.done_event.set()
                lat_str = f"{latency_ms:.1f} ms" if latency_ms is not None else "N/A"
                return "ack", (
                    f"[ACK] request_id={req_id} | status={status} | "
                    f"cooling_state={actual_state} | latency={lat_str}"
                )

            return "ack", (
                f"[ACK] request_id={req_id} | ok={ok} | cooling_state={actual_state}"
                + (f" | error={err_msg}" if err_msg else "")
            )

        return "json", payload

    def render_markdown_summary(self, label: str = "node_b") -> str:
        """Render Chapter 4 Markdown summary report for Node B."""
        m = self.telemetry_metrics()
        missing_preview = ", ".join(m["missing_seqs"][:20])
        if len(m["missing_seqs"]) > 20:
            missing_preview += f", ... (+{len(m['missing_seqs']) - 20} gói)"
        if not missing_preview:
            missing_preview = "Không có"

        ok_rpcs = [r for r in self.rpc_records if r["status"] == "OK"]
        latencies = [
            r["latency_ms"]
            for r in ok_rpcs
            if isinstance(r.get("latency_ms"), (int, float))
        ]
        total_rpc = len(self.rpc_records)
        rpc_success_rate = (len(ok_rpcs) / total_rpc * 100.0) if total_rpc > 0 else 0.0
        timeout_count = sum(1 for r in self.rpc_records if r["status"] == "TIMEOUT")

        lines = [
            f"### Tổng kết đo đạc Node B (`{label}`)",
            "",
            "#### 1. Thống kê truyền nhận ESP-NOW & Môi trường",
            "",
            "| Chỉ số | Giá trị đo được |",
            "| :--- | :--- |",
            f"| Dải seq dự kiến (`expected_span`) | {m['expected_span']} gói |",
            f"| Số gói duy nhất nhận được (`received_unique`) | {m['received_unique']} gói (tổng RX: {m['total_rx']}) |",
            f"| Số gói bị mất (`lost_count`) | {m['lost_count']} gói |",
            f"| Tỷ lệ mất gói (`loss_rate`) | {m['loss_rate']:.2f}% |",
            f"| Các `seq` bị mất | {missing_preview} |",
            f"| Gói trùng / sai thứ tự / reboot Node A | {self.duplicate_count} / {self.out_of_order_count} / {self.reset_events} |",
            f"| Nhiệt độ (Min / Avg / Max) | {format_numeric_summary(self.temps, '°C')} |",
            f"| Độ ẩm (Min / Avg / Max) | {format_numeric_summary(self.humis, '%')} |",
            f"| Số sự kiện `state_changed` ghi nhận | {len(self.events)} |",
            "",
            "#### 2. Thống kê điều khiển `set_cooling` & Phản hồi ACK",
            "",
            "| Chỉ số | Giá trị đo được |",
            "| :--- | :--- |",
            f"| Tổng số lệnh đã gửi & kết thúc | {total_rpc} (OK: {len(ok_rpcs)}, Timeout: {timeout_count}) |",
            f"| Tỷ lệ ACK thành công | {rpc_success_rate:.2f}% |",
            f"| Độ trễ ACK (Min / Avg / Max) | {format_numeric_summary(latencies, 'ms')} |",
        ]

        if self.rpc_records:
            lines.extend(
                [
                    "",
                    "| Lần | request_id | Mục tiêu | Kết quả | Độ trễ (ms) |",
                    "| :---: | :---: | :---: | :---: | :---: |",
                ]
            )
            for idx, r in enumerate(self.rpc_records, start=1):
                lat = (
                    f"{r['latency_ms']:.1f}"
                    if isinstance(r.get("latency_ms"), (int, float))
                    else "N/A"
                )
                target = "ON" if r["target_state"] else "OFF"
                lines.append(
                    f"| {idx} | {r['request_id']} | {target} | {r['status']} | {lat} |"
                )

        return "\n".join(lines)


class NodeAStats:
    """Tracks Modbus RS485 read success/errors and ESP-NOW TX results on Node A."""

    def __init__(self) -> None:
        self.modbus_ok_count = 0
        self.modbus_err_count = 0
        self.mock_count = 0
        self.error_codes: Counter[str] = Counter()
        self.error_sources: Counter[str] = Counter()
        self.temps: list[float] = []
        self.humis: list[float] = []
        self.espnow_ok_count = 0
        self.espnow_fail_count = 0
        self.target_alerted = False

    def reset(self) -> None:
        """Reset all Node A measurement counters."""
        self.modbus_ok_count = 0
        self.modbus_err_count = 0
        self.mock_count = 0
        self.error_codes.clear()
        self.error_sources.clear()
        self.temps.clear()
        self.humis.clear()
        self.espnow_ok_count = 0
        self.espnow_fail_count = 0
        self.target_alerted = False

    def sample_count(self) -> int:
        """Return total real Modbus read attempts."""
        return self.modbus_ok_count + self.modbus_err_count

    def process_line(
        self, payload: str, event_ts: float | None = None
    ) -> tuple[str, str]:
        """Parse one Node A Serial line and return (kind, formatted_console_message)."""
        del event_ts
        if not payload:
            return "empty", ""

        m_ok = RE_MODBUS_OK.search(payload)
        if m_ok:
            self.modbus_ok_count += 1
            temp = float(m_ok.group(2))
            humi = float(m_ok.group(3))
            self.temps.append(temp)
            self.humis.append(humi)
            total = self.sample_count()
            rate = (self.modbus_ok_count / total * 100.0) if total > 0 else 0.0
            return "modbus_ok", (
                f"[MODBUS OK] #{total}: T={temp:.2f}°C H={humi:.2f}% | "
                f"OK={self.modbus_ok_count}/{total} ({rate:.1f}%)"
            )

        m_err = RE_MODBUS_ERR.search(payload)
        if m_err:
            source = m_err.group(1)
            code = m_err.group(2).upper().replace("0X", "0x")
            self.modbus_err_count += 1
            self.error_codes[code] += 1
            self.error_sources[source] += 1
            total = self.sample_count()
            return "modbus_err", (
                f"[MODBUS ERR] Lỗi đọc {source}: {code} | "
                f"OK={self.modbus_ok_count}, ERR={self.modbus_err_count} (tổng {total})"
            )

        m_mock = RE_MOCK.search(payload)
        if m_mock:
            self.mock_count += 1
            return "mock", payload

        m_tx = RE_ESPNOW_TX.search(payload)
        if m_tx:
            if m_tx.group(1) == "thanh cong":
                self.espnow_ok_count += 1
            else:
                self.espnow_fail_count += 1
            return "espnow_tx", payload

        return "debug", payload

    def render_markdown_summary(self, label: str = "node_a") -> str:
        """Render Chapter 4 Markdown summary report for Node A."""
        total_modbus = self.sample_count()
        modbus_rate = (
            (self.modbus_ok_count / total_modbus * 100.0) if total_modbus > 0 else 0.0
        )
        total_espnow = self.espnow_ok_count + self.espnow_fail_count
        espnow_rate = (
            (self.espnow_ok_count / total_espnow * 100.0) if total_espnow > 0 else 0.0
        )
        err_summary = (
            ", ".join(f"{code}: {cnt}" for code, cnt in sorted(self.error_codes.items()))
            or "Không có"
        )

        lines = [
            f"### Tổng kết đo đạc Node A (`{label}`)",
            "",
            "| Chỉ số | Giá trị đo được |",
            "| :--- | :--- |",
            f"| Tổng số lần đọc Modbus thật | {total_modbus} lần (OK: {self.modbus_ok_count}, Lỗi: {self.modbus_err_count}) |",
            f"| Tỷ lệ đọc Modbus thành công | {modbus_rate:.2f}% |",
            f"| Phân loại mã lỗi Modbus | {err_summary} |",
            f"| Nhiệt độ đo được (Min / Avg / Max) | {format_numeric_summary(self.temps, '°C')} |",
            f"| Độ ẩm đo được (Min / Avg / Max) | {format_numeric_summary(self.humis, '%')} |",
            f"| Số lần gửi ESP-NOW (OK / FAIL) | {self.espnow_ok_count} / {self.espnow_fail_count} ({espnow_rate:.2f}% OK) |",
        ]
        if self.mock_count > 0:
            lines.append(
                f"| Cảnh báo chế độ giả lập (`USE_MOCK_SENSOR`) | Phát hiện {self.mock_count} dòng `[MOCK]` — không dùng cho T02 |"
            )
        return "\n".join(lines)


def list_serial_ports() -> list[Any]:
    """Return available COM ports using pyserial."""
    if list_ports is None:
        raise RuntimeError("Chưa cài pyserial. Chạy: pip install -r tests/requirements.txt")
    return sorted(list_ports.comports(), key=lambda p: p.device)


def print_serial_ports() -> list[Any]:
    """Print available COM ports to console and return the list."""
    ports = list_serial_ports()
    if not ports:
        print("[INFO] Không tìm thấy cổng COM nào. Kiểm tra cáp USB-C truyền dữ liệu hoặc driver.")
        return []
    print("Danh sách cổng COM hiện có:")
    for idx, p in enumerate(ports, start=1):
        print(f"  [{idx}] {p.device} - {p.description} ({p.hwid})")
    return ports


def select_port_interactive() -> str:
    """List COM ports and let user pick one interactively."""
    ports = print_serial_ports()
    if not ports:
        sys.exit(1)
    while True:
        choice = input("Chọn số thứ tự cổng COM (hoặc nhập tên cổng, vd COM5, 'q' để thoát): ").strip()
        if choice.lower() in {"q", "quit", "exit"}:
            sys.exit(0)
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(ports):
                return ports[idx].device
        else:
            for p in ports:
                if p.device.upper() == choice.upper():
                    return p.device
        print("[CẢNH BÁO] Lựa chọn không hợp lệ, vui lòng thử lại.")


def analyze_log_file(log_path: Path, mode: str) -> str:
    """Analyze a saved log file offline and return its Markdown summary."""
    if not log_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file log: {log_path}")

    stats: NodeBStats | NodeAStats = NodeBStats() if mode == "node_b" else NodeAStats()
    last_ts: float | None = None

    with log_path.open("r", encoding="utf-8", errors="replace") as fh:
        for raw_line in fh:
            parsed_ts, payload = parse_log_line(raw_line)
            if parsed_ts is not None:
                last_ts = parsed_ts
                if isinstance(stats, NodeBStats):
                    stats.expire_timeouts(parsed_ts)
            stats.process_line(payload, event_ts=parsed_ts)

    if isinstance(stats, NodeBStats):
        if last_ts is not None:
            stats.expire_timeouts(last_ts)
        stats.finalize_pending_offline()

    return stats.render_markdown_summary(label=log_path.stem)


def print_help(mode: str) -> None:
    """Print interactive commands for the active mode."""
    print("\n--- Lệnh điều khiển nhanh ---")
    if mode == "node_b":
        print("  on      : Gửi lệnh bật LED làm mát (set_cooling=true)")
        print("  off     : Gửi lệnh tắt LED làm mát (set_cooling=false)")
        print("  test10  : Chạy tự động 10 lần bật/tắt xen kẽ và thống kê độ trễ ACK")
    print("  stats   : Xem bảng thống kê hiện tại")
    print("  reset   : Xóa bộ đếm hiện tại để bắt đầu lượt đo mới")
    print("  help    : Xem lại hướng dẫn lệnh")
    print("  quit    : Lưu báo cáo tổng hợp và thoát\n")


class LiveSerialSession:
    """Manages live Serial I/O, logging, stats tracking, and interactive commands."""

    def __init__(
        self,
        port: str,
        baud: int,
        mode: str,
        label: str,
        log_dir: Path,
        target: int | None,
        auto_exit: bool,
    ) -> None:
        self.port = port
        self.baud = baud
        self.mode = mode
        self.label = sanitize_label(label)
        self.log_dir = log_dir
        self.target = target
        self.auto_exit = auto_exit

        self.stats: NodeBStats | NodeAStats = (
            NodeBStats() if mode == "node_b" else NodeAStats()
        )
        self.state_lock = threading.Lock()
        self.file_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.next_req_id = 1

        ts_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.log_dir / f"{ts_tag}_{self.label}.log"
        self.summary_path = self.log_dir / f"{ts_tag}_{self.label}_summary.md"
        self.log_fp = self.log_path.open("w", encoding="utf-8", buffering=1)
        self.ser: Any = None

    def write_log_line(self, line: str) -> None:
        """Write one timestamped raw line to the log file safely."""
        with self.file_lock:
            self.log_fp.write(f"[{now_timestamp_str()}] {line}\n")

    def send_cooling_command(
        self, target_state: bool, wait_ack: bool = False
    ) -> dict[str, Any] | None:
        """Send JSON set_cooling command to Node B and optionally wait for matching ACK."""
        if not isinstance(self.stats, NodeBStats):
            print("[CẢNH BÁO] Lệnh điều khiển chỉ dùng ở chế độ --mode node_b.")
            return None

        done_ev = threading.Event() if wait_ack else None
        with self.state_lock:
            req_id = self.next_req_id
            self.next_req_id += 1
            payload_str = json.dumps(
                {
                    "type": "command",
                    "cmd": "set_cooling",
                    "state": target_state,
                    "request_id": req_id,
                },
                separators=(",", ":"),
            )
            pending = self.stats.register_command(
                request_id=req_id,
                target_state=target_state,
                sent_ts=time.perf_counter(),
                done_event=done_ev,
            )

        self.write_log_line(f"[TX] {payload_str}")
        self.ser.write((payload_str + "\n").encode("utf-8"))
        self.ser.flush()
        print(
            f"[TX] Đã gửi set_cooling={str(target_state).lower()} (request_id={req_id})"
        )

        if wait_ack and done_ev is not None:
            done_ev.wait(timeout=RPC_TIMEOUT_SEC + 0.5)
            return pending.result
        return None

    def run_test10(self) -> None:
        """Send 10 alternating ON/OFF commands, wait for each ACK, and print latency stats."""
        if not isinstance(self.stats, NodeBStats):
            return

        with self.state_lock:
            cur = self.stats.last_cooling_state
        next_state = (not cur) if isinstance(cur, bool) else True

        print("\n=== BẮT ĐẦU TEST 10 LẦN RPC (on/off xen kẽ, chờ ACK từng lần) ===")
        results: list[dict[str, Any]] = []
        for idx in range(1, 11):
            if self.stop_event.is_set():
                break
            res = self.send_cooling_command(next_state, wait_ack=True)
            if res is not None:
                results.append(res)
                lat = (
                    f"{res['latency_ms']:.1f} ms"
                    if isinstance(res.get("latency_ms"), (int, float))
                    else "N/A"
                )
                print(
                    f"  Lần {idx}/10: target={'ON' if next_state else 'OFF'} -> "
                    f"{res['status']} ({lat})"
                )
            else:
                print(f"  Lần {idx}/10: Không nhận được kết quả ACK.")
            next_state = not next_state
            time.sleep(0.5)

        ok_list = [r for r in results if r["status"] == "OK"]
        lats = [
            r["latency_ms"]
            for r in ok_list
            if isinstance(r.get("latency_ms"), (int, float))
        ]
        print("\n=== KẾT QUẢ TEST 10 LẦN RPC ===")
        print(f"  Thành công: {len(ok_list)}/{len(results)}")
        print(f"  Độ trễ ACK (Min / Avg / Max): {format_numeric_summary(lats, 'ms')}\n")

    def _reader_loop(self) -> None:
        """Background serial reader thread: logs lines, updates stats, checks timeouts."""
        while not self.stop_event.is_set():
            try:
                raw_bytes = self.ser.readline()
            except Exception as exc:
                if not self.stop_event.is_set():
                    print(f"\n[LỖI SERIAL] Mất kết nối cổng {self.port}: {exc}")
                    self.stop_event.set()
                break

            now_perf = time.perf_counter()

            with self.state_lock:
                if isinstance(self.stats, NodeBStats):
                    expired = self.stats.expire_timeouts(now_perf)
                else:
                    expired = []
            for rec in expired:
                print(
                    f"[RPC TIMEOUT] request_id={rec['request_id']} "
                    f"(không có ACK sau {int(RPC_TIMEOUT_SEC * 1000)} ms)"
                )

            if not raw_bytes:
                continue

            raw_line = raw_bytes.decode("utf-8", errors="replace").rstrip("\r\n")
            if not raw_line:
                continue

            self.write_log_line(raw_line)

            target_hit = False
            with self.state_lock:
                kind, msg = self.stats.process_line(raw_line, event_ts=now_perf)
                if (
                    self.target is not None
                    and not self.stats.target_alerted
                    and self.stats.sample_count() >= self.target
                ):
                    self.stats.target_alerted = True
                    target_hit = True
                    summary_snapshot = self.stats.render_markdown_summary(self.label)

            if msg:
                print(msg)

            if target_hit:
                print("\n" + "=" * 64)
                print(f"[ĐẠT MỤC TIÊU] Đã thu đủ {self.target} mẫu/gói cho '{self.label}'!")
                print("=" * 64)
                print(summary_snapshot)
                print("=" * 64 + "\n")
                if self.auto_exit:
                    self.stop_event.set()
                    break

    def run(self) -> None:
        """Open Serial port, start reader thread, process commands, save summary on exit."""
        if serial is None:
            raise RuntimeError("Chưa cài pyserial. Chạy: pip install -r tests/requirements.txt")

        print(f"Đang mở {self.port} @ {self.baud} baud (mode={self.mode}, label={self.label})...")
        print(f"File log gốc: {self.log_path}")

        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=0.1)
            reader = threading.Thread(target=self._reader_loop, daemon=True)
            reader.start()
            print_help(self.mode)

            if self.auto_exit:
                while not self.stop_event.is_set():
                    time.sleep(0.2)
            else:
                while not self.stop_event.is_set():
                    try:
                        cmd = input().strip().lower()
                    except EOFError:
                        break
                    if self.stop_event.is_set():
                        break
                    if not cmd:
                        continue
                    if cmd in {"quit", "exit", "q"}:
                        break
                    if cmd == "help":
                        print_help(self.mode)
                    elif cmd == "stats":
                        with self.state_lock:
                            print("\n" + self.stats.render_markdown_summary(self.label) + "\n")
                    elif cmd == "reset":
                        with self.state_lock:
                            self.stats.reset()
                        print("[INFO] Đã đặt lại bộ đếm thống kê.")
                    elif cmd == "on" and self.mode == "node_b":
                        self.send_cooling_command(True, wait_ack=False)
                    elif cmd == "off" and self.mode == "node_b":
                        self.send_cooling_command(False, wait_ack=False)
                    elif cmd == "test10" and self.mode == "node_b":
                        self.run_test10()
                    else:
                        print(f"[CẢNH BÁO] Lệnh không hợp lệ: '{cmd}'. Gõ 'help' để xem lệnh.")
        except KeyboardInterrupt:
            print("\n[INFO] Dừng phiên đo theo Ctrl+C...")
        finally:
            self.stop_event.set()
            if self.ser is not None and getattr(self.ser, "is_open", False):
                self.ser.close()

            with self.state_lock:
                if isinstance(self.stats, NodeBStats):
                    self.stats.expire_timeouts(time.perf_counter())
                final_summary = self.stats.render_markdown_summary(self.label)

            self.summary_path.write_text(final_summary + "\n", encoding="utf-8")
            with self.file_lock:
                self.log_fp.close()

            print("\n" + final_summary)
            print(f"\n[ĐÃ LƯU] Log gốc : {self.log_path}")
            print(f"[ĐÃ LƯU] Thống kê: {self.summary_path}")


def build_arg_parser() -> argparse.ArgumentParser:
    """Create CLI argument parser."""
    default_log_dir = Path(__file__).resolve().parent / "logs"
    parser = argparse.ArgumentParser(
        description="Cong cu test Serial & thong ke Chuong 4 cho Smart Room IoT (Node A / Node B)."
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Liệt kê các cổng COM hiện có rồi thoát.",
    )
    parser.add_argument(
        "--port",
        type=str,
        default=None,
        help="Tên cổng COM (vd COM5). Bỏ trống để chọn tương tác.",
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=DEFAULT_BAUD,
        help=f"Tốc độ Serial baud (mặc định {DEFAULT_BAUD}).",
    )
    parser.add_argument(
        "--mode",
        choices=["node_b", "node_a"],
        default="node_b",
        help="Chế độ đọc log: node_b (mặc định) hoặc node_a.",
    )
    parser.add_argument(
        "--target",
        type=int,
        default=None,
        help="Số gói/mẫu mục tiêu (vd 100 cho Node B ESP-NOW, 50 cho Node A Modbus).",
    )
    parser.add_argument(
        "--auto-exit",
        action="store_true",
        help="Tự động lưu summary và thoát ngay khi đạt --target.",
    )
    parser.add_argument(
        "--label",
        type=str,
        default=None,
        help="Nhãn bài test dùng cho tên file log (vd espnow_1m, modbus_50).",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=default_log_dir,
        help=f"Thư mục lưu file log và summary (mặc định: {default_log_dir}).",
    )
    parser.add_argument(
        "--analyze",
        type=Path,
        default=None,
        help="Phân tích offline 1 file .log đã lưu và in bảng Markdown Chương 4.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for CLI."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.list:
        print_serial_ports()
        return 0

    if args.analyze is not None:
        summary = analyze_log_file(args.analyze, args.mode)
        print(summary)
        return 0

    port = args.port or select_port_interactive()
    label = args.label or args.mode
    session = LiveSerialSession(
        port=port,
        baud=args.baud,
        mode=args.mode,
        label=label,
        log_dir=args.log_dir,
        target=args.target,
        auto_exit=args.auto_exit,
    )
    session.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
