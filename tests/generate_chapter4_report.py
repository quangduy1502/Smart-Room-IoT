"""Tong hop so lieu do dac thuc nghiem phuc vu Chuong 4 Bao cao BTL IoT.

Tai su dung parser tu lab_serial_tool.py de phan tich log Modbus (50 lan),
ESP-NOW (100 goi o 1m/5m), cung CSV/log do do tre RPC (10 lan) va Notification (5 lan).
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from lab_serial_tool import (  # noqa: E402
    NodeAStats,
    NodeBStats,
    format_numeric_summary,
    parse_log_line,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def parse_bool_cell(value: str | None) -> bool | None:
    """Parse flexible CSV boolean representation."""
    if value is None:
        return None
    norm = value.strip().lower()
    if norm in {"true", "1", "yes", "ok", "on"}:
        return True
    if norm in {"false", "0", "no", "fail", "off"}:
        return False
    return None


def parse_float_cell(value: str | None) -> float | None:
    """Parse float cell safely, returning None on blank/invalid values."""
    if value is None or not value.strip():
        return None
    try:
        return float(value.strip())
    except ValueError:
        return None


def analyze_modbus_log(log_path: Path) -> NodeAStats:
    """Parse Node A serial log into NodeAStats."""
    if not log_path.exists():
        raise FileNotFoundError(f"Không tìm thấy log Modbus: {log_path}")
    stats = NodeAStats()
    with log_path.open("r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            parsed_ts, payload = parse_log_line(raw)
            stats.process_line(payload, event_ts=parsed_ts)
    return stats


def analyze_node_b_log(log_path: Path) -> NodeBStats:
    """Parse Node B serial log into NodeBStats."""
    if not log_path.exists():
        raise FileNotFoundError(f"Không tìm thấy log Node B: {log_path}")
    stats = NodeBStats()
    last_ts: float | None = None
    with log_path.open("r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            parsed_ts, payload = parse_log_line(raw)
            if parsed_ts is not None:
                last_ts = parsed_ts
                stats.expire_timeouts(parsed_ts)
            stats.process_line(payload, event_ts=parsed_ts)
    if last_ts is not None:
        stats.expire_timeouts(last_ts)
    stats.finalize_pending_offline()
    return stats


def render_modbus_section(modbus_log: Path | None) -> list[str]:
    """Render Section 1: Modbus RS485 measurement table."""
    lines = ["## 1. Kết quả đo độ ổn định đọc cảm biến Modbus RS485 (T02)", ""]
    if modbus_log is None:
        lines.append("> *Chưa có dữ liệu đo thực tế (truyền `--modbus-log` để tổng hợp).*")
        lines.append("")
        return lines

    st = analyze_modbus_log(modbus_log)
    total = st.sample_count()
    rate = (st.modbus_ok_count / total * 100.0) if total > 0 else 0.0
    err_detail = (
        ", ".join(f"{code}: {cnt}" for code, cnt in sorted(st.error_codes.items()))
        or "Không có"
    )
    lines.extend(
        [
            f"- Nguồn log: `{modbus_log.name}`",
            "",
            "| Chỉ số | Giá trị đo được |",
            "| :--- | :--- |",
            f"| Tổng số lần đọc Modbus thật | {total} |",
            f"| Số lần thành công / thất bại | {st.modbus_ok_count} / {st.modbus_err_count} |",
            f"| Tỷ lệ đọc thành công | {rate:.2f}% |",
            f"| Phân loại mã lỗi (timeout `0xE2`, địa chỉ `0x02`, ...) | {err_detail} |",
            f"| Nhiệt độ (Min / Avg / Max) | {format_numeric_summary(st.temps, '°C')} |",
            f"| Độ ẩm (Min / Avg / Max) | {format_numeric_summary(st.humis, '%')} |",
            "",
        ]
    )
    if st.mock_count > 0:
        lines.append(
            f"> **Cảnh báo:** Log chứa {st.mock_count} dòng `[MOCK]` — không đủ điều kiện nghiệm thu T02."
        )
        lines.append("")
    return lines


def render_espnow_section(
    log_1m: Path | None, log_5m: Path | None
) -> list[str]:
    """Render Section 2: ESP-NOW packet loss comparison at 1m and 5m."""
    lines = ["## 2. Kết quả đo truyền thông không dây ESP-NOW khi bật SoftAP (T06)", ""]
    if log_1m is None and log_5m is None:
        lines.append(
            "> *Chưa có dữ liệu đo thực tế (truyền `--espnow-1m-log` / `--espnow-5m-log` để tổng hợp).* "
        )
        lines.append("")
        return lines

    rows: list[tuple[str, dict[str, Any], NodeBStats]] = []
    if log_1m is not None:
        st1 = analyze_node_b_log(log_1m)
        rows.append(("1m (có điện thoại kết nối AP)", st1.telemetry_metrics(), st1))
    if log_5m is not None:
        st5 = analyze_node_b_log(log_5m)
        rows.append(("5m (có điện thoại kết nối AP)", st5.telemetry_metrics(), st5))

    lines.extend(
        [
            "| Khoảng cách / Điều kiện | Gói dự kiến (`seq`) | Gói nhận duy nhất | Gói mất | Tỷ lệ mất gói | Trùng / Lệch thứ tự |",
            "| :--- | :---: | :---: | :---: | :---: | :---: |",
        ]
    )
    for label, m, st in rows:
        lines.append(
            f"| {label} | {m['expected_span']} | {m['received_unique']} | "
            f"{m['lost_count']} | {m['loss_rate']:.2f}% | "
            f"{st.duplicate_count} / {st.out_of_order_count} |"
        )
    lines.append("")
    return lines


def load_rpc_csv(csv_path: Path) -> list[dict[str, Any]]:
    """Read RPC trial records from CSV file matching rpc_10_trials.template.csv."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Không tìm thấy CSV RPC: {csv_path}")
    records: list[dict[str, Any]] = []
    with csv_path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            records.append(
                {
                    "trial": row.get("trial", "").strip(),
                    "source": row.get("source", "").strip() or "CoreIOT/Gateway",
                    "request_id": row.get("request_id", "").strip(),
                    "target_state": row.get("target_state", "").strip(),
                    "ack_ok": parse_bool_cell(row.get("ack_ok")),
                    "led_verified": parse_bool_cell(row.get("led_verified")),
                    "latency_ms": parse_float_cell(row.get("latency_ms")),
                }
            )
    return records


def render_rpc_section(
    rpc_csv: Path | None, rpc_log: Path | None
) -> list[str]:
    """Render Section 3: Two-way RPC latency and reliability table."""
    lines = ["## 3. Kết quả đo điều khiển hai chiều RPC `setCooling` (T08 & T11)", ""]
    if rpc_csv is None and rpc_log is None:
        lines.append(
            "> *Chưa có dữ liệu đo thực tế (truyền `--rpc-csv` hoặc `--rpc-log` để tổng hợp).* "
        )
        lines.append("")
        return lines

    records: list[dict[str, Any]] = []
    source_desc: list[str] = []
    if rpc_csv is not None:
        records.extend(load_rpc_csv(rpc_csv))
        source_desc.append(rpc_csv.name)
    if rpc_log is not None:
        st = analyze_node_b_log(rpc_log)
        for idx, rec in enumerate(st.rpc_records, start=len(records) + 1):
            records.append(
                {
                    "trial": str(idx),
                    "source": "Serial/Gateway",
                    "request_id": str(rec["request_id"]),
                    "target_state": "ON" if rec["target_state"] else "OFF",
                    "ack_ok": rec["status"] == "OK",
                    "led_verified": rec["status"] == "OK",
                    "latency_ms": rec["latency_ms"],
                }
            )
        source_desc.append(rpc_log.name)

    if not records:
        lines.append("> *Tệp đầu vào chưa có lượt đo RPC nào.*")
        lines.append("")
        return lines

    ok_count = sum(1 for r in records if r["ack_ok"] is True)
    led_count = sum(1 for r in records if r["led_verified"] is True)
    latencies = [
        r["latency_ms"]
        for r in records
        if r["ack_ok"] is True and isinstance(r["latency_ms"], float)
    ]
    total = len(records)
    lines.extend(
        [
            f"- Nguồn dữ liệu: `{', '.join(source_desc)}`",
            "",
            "| Chỉ số | Giá trị đo được |",
            "| :--- | :--- |",
            f"| Tổng số lượt gửi lệnh RPC | {total} |",
            f"| Số lượt ACK thành công (`ok=true`) | {ok_count}/{total} ({ok_count / total * 100.0:.2f}%) |",
            f"| Số lượt LED đổi trạng thái đúng thực tế | {led_count}/{total} ({led_count / total * 100.0:.2f}%) |",
            f"| Độ trễ phản hồi ACK (Min / Avg / Max) | {format_numeric_summary(latencies, 'ms')} |",
            "",
        ]
    )
    return lines


def render_notification_section(notif_csv: Path | None) -> list[str]:
    """Render Section 4: CoreIOT Notification delivery latency table."""
    lines = ["## 4. Kết quả đo cảnh báo vượt ngưỡng Notification (T12 & T13)", ""]
    if notif_csv is None:
        lines.append("> *Chưa có dữ liệu đo thực tế (truyền `--notif-csv` để tổng hợp).*")
        lines.append("")
        return lines
    if not notif_csv.exists():
        raise FileNotFoundError(f"Không tìm thấy CSV Notification: {notif_csv}")

    rows: list[dict[str, Any]] = []
    with notif_csv.open("r", encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(
                {
                    "trial": row.get("trial", "").strip(),
                    "trigger_temp_c": parse_float_cell(row.get("trigger_temp_c")),
                    "latency_ms": parse_float_cell(row.get("latency_ms")),
                    "channel": row.get("channel", "").strip() or "CoreIOT Web",
                    "alarm_created": parse_bool_cell(row.get("alarm_created")),
                }
            )

    if not rows:
        lines.append("> *Tệp CSV Notification chưa có dữ liệu đo.*")
        lines.append("")
        return lines

    alarm_ok = sum(1 for r in rows if r["alarm_created"] is True)
    lats = [r["latency_ms"] for r in rows if isinstance(r["latency_ms"], float)]
    total = len(rows)
    lines.extend(
        [
            f"- Nguồn dữ liệu: `{notif_csv.name}`",
            "",
            "| Chỉ số | Giá trị đo được |",
            "| :--- | :--- |",
            f"| Tổng số lần thử vượt ngưỡng (> 32°C) | {total} |",
            f"| Số lần sinh Alarm & nhận Notification | {alarm_ok}/{total} ({alarm_ok / total * 100.0:.2f}%) |",
            f"| Độ trễ nhận Notification (Min / Avg / Max) | {format_numeric_summary(lats, 'ms')} |",
            "",
        ]
    )
    return lines


def generate_report(args: argparse.Namespace) -> str:
    """Assemble full Chapter 4 Markdown report from available inputs."""
    sections: list[str] = [
        "# Tổng Hợp Số Liệu Thực Nghiệm Chương 4 – Smart Room IoT",
        "",
        "*Báo cáo được tổng hợp tự động từ log gốc và bảng ghi nhận đo đạc thực tế.*",
        "",
    ]
    sections.extend(render_modbus_section(args.modbus_log))
    sections.extend(render_espnow_section(args.espnow_1m_log, args.espnow_5m_log))
    sections.extend(render_rpc_section(args.rpc_csv, args.rpc_log))
    sections.extend(render_notification_section(args.notif_csv))
    return "\n".join(sections)


def build_arg_parser() -> argparse.ArgumentParser:
    """Create CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Tong hop so lieu do dac Chuong 4 tu log Serial va CSV."
    )
    parser.add_argument("--modbus-log", type=Path, default=None, help="File log Node A (Modbus 50 lan).")
    parser.add_argument("--espnow-1m-log", type=Path, default=None, help="File log Node B (ESP-NOW 100 goi 1m).")
    parser.add_argument("--espnow-5m-log", type=Path, default=None, help="File log Node B (ESP-NOW 100 goi 5m).")
    parser.add_argument("--rpc-csv", type=Path, default=None, help="File CSV đo 10 lần RPC.")
    parser.add_argument("--rpc-log", type=Path, default=None, help="File log Node B có chứa lệnh [TX] và ACK RPC.")
    parser.add_argument("--notif-csv", type=Path, default=None, help="File CSV đo 5 lần Notification.")
    parser.add_argument("--output", type=Path, default=None, help="Đường dẫn file Markdown xuất ra.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    report = generate_report(args)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
        print(f"[ĐÃ XUẤT BÁO CÁO CHƯƠNG 4] {args.output}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
