"""语音链路后端 · 骨架

考生实现区以 TODO 标注。启动契约（判分依赖，勿改）：
    python3 app.py --port 9000 --config config.json
"""
import argparse
import json
import pathlib
import socket
import threading

import audio        # WAV/PCM 工具（考题③）
import http_client  # 调 mock 服务（考题②）
import protocol     # 帧编解码（考题①）


def load_config(path):
    return json.loads(pathlib.Path(path).read_text())


def handle_connection(conn, cfg):
    # TODO 考题①：HELLO / AUDIO_CHUNK / AUDIO_END / ACK / ERROR 流程，
    #             断线续传，落盘 sessions/<session_id>/upload.wav
    # TODO 考题②：完整性校验通过后编排 ASR→LLM→TTS，落盘 reply.wav，ACK 携带 text/reply
    # TODO 考题③：TTS 结果按规范下发设备
    conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = load_config(args.config)

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((cfg.get("listen_host", "127.0.0.1"), args.port))
    srv.listen(16)
    while True:
        conn, _ = srv.accept()
        threading.Thread(target=handle_connection, args=(conn, cfg), daemon=True).start()


if __name__ == "__main__":
    main()
