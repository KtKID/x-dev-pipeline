"""语音链路后端 · 骨架

考生实现区以 TODO 标注。启动契约（判分依赖，勿改）：
    python3 app.py --port 9000 --config config.json
"""
import argparse
import hashlib
import json
import pathlib
import socket
import threading
import urllib.parse

import audio        # WAV/PCM 工具（考题③）
import http_client  # 调 mock 服务（考题②）
import protocol     # 帧编解码（考题①）


RECV_SIZE = protocol.HEADER_LEN + protocol.MAX_PAYLOAD + protocol.CRC_LEN
SESSIONS_DIR = pathlib.Path("sessions")


class UpstreamFailure(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


class ClientFailure(Exception):
    def __init__(self, code, seq, message):
        super().__init__(message)
        self.code = code
        self.seq = seq
        self.message = message


class SessionState:
    def __init__(self, session_id, device_id):
        self.session_id = session_id
        self.device_id = device_id
        self.lock = threading.RLock()
        self.chunks = {}
        self.short_seq = None
        self.completed = None

    @property
    def last_seq(self):
        return len(self.chunks)


_sessions = {}
_sessions_lock = threading.Lock()


def load_config(path):
    return validate_config(json.loads(pathlib.Path(path).read_text()))


def validate_config(cfg):
    if not isinstance(cfg, dict):
        raise ValueError("config must be a JSON object")
    host = cfg.get("listen_host", "127.0.0.1")
    if not isinstance(host, str) or not host:
        raise ValueError("listen_host must be a non-empty string")
    base_url = cfg.get("mock_base_url")
    if not isinstance(base_url, str):
        raise ValueError("mock_base_url must be a URL string")
    parsed = urllib.parse.urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.query or parsed.fragment:
        raise ValueError("mock_base_url must be an absolute HTTP(S) base URL")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("mock_base_url contains an invalid port") from exc
    if port is not None and port < 1:
        raise ValueError("mock_base_url contains an invalid port")
    timeout_ms = cfg.get("service_timeout_ms")
    if isinstance(timeout_ms, bool) or not isinstance(timeout_ms, int) or timeout_ms <= 0:
        raise ValueError("service_timeout_ms must be a positive integer")
    retry_max = cfg.get("retry_max_5xx")
    if isinstance(retry_max, bool) or not isinstance(retry_max, int) or retry_max < 0:
        raise ValueError("retry_max_5xx must be a non-negative integer")
    return cfg


def _json_payload(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()


def _parse_object(payload, seq):
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ClientFailure("INTEGRITY_FAIL", seq, "invalid JSON payload") from exc
    if not isinstance(value, dict):
        raise ClientFailure("INTEGRITY_FAIL", seq, "JSON payload must be an object")
    return value


def _validate_session_id(value, seq):
    if not isinstance(value, str) or not value or pathlib.Path(value).name != value:
        raise ClientFailure("INTEGRITY_FAIL", seq, "invalid session_id")
    if value in {".", ".."} or "\x00" in value:
        raise ClientFailure("INTEGRITY_FAIL", seq, "invalid session_id")
    return value


def _session_for(session_id, device_id):
    with _sessions_lock:
        state = _sessions.get(session_id)
        if state is None:
            state = SessionState(session_id, device_id)
            _sessions[session_id] = state
        return state


def _write_atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{threading.get_ident()}.tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def call_upstream(url, data, content_type, timeout_ms, retry_max_5xx):
    """执行一次上游阶段，5xx 最多做配置数量的额外重试。"""
    for attempt in range(retry_max_5xx + 1):
        try:
            status, body = http_client.post(url, data, content_type, timeout_ms)
        except TimeoutError as exc:
            raise UpstreamFailure("UPSTREAM_TIMEOUT", f"timeout calling {url}") from exc
        except OSError as exc:
            raise UpstreamFailure("UPSTREAM_ERROR", f"network error calling {url}") from exc

        if 200 <= status < 300:
            return body
        if 500 <= status < 600 and attempt < retry_max_5xx:
            continue
        raise UpstreamFailure("UPSTREAM_ERROR", f"upstream status {status} from {url}")
    raise AssertionError("unreachable retry loop")


def _required_text(body, field, service):
    try:
        value = json.loads(body)[field]
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise UpstreamFailure("UPSTREAM_ERROR", f"invalid {service} response") from exc
    if not isinstance(value, str):
        raise UpstreamFailure("UPSTREAM_ERROR", f"invalid {service} response")
    return value


def _orchestrate(raw, cfg, session_dir):
    base_url = cfg["mock_base_url"].rstrip("/")
    timeout_ms = cfg["service_timeout_ms"]
    retry_max_5xx = cfg["retry_max_5xx"]

    asr_body = call_upstream(
        f"{base_url}/asr", raw, "application/octet-stream", timeout_ms, retry_max_5xx
    )
    text = _required_text(asr_body, "text", "ASR")

    llm_body = call_upstream(
        f"{base_url}/llm",
        _json_payload({"text": text}),
        "application/json",
        timeout_ms,
        retry_max_5xx,
    )
    reply = _required_text(llm_body, "reply", "LLM")

    tts_wav = call_upstream(
        f"{base_url}/tts",
        _json_payload({"text": reply}),
        "application/json",
        timeout_ms,
        retry_max_5xx,
    )
    _write_atomic(session_dir / "reply.wav", tts_wav)
    try:
        pcm = audio.wav_pcm(tts_wav)
    except ValueError as exc:
        raise UpstreamFailure("UPSTREAM_ERROR", "TTS returned unsupported WAV") from exc
    return text, reply, tts_wav, pcm


def _send(conn, frame_type, seq, payload=b""):
    conn.sendall(protocol.encode_frame(frame_type, seq, payload))


def _send_error(conn, code, seq, message):
    payload = {"code": code}
    if message:
        payload["msg"] = message
    try:
        _send(conn, protocol.T_ERROR, seq, _json_payload(payload))
    except OSError:
        pass


def _send_downlink(conn, pcm):
    chunks = list(audio.chunk_pcm(pcm, audio.PCM_CHUNK_SIZE))
    for seq, chunk in enumerate(chunks, 1):
        _send(conn, protocol.T_TTS_CHUNK, seq, chunk)
    metadata = {
        "total_chunks": len(chunks),
        "sha256": hashlib.sha256(pcm).hexdigest(),
    }
    _send(conn, protocol.T_TTS_END, len(chunks), _json_payload(metadata))


def _handle_hello(conn, seq, payload):
    if seq != 0:
        raise ClientFailure("INTEGRITY_FAIL", seq, "HELLO seq must be zero")
    hello = _parse_object(payload, seq)
    session_id = _validate_session_id(hello.get("session_id"), seq)
    device_id = hello.get("device_id")
    if not isinstance(device_id, str) or not device_id:
        raise ClientFailure("INTEGRITY_FAIL", seq, "invalid device_id")
    state = _session_for(session_id, device_id)
    with state.lock:
        last_seq = state.last_seq
    _send(conn, protocol.T_ACK, 0, _json_payload({"last_seq": last_seq}))
    return state


def _handle_chunk(conn, state, seq, payload):
    with state.lock:
        if seq in state.chunks:
            if state.chunks[seq] != payload:
                raise ClientFailure("INTEGRITY_FAIL", seq, "chunk content changed")
        else:
            expected = state.last_seq + 1
            if seq != expected or state.completed is not None:
                raise ClientFailure("INTEGRITY_FAIL", seq, f"expected chunk {expected}")
            if not payload or len(payload) > audio.PCM_CHUNK_SIZE or state.short_seq is not None:
                raise ClientFailure("INTEGRITY_FAIL", seq, "invalid audio chunk boundary")
            state.chunks[seq] = bytes(payload)
            if len(payload) < audio.PCM_CHUNK_SIZE:
                state.short_seq = seq
    _send(conn, protocol.T_ACK, seq)


def _handle_end(conn, state, seq, payload, cfg):
    end = _parse_object(payload, seq)
    total_chunks = end.get("total_chunks")
    expected_hash = end.get("sha256")
    if (
        not isinstance(total_chunks, int)
        or isinstance(total_chunks, bool)
        or total_chunks < 1
        or seq != total_chunks
        or not isinstance(expected_hash, str)
        or len(expected_hash) != hashlib.sha256().digest_size * 2
    ):
        raise ClientFailure("INTEGRITY_FAIL", seq, "invalid AUDIO_END metadata")
    try:
        int(expected_hash, 16)
    except ValueError as exc:
        raise ClientFailure("INTEGRITY_FAIL", seq, "invalid AUDIO_END sha256") from exc

    with state.lock:
        if state.last_seq != total_chunks:
            raise ClientFailure("INTEGRITY_FAIL", seq, "missing audio chunks")
        raw = b"".join(state.chunks[index] for index in range(1, total_chunks + 1))
        actual_hash = hashlib.sha256(raw).hexdigest()
        if actual_hash != expected_hash.lower():
            raise ClientFailure("INTEGRITY_FAIL", seq, "upload sha256 mismatch")

        session_dir = SESSIONS_DIR / state.session_id
        if state.completed is None:
            _write_atomic(session_dir / "upload.wav", raw)
            text, reply, _tts_wav, pcm = _orchestrate(raw, cfg, session_dir)
            state.completed = {
                "upload_hash": actual_hash,
                "text": text,
                "reply": reply,
                "pcm": pcm,
            }
        elif state.completed["upload_hash"] != actual_hash:
            raise ClientFailure("INTEGRITY_FAIL", seq, "completed session content changed")

        ack = {
            "ok": True,
            "text": state.completed["text"],
            "reply": state.completed["reply"],
        }
        pcm = state.completed["pcm"]
        _send(conn, protocol.T_ACK, total_chunks, _json_payload(ack))
        _send_downlink(conn, pcm)


def _dispatch_frame(conn, state, frame_type, seq, payload, cfg):
    if frame_type == protocol.T_HELLO:
        if state is not None:
            raise ClientFailure("INTEGRITY_FAIL", seq, "duplicate HELLO")
        return _handle_hello(conn, seq, payload)
    if state is None:
        raise ClientFailure("INTEGRITY_FAIL", seq, "HELLO required")
    if frame_type == protocol.T_AUDIO_CHUNK:
        _handle_chunk(conn, state, seq, payload)
    elif frame_type == protocol.T_AUDIO_END:
        _handle_end(conn, state, seq, payload, cfg)
    else:
        raise ClientFailure("INTEGRITY_FAIL", seq, "unexpected frame type")
    return state


def handle_connection(conn, cfg):
    decoder = protocol.FrameDecoder()
    state = None
    active_seq = 0
    try:
        while True:
            data = conn.recv(RECV_SIZE)
            if not data:
                return
            try:
                frames = decoder.feed(data)
            except protocol.ProtocolError as exc:
                for frame_type, seq, payload in exc.frames:
                    active_seq = seq
                    state = _dispatch_frame(conn, state, frame_type, seq, payload, cfg)
                raise
            for frame_type, seq, payload in frames:
                active_seq = seq
                state = _dispatch_frame(conn, state, frame_type, seq, payload, cfg)
    except protocol.ProtocolError as exc:
        _send_error(conn, exc.code, exc.seq, str(exc))
    except (ClientFailure, UpstreamFailure) as exc:
        _send_error(conn, exc.code, getattr(exc, "seq", active_seq), exc.message)
    except (BrokenPipeError, ConnectionResetError, OSError):
        pass
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
    srv.bind((cfg.get("listen_host", "127.0.0.1"), args.port))
    srv.listen(socket.SOMAXCONN)
    while True:
        conn, _ = srv.accept()
        threading.Thread(target=handle_connection, args=(conn, cfg), daemon=True).start()


if __name__ == "__main__":
    main()
