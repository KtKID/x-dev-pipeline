"""语音链路后端 · 骨架

考生实现区以 TODO 标注。启动契约（判分依赖，勿改）：
    python3 app.py --port 9000 --config config.json
"""
import argparse
import hashlib
import json
import pathlib
import re
import socket
import threading

import audio        # WAV/PCM 工具（考题③）
import http_client  # 调 mock 服务（考题②）
import protocol     # 帧编解码（考题①）


SESSION_ID_RE = re.compile(r"[A-Za-z0-9._-]{1,128}\Z")
UPLOAD_CHUNK_BYTES = audio.PLAYBACK_CHUNK_BYTES


class ConversationError(Exception):
    """可安全映射为设备 ERROR 帧的会话错误。"""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


class SessionState:
    """单会话的进程内连续上传状态。"""

    def __init__(self, session_id):
        self.session_id = session_id
        self.chunks = []
        self.lock = threading.RLock()

    @property
    def last_seq(self):
        return len(self.chunks)

    def accept_chunk(self, seq, payload):
        if not payload or len(payload) > UPLOAD_CHUNK_BYTES:
            raise ConversationError("INTEGRITY_FAIL", "invalid audio chunk size")
        if seq <= 0:
            raise ConversationError("INTEGRITY_FAIL", "invalid audio chunk sequence")
        if seq <= self.last_seq:
            if self.chunks[seq - 1] != payload:
                raise ConversationError("INTEGRITY_FAIL", "replayed chunk differs")
            return
        if seq != self.last_seq + 1:
            raise ConversationError("INTEGRITY_FAIL", "audio chunk sequence gap")
        if self.chunks and len(self.chunks[-1]) != UPLOAD_CHUNK_BYTES:
            raise ConversationError("INTEGRITY_FAIL", "short chunk was not final")
        self.chunks.append(payload)

    def assemble(self, end_seq, payload):
        try:
            metadata = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ConversationError("INTEGRITY_FAIL", "invalid AUDIO_END JSON") from exc
        if not isinstance(metadata, dict):
            raise ConversationError("INTEGRITY_FAIL", "AUDIO_END JSON must be an object")
        total = metadata.get("total_chunks")
        digest = metadata.get("sha256")
        if isinstance(total, bool) or not isinstance(total, int):
            raise ConversationError("INTEGRITY_FAIL", "invalid total_chunks")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
            raise ConversationError("INTEGRITY_FAIL", "invalid sha256")
        if total <= 0 or end_seq != total or total != self.last_seq:
            raise ConversationError("INTEGRITY_FAIL", "audio chunk count mismatch")
        if any(len(chunk) != UPLOAD_CHUNK_BYTES for chunk in self.chunks[:-1]):
            raise ConversationError("INTEGRITY_FAIL", "non-final chunk size mismatch")
        raw = b"".join(self.chunks)
        if hashlib.sha256(raw).hexdigest() != digest.lower():
            raise ConversationError("INTEGRITY_FAIL", "audio sha256 mismatch")
        return raw


_sessions = {}
_sessions_lock = threading.Lock()


def validate_hello(payload):
    try:
        hello = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ConversationError("PROTOCOL_ERROR", "invalid HELLO JSON") from exc
    if not isinstance(hello, dict):
        raise ConversationError("PROTOCOL_ERROR", "HELLO JSON must be an object")
    device_id = hello.get("device_id")
    session_id = hello.get("session_id")
    if not isinstance(device_id, str) or not device_id:
        raise ConversationError("PROTOCOL_ERROR", "invalid device_id")
    if (
        not isinstance(session_id, str)
        or session_id in {".", ".."}
        or not SESSION_ID_RE.fullmatch(session_id)
    ):
        raise ConversationError("PROTOCOL_ERROR", "invalid session_id")
    return device_id, session_id


def get_session(session_id):
    with _sessions_lock:
        return _sessions.setdefault(session_id, SessionState(session_id))


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def send_frame(conn, frame_type, seq, payload=b""):
    conn.sendall(protocol.encode_frame(frame_type, seq, payload))


def send_error(conn, seq, error):
    payload = {"code": error.code}
    if error.message:
        payload["msg"] = error.message
    try:
        send_frame(conn, protocol.T_ERROR, seq, json_bytes(payload))
    except OSError:
        pass


def _config_number(cfg, name, minimum):
    value = cfg.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"invalid config value: {name}")
    return value


def upstream_post(cfg, endpoint, data, content_type):
    timeout_ms = _config_number(cfg, "service_timeout_ms", 1)
    retry_max = _config_number(cfg, "retry_max_5xx", 0)
    base_url = cfg.get("mock_base_url")
    if not isinstance(base_url, str) or not base_url:
        raise ValueError("invalid config value: mock_base_url")
    attempts = 0
    while True:
        try:
            status, body = http_client.post(
                base_url.rstrip("/") + endpoint, data, content_type, timeout_ms
            )
        except TimeoutError as exc:
            raise ConversationError("UPSTREAM_TIMEOUT", f"{endpoint} timed out") from exc
        except OSError as exc:
            raise ConversationError(
                "UPSTREAM_ERROR", f"{endpoint} connection failed: {type(exc).__name__}: {exc}"
            ) from exc
        if 500 <= status <= 599 and attempts < retry_max:
            attempts += 1
            continue
        if not 200 <= status <= 299:
            raise ConversationError("UPSTREAM_ERROR", f"{endpoint} returned HTTP {status}")
        return body


def _response_json(raw, field, endpoint):
    try:
        value = json.loads(raw.decode("utf-8"))[field]
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ConversationError("UPSTREAM_ERROR", f"invalid {endpoint} response") from exc
    if not isinstance(value, str):
        raise ConversationError("UPSTREAM_ERROR", f"invalid {endpoint} response field")
    return value


def orchestrate(upload_wav, cfg):
    asr_raw = upstream_post(cfg, "/asr", upload_wav, "application/octet-stream")
    text = _response_json(asr_raw, "text", "ASR")
    llm_raw = upstream_post(cfg, "/llm", json_bytes({"text": text}), "application/json")
    reply = _response_json(llm_raw, "reply", "LLM")
    reply_wav = upstream_post(
        cfg, "/tts", json_bytes({"text": reply}), "application/json"
    )
    return text, reply, reply_wav


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def load_config(path):
    cfg = json.loads(pathlib.Path(path).read_text())
    _config_number(cfg, "service_timeout_ms", 1)
    _config_number(cfg, "retry_max_5xx", 0)
    if not isinstance(cfg.get("listen_host"), str) or not cfg["listen_host"]:
        raise ValueError("invalid config value: listen_host")
    if not isinstance(cfg.get("mock_base_url"), str) or not cfg["mock_base_url"]:
        raise ValueError("invalid config value: mock_base_url")
    return cfg


def handle_connection(conn, cfg):
    decoder = protocol.FrameDecoder()
    state = None
    active_seq = 0
    try:
        while True:
            incoming = conn.recv(protocol.MAX_PAYLOAD + protocol.HEADER_LEN + protocol.CRC_LEN)
            if not incoming:
                return
            protocol_failure = None
            try:
                frames = decoder.feed(incoming)
            except protocol.ProtocolError as exc:
                frames = exc.frames
                protocol_failure = exc
            for frame_type, seq, payload in frames:
                active_seq = seq
                if state is None:
                    if frame_type != protocol.T_HELLO or seq != 0:
                        raise ConversationError("PROTOCOL_ERROR", "HELLO must be first")
                    _, session_id = validate_hello(payload)
                    state = get_session(session_id)
                    with state.lock:
                        last_seq = state.last_seq
                    send_frame(
                        conn,
                        protocol.T_ACK,
                        0,
                        json_bytes({"last_seq": last_seq}),
                    )
                    continue
                if frame_type == protocol.T_AUDIO_CHUNK:
                    with state.lock:
                        state.accept_chunk(seq, payload)
                    send_frame(conn, protocol.T_ACK, seq)
                    continue
                if frame_type != protocol.T_AUDIO_END:
                    raise ConversationError("PROTOCOL_ERROR", "unexpected frame type")
                with state.lock:
                    upload_wav = state.assemble(seq, payload)
                    session_dir = pathlib.Path("sessions") / state.session_id
                    atomic_write(session_dir / "upload.wav", upload_wav)
                    text, reply, reply_wav = orchestrate(upload_wav, cfg)
                    pcm = audio.wav_pcm(reply_wav)
                    atomic_write(session_dir / "reply.wav", reply_wav)
                send_frame(
                    conn,
                    protocol.T_ACK,
                    seq,
                    json_bytes({"ok": True, "text": text, "reply": reply}),
                )
                chunks = list(audio.chunk_pcm(pcm, audio.PLAYBACK_CHUNK_BYTES))
                for chunk_seq, chunk in enumerate(chunks, 1):
                    send_frame(conn, protocol.T_TTS_CHUNK, chunk_seq, chunk)
                end_payload = json_bytes(
                    {
                        "total_chunks": len(chunks),
                        "sha256": hashlib.sha256(pcm).hexdigest(),
                    }
                )
                send_frame(conn, protocol.T_TTS_END, len(chunks), end_payload)
                return
            if protocol_failure is not None:
                send_error(
                    conn,
                    protocol_failure.seq,
                    ConversationError(protocol_failure.code, protocol_failure.code),
                )
                return
    except ConversationError as exc:
        send_error(conn, active_seq, exc)
    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
        pass
    except (OSError, ValueError) as exc:
        send_error(conn, active_seq, ConversationError("UPSTREAM_ERROR", str(exc)))
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = load_config(args.config)

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((cfg["listen_host"], args.port))
    srv.listen(16)
    while True:
        conn, _ = srv.accept()
        threading.Thread(target=handle_connection, args=(conn, cfg), daemon=True).start()


if __name__ == "__main__":
    main()
