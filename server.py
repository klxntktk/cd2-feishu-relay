#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CloudDrive2 → Feishu(Lark) Webhook Relay

接收 CloudDrive2 的 webhook 推送，将文件变动/挂载状态翻译为中文，
并转发为飞书群机器人通知。

环境变量:
  FEISHU_WEBHOOK  飞书群机器人 Webhook 地址 (必填)
  LISTEN_PORT     监听端口 (默认 9090)

特性:
  - 多线程处理并发请求 (ThreadingHTTPServer)
  - 飞书推送超时 + 失败自动重试
  - 消息长度截断保护 (飞书 text 消息限制 4096 字节)
  - GET /health 健康检查端点
"""

import json
import os
import time
import urllib.request
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler

FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK", "")
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "9090"))
FEISHU_TIMEOUT = int(os.environ.get("FEISHU_TIMEOUT", "10"))
FEISHU_RETRIES = int(os.environ.get("FEISHU_RETRIES", "2"))
MAX_TEXT_BYTES = 4000  # 飞书 text 消息上限 4096 字节，留一点余量

ACTION_MAP = {
    "create": "新建文件/目录 ➕",
    "add": "新建文件/目录 ➕",
    "delete": "删除文件/目录 🗑️",
    "remove": "删除文件/目录 🗑️",
    "move": "移动文件/目录 📁",
    "rename": "重命名/移动文件/目录 ✏️",
    "modify": "修改/更新文件 📝",
    "update": "修改/更新文件 📝",
    "write": "写入文件 📝",
    "mount": "挂载成功 🔌",
    "unmount": "取消挂载 🔌",
    "mount_failed": "挂载失败 ❌",
}


def is_trash_move(dest_file, source_file):
    """Mac 删除文件到废纸篓(.Trashes)时，CD2 底层表现为 rename，这里识别为删除"""
    dest = (dest_file or "").lower()
    if ".trashes" in dest or "/trash" in dest:
        return True
    return False


def translate_action(raw_action, dest_file, source_file):
    """将 CD2 英文动作翻译为中文；优先识别废纸篓删除。"""
    raw_action = str(raw_action or "").strip()
    if is_trash_move(dest_file, source_file):
        return "删除文件/目录（移入废纸篓）🗑️"
    key = raw_action.lower()
    if key in ACTION_MAP:
        return ACTION_MAP[key]
    if raw_action and not raw_action.startswith("{"):
        return f"变动 ({raw_action})"
    return "文件变动/新建 📁"


def send_feishu(text):
    """推送消息到飞书，带超时与重试。成功返回 True。"""
    feishu_msg = {
        "msg_type": "text",
        "content": {"text": text},
    }
    body = json.dumps(feishu_msg).encode("utf-8")

    last_err = None
    for attempt in range(1, FEISHU_RETRIES + 1):
        try:
            req = urllib.request.Request(
                FEISHU_WEBHOOK,
                data=body,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=FEISHU_TIMEOUT) as resp:
                resp_body = resp.read().decode("utf-8")
                print(f"[Relay Success] attempt={attempt} Feishu response: {resp_body}", flush=True)
                return True
        except Exception as err:
            last_err = err
            print(f"[Relay Error] attempt={attempt}/{FEISHU_RETRIES}: {err}", flush=True)
            if attempt < FEISHU_RETRIES:
                time.sleep(1)

    print(f"[Relay Failed] {last_err}", flush=True)
    return False


class RelayHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 健康检查端点
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)

        try:
            payload = json.loads(post_data.decode("utf-8"))
            print(f"[CD2 Received Payload] {json.dumps(payload, ensure_ascii=False)}", flush=True)
        except Exception as e:
            print(f"[Parse Error] {e}, Raw: {post_data}", flush=True)
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Invalid JSON")
            return

        device_name = payload.get("device_name", "未知设备")
        user_name = payload.get("user_name", "未知用户")
        event_time = payload.get("event_time", "")

        events = payload.get("data")
        if isinstance(events, dict):
            events = [events]
        elif not isinstance(events, list):
            events = []

        combined = "\n\n".join(self._format_event(ev, device_name, user_name, event_time) for ev in events)

        # 飞书 text 消息长度保护：超出则截断并提示
        if len(combined.encode("utf-8")) > MAX_TEXT_BYTES:
            truncated = combined.encode("utf-8")[:MAX_TEXT_BYTES].decode("utf-8", errors="ignore")
            truncated += "\n\n⚠️ 事件过多，消息已截断"
            combined = truncated

        if combined.strip():
            send_feishu(combined)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

    def _format_event(self, ev, device_name, user_name, event_time):
        ev = ev or {}
        action_cn = translate_action(
            ev.get("action"), ev.get("destination_file"), ev.get("source_file")
        )
        source_file = str(ev.get("source_file", "")).strip()
        dest_file = str(ev.get("destination_file", "")).strip()
        is_dir = str(ev.get("is_dir", "")).strip()
        mount_point = str(ev.get("mount_point", "")).strip()
        status = str(ev.get("status", "")).strip()
        reason = str(ev.get("reason", "")).strip()

        if mount_point or action_cn in ("挂载成功 🔌", "取消挂载 🔌", "挂载失败 ❌"):
            lines = [
                "🔌【CloudDrive2 挂载状态通知】",
                "-------------------------------",
                f"设备名称: {device_name}",
                f"变动动作: {action_cn}",
            ]
            if mount_point and not mount_point.startswith("{"):
                lines.append(f"挂载路径: {mount_point}")
            if status and not status.startswith("{"):
                lines.append(f"执行状态: {status}")
            if reason and not reason.startswith("{"):
                lines.append(f"失败原因: {reason}")
        else:
            lines = [
                "📁【CloudDrive2 文件变动通知】",
                "-------------------------------",
                f"设备名称: {device_name}",
                f"操作用户: {user_name}",
                f"变动类型: {action_cn}",
            ]
            if is_dir and is_dir.lower() in ("true", "false") and not is_dir.startswith("{"):
                lines.append(f"类型: {'文件夹 🗂️' if is_dir.lower() == 'true' else '文件 📄'}")
            if source_file and not source_file.startswith("{"):
                lines.append(f"源 文件: {source_file}")
            if dest_file and not dest_file.startswith("{"):
                lines.append(f"目标文件: {dest_file}")

        lines.append(f"触发时间: {event_time}")
        return "\n".join(lines)

    def log_message(self, format, *args):
        # 精简访问日志，避免刷屏
        if self.path == "/health":
            return
        super().log_message(format, *args)


if __name__ == "__main__":
    if not FEISHU_WEBHOOK:
        print("[FATAL] FEISHU_WEBHOOK 环境变量未设置，程序无法启动。", flush=True)
        raise SystemExit(1)
    print(f"Starting CD2 Feishu Relay on port {LISTEN_PORT}...", flush=True)
    print(f"[Config] FEISHU_TIMEOUT={FEISHU_TIMEOUT}s FEISHU_RETRIES={FEISHU_RETRIES}", flush=True)
    server = ThreadingHTTPServer(("0.0.0.0", LISTEN_PORT), RelayHandler)
    server.serve_forever()