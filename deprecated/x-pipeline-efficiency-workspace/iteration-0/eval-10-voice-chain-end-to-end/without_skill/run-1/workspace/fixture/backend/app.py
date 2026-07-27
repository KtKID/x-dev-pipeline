"""语音链路后端。

启动契约：
    python3 app.py --port 9000 --config config.json
"""
import argparse
from dataclasses import dataclass, field
import hashlib
import hmac
import json
import pathlib
import re
import socket
import threading

import audio
import http_client
import protocol


# docs/spec/voice-chain/spec.md J8 记录的路径安全边界。
SESSION_ID_RE = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9._-]{0,127}\Z")


class ClientError(Exception):
    def __init__(self, code, seq=0, msg=None):
        super().__init__(msg or code)
        self.code = code
        self.seq = seq
        self.msg = msg


class UpstreamFailure(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code
        self.msg = msg


@dataclass
class SessionState:
    device_id: str
    session_id: str
    chunks: dict = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def last_seq(self):
        return len(self.chunks)


_sessions = {}
_sessions_lock = threading.Lock()


def load_config(path):
    cfg = json.loads(pathlib.Path(path).read_text())
    required = ("listen_host", "mock_base_url", "service_timeout_ms", "retry_max_5xx")
    missing = [key for key in required if key not in cfg]
    if missing:
        raise ValueError(f"missing config keys: {', '.join(missing)}")
    if not isinstance(cfg["service_timeout_ms"], int) or cfg["service_timeout_ms"] <= 0:
        raise ValueError("service_timeout_ms must be a positive integer")
    if not isinstance(cfg["retry_max_5xx"], int) or cfg["retry_max_5xx"] < 0:
        raise ValueError("retry_max_5xx must be a non-negative integer")
    return cfg


def _json_bytes(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _parse_json_object(payload, seq, label):
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ClientError("INTEGRITY_FAIL", seq, f"invalid {label} JSON") from exc
    if not isinstance(value, dict):
        raise ClientError("INTEGRITY_FAIL", seq, f"{label} payload must be an object")
    return value


def _send_frame(conn, frame_type, seq, payload=b""):
    conn.sendall(protocol.encode_frame(frame_type, seq, payload))


def _send_error(conn, code, seq=0, msg=None):
    payload = {"code": code}
    if msg:
        payload["msg"] = msg
    try:
        _send_frame(conn, protocol.T_ERROR, seq, _json_bytes(payload))
    except OSError:
        pass


def _get_session(device_id, session_id):
    if not isinstance(device_id, str) or not device_id:
        raise ClientError("INTEGRITY_FAIL", 0, "device_id must be a non-empty string")
    if not isinstance(session_id, str) or not SESSION_ID_RE.fullmatch(session_id):
        raise ClientError("INTEGRITY_FAIL", 0, "unsafe session_id")
    with _sessions_lock:
        state = _sessions.get(session_id)
        if state is None:
            state = SessionState(device_id=device_id, session_id=session_id)
            _sessions[session_id] = state
        elif state.device_id != device_id:
            raise ClientError("INTEGRITY_FAIL", 0, "session belongs to another device")
    return state


def _atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def _service_post(cfg, path, body, content_type):
    url = cfg["mock_base_url"].rstrip("/") + path
    attempts = cfg["retry_max_5xx"] + 1
    for attempt in range(attempts):
        try:
            status, response = http_client.post(
                url, body, content_type, cfg["service_timeout_ms"]
            )
        except (TimeoutError, socket.timeout) as exc:
            raise UpstreamFailure("UPSTREAM_TIMEOUT", f"{path} timed out") from exc
        except OSError as exc:
            detail = f"{type(exc).__name__}: {exc}"
            raise UpstreamFailure("UPSTREAM_ERROR", f"{path} transport failure ({detail})") from exc
        if status == 200:
            return response
        if status >= 500 and attempt + 1 < attempts:
            continue
        raise UpstreamFailure("UPSTREAM_ERROR", f"{path} returned HTTP {status}")
    raise AssertionError("unreachable retry state")


def _response_text(body, key, path):
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UpstreamFailure("UPSTREAM_ERROR", f"{path} returned invalid JSON") from exc
    result = value.get(key) if isinstance(value, dict) else None
    if not isinstance(result, str):
        raise UpstreamFailure("UPSTREAM_ERROR", f"{path} response lacks {key}")
    return result


def run_pipeline(cfg, upload_wav):
    asr_body = _service_post(cfg, "/asr", upload_wav, "application/octet-stream")
    text = _response_text(asr_body, "text", "/asr")
    llm_body = _service_post(
        cfg, "/llm", _json_bytes({"text": text}), "application/json"
    )
    reply = _response_text(llm_body, "reply", "/llm")
    reply_wav = _service_post(
        cfg, "/tts", _json_bytes({"text": reply}), "application/json"
    )
    try:
        reply_pcm = audio.wav_pcm(reply_wav)
    except ValueError as exc:
        raise UpstreamFailure("UPSTREAM_ERROR", "/tts returned unsupported WAV") from exc
    return text, reply, reply_wav, reply_pcm


def _handle_hello(conn, seq, payload):
    if seq != 0:
        raise ClientError("INTEGRITY_FAIL", seq, "HELLO seq must be 0")
    hello = _parse_json_object(payload, seq, "HELLO")
    state = _get_session(hello.get("device_id"), hello.get("session_id"))
    with state.lock:
        last_seq = state.last_seq
    _send_frame(conn, protocol.T_ACK, 0, _json_bytes({"last_seq": last_seq}))
    return state


def _handle_chunk(conn, state, seq, payload):
    if state is None:
        raise ClientError("INTEGRITY_FAIL", seq, "HELLO required before AUDIO_CHUNK")
    with state.lock:
        if seq <= state.last_seq:
            if state.chunks.get(seq) != payload:
                raise ClientError("INTEGRITY_FAIL", seq, "duplicate chunk content differs")
        elif seq == state.last_seq + 1:
            if not payload:
                raise ClientError("INTEGRITY_FAIL", seq, "empty audio chunk")
            state.chunks[seq] = bytes(payload)
        else:
            raise ClientError("INTEGRITY_FAIL", seq, "audio chunks must be consecutive")
    _send_frame(conn, protocol.T_ACK, seq)


def _validated_upload(state, seq, payload):
    end = _parse_json_object(payload, seq, "AUDIO_END")
    total = end.get("total_chunks")
    digest = end.get("sha256")
    if not isinstance(total, int) or isinstance(total, bool) or total <= 0:
        raise ClientError("INTEGRITY_FAIL", seq, "invalid total_chunks")
    if seq != total or state.last_seq != total:
        raise ClientError("INTEGRITY_FAIL", seq, "chunk count mismatch")
    for index in range(1, total + 1):
        chunk_len = len(state.chunks[index])
        if chunk_len <= 0 or chunk_len > audio.AUDIO_BLOCK_SIZE:
            raise ClientError("INTEGRITY_FAIL", seq, "invalid audio chunk size")
        if index < total and chunk_len != audio.AUDIO_BLOCK_SIZE:
            raise ClientError("INTEGRITY_FAIL", seq, "short non-final audio chunk")
    if not isinstance(digest, str) or len(digest) != hashlib.sha256().digest_size * 2:
        raise ClientError("INTEGRITY_FAIL", seq, "invalid sha256")
    upload_wav = b"".join(state.chunks[index] for index in range(1, total + 1))
    if not hmac.compare_digest(hashlib.sha256(upload_wav).hexdigest(), digest.lower()):
        raise ClientError("INTEGRITY_FAIL", seq, "sha256 mismatch")
    try:
        audio.wav_pcm(upload_wav)
    except ValueError as exc:
        raise ClientError("INTEGRITY_FAIL", seq, "unsupported upload WAV") from exc
    return total, upload_wav


def _handle_end(conn, cfg, state, seq, payload):
    if state is None:
        raise ClientError("INTEGRITY_FAIL", seq, "HELLO required before AUDIO_END")
    with state.lock:
        total, upload_wav = _validated_upload(state, seq, payload)
        session_dir = pathlib.Path("sessions") / state.session_id
        _atomic_write(session_dir / "upload.wav", upload_wav)

        try:
            text, reply, reply_wav, reply_pcm = run_pipeline(cfg, upload_wav)
        except UpstreamFailure as exc:
            raise ClientError(exc.code, seq, exc.msg) from exc
        _atomic_write(session_dir / "reply.wav", reply_wav)

        ack = {"ok": True, "text": text, "reply": reply}
        _send_frame(conn, protocol.T_ACK, total, _json_bytes(ack))
        chunks = list(audio.chunk_pcm(reply_pcm, audio.AUDIO_BLOCK_SIZE))
        for chunk_seq, chunk in enumerate(chunks, 1):
            _send_frame(conn, protocol.T_TTS_CHUNK, chunk_seq, chunk)
        end_payload = {
            "total_chunks": len(chunks),
            "sha256": hashlib.sha256(reply_pcm).hexdigest(),
        }
        _send_frame(conn, protocol.T_TTS_END, len(chunks), _json_bytes(end_payload))


def handle_connection(conn, cfg):
    decoder = protocol.FrameDecoder()
    state = None
    finished = False
    try:
        while not finished:
            data = conn.recv(protocol.MAX_PAYLOAD + protocol.HEADER_LEN + protocol.CRC_LEN)
            if not data:
                break
            for frame_type, seq, payload in decoder.feed(data):
                if frame_type == protocol.T_HELLO:
                    if state is not None:
                        raise ClientError("INTEGRITY_FAIL", seq, "duplicate HELLO")
                    state = _handle_hello(conn, seq, payload)
                elif frame_type == protocol.T_AUDIO_CHUNK:
                    _handle_chunk(conn, state, seq, payload)
                elif frame_type == protocol.T_AUDIO_END:
                    _handle_end(conn, cfg, state, seq, payload)
                    finished = True
                    break
                else:
                    raise ClientError("INTEGRITY_FAIL", seq, "unexpected frame type")
    except protocol.ProtocolError as exc:
        _send_error(conn, exc.code, exc.seq)
    except ClientError as exc:
        _send_error(conn, exc.code, exc.seq, exc.msg)
    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
        pass
    except OSError:
        # Socket lifecycle failures are isolated to this connection.
        pass
    except Exception:
        # Preserve the finite-response contract for unexpected per-connection failures.
        _send_error(conn, "UPSTREAM_ERROR", 0, "internal connection failure")
    finally:
        try:
            conn.close()
        except OSError:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = load_config(args.config)

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((cfg["listen_host"], args.port))
    srv.listen()
    while True:
        conn, _ = srv.accept()
        threading.Thread(target=handle_connection, args=(conn, cfg), daemon=True).start()


if __name__ == "__main__":
    main()
