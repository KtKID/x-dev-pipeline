"""语音链路后端 · 骨架

考生实现区以 TODO 标注。启动契约（判分依赖，勿改）：
    python3 app.py --port 9000 --config config.json
"""
import argparse
import hashlib
import json
import os
import pathlib
import re
import secrets
import socket
import tempfile
import threading
import time

import audio        # WAV/PCM 工具（考题③）
import http_client  # 调 mock 服务（考题②）
import protocol     # 帧编解码（考题①）


class SessionState:
    """A process-local resumable upload and its completed response."""

    def __init__(self, device_id):
        self.device_id = device_id
        self.chunks = {}
        self.condition = threading.Condition()
        self.processing = False
        self.result = None
        self.upload_sha = None
        self.total_chunks = None
        self.byte_count = 0
        self.last_activity = time.monotonic()
        self.active_connections = 0

    @property
    def last_seq(self):
        return len(self.chunks)


_sessions = {}
_sessions_lock = threading.Lock()


class RequestFailure(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def _json_bytes(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _parse_json_object(payload):
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RequestFailure("INTEGRITY_FAIL", "invalid JSON payload") from exc
    if not isinstance(value, dict):
        raise RequestFailure("INTEGRITY_FAIL", "JSON payload must be an object")
    return value


def _valid_identifier(value, max_length):
    return (
        isinstance(value, str)
        and 0 < len(value) <= max_length
        and value not in {".", ".."}
        and re.fullmatch(r"[A-Za-z0-9._-]+", value) is not None
    )


def _open_session(payload, cfg):
    hello = _parse_json_object(payload)
    device_id = hello.get("device_id")
    session_id = hello.get("session_id")
    max_length = cfg["session_id_max_length"]
    if (
        not isinstance(device_id, str)
        or not device_id
        or len(device_id) > cfg["device_id_max_length"]
    ):
        raise RequestFailure("INTEGRITY_FAIL", "invalid device_id")
    if not _valid_identifier(session_id, max_length):
        raise RequestFailure("INTEGRITY_FAIL", "invalid session_id")
    now = time.monotonic()
    with _sessions_lock:
        for existing_id, existing in list(_sessions.items()):
            with existing.condition:
                expired = (
                    not existing.processing
                    and existing.active_connections == 0
                    and now - existing.last_activity > cfg["session_ttl_seconds"]
                )
            if expired:
                del _sessions[existing_id]
        session = _sessions.get(session_id)
        if session is None:
            if len(_sessions) >= cfg["max_sessions"]:
                raise RequestFailure("INTEGRITY_FAIL", "session capacity reached")
            session = SessionState(device_id)
            _sessions[session_id] = session
        elif session.device_id != device_id:
            raise RequestFailure("INTEGRITY_FAIL", "session belongs to another device")
        with session.condition:
            session.last_activity = now
            session.active_connections += 1
    return session_id, session


def _accept_chunk(session, seq, payload, cfg):
    chunk_size = cfg["audio_chunk_bytes"]
    if not 0 < len(payload) <= chunk_size:
        raise RequestFailure("INTEGRITY_FAIL", "invalid audio chunk size")
    with session.condition:
        previous = session.chunks.get(seq)
        if previous is not None:
            if previous != payload:
                raise RequestFailure("INTEGRITY_FAIL", "conflicting repeated chunk")
            session.last_activity = time.monotonic()
            return
        expected = session.last_seq + 1
        if seq != expected:
            raise RequestFailure("INTEGRITY_FAIL", "audio chunks must be contiguous")
        if session.upload_sha is not None:
            raise RequestFailure("INTEGRITY_FAIL", "upload is already finalized")
        if session.chunks and len(session.chunks[session.last_seq]) < chunk_size:
            raise RequestFailure("INTEGRITY_FAIL", "chunk received after short final chunk")
        if session.byte_count + len(payload) > cfg["max_upload_bytes"]:
            raise RequestFailure("INTEGRITY_FAIL", "upload exceeds configured maximum")
        session.chunks[seq] = payload
        session.byte_count += len(payload)
        session.last_activity = time.monotonic()


def _assemble_upload(session, end_seq, payload, cfg):
    end = _parse_json_object(payload)
    total_chunks = end.get("total_chunks")
    expected_sha = end.get("sha256")
    if (
        not isinstance(total_chunks, int)
        or isinstance(total_chunks, bool)
        or total_chunks <= 0
        or end_seq != total_chunks
        or not isinstance(expected_sha, str)
        or re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha) is None
    ):
        raise RequestFailure("INTEGRITY_FAIL", "invalid AUDIO_END payload")

    chunk_size = cfg["audio_chunk_bytes"]
    with session.condition:
        if session.last_seq != total_chunks:
            raise RequestFailure("INTEGRITY_FAIL", "missing audio chunks")
        chunks = [session.chunks[i] for i in range(1, total_chunks + 1)]
        if any(len(chunk) != chunk_size for chunk in chunks[:-1]):
            raise RequestFailure("INTEGRITY_FAIL", "short non-final audio chunk")
        raw = b"".join(chunks)
        if hashlib.sha256(raw).hexdigest() != expected_sha.lower():
            raise RequestFailure("INTEGRITY_FAIL", "upload sha256 mismatch")
        if session.upload_sha is not None and (
            session.upload_sha != expected_sha.lower()
            or session.total_chunks != total_chunks
        ):
            raise RequestFailure("INTEGRITY_FAIL", "conflicting AUDIO_END")
        session.upload_sha = expected_sha.lower()
        session.total_chunks = total_chunks
        session.last_activity = time.monotonic()
        return raw


def _session_dir(session_id, cfg):
    root = pathlib.Path(cfg["sessions_dir"])
    return root / session_id


def _atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = pathlib.Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _write_session_file(session_id, filename, data, cfg):
    """Atomically write below the configured root without following session links."""
    root = pathlib.Path(cfg["sessions_dir"])
    root.mkdir(parents=True, exist_ok=True)
    directory_flags = os.O_RDONLY | os.O_DIRECTORY
    root_fd = os.open(root, directory_flags)
    session_fd = None
    temporary = None
    try:
        try:
            os.mkdir(session_id, mode=0o700, dir_fd=root_fd)
        except FileExistsError:
            pass
        try:
            session_fd = os.open(
                session_id,
                directory_flags | os.O_NOFOLLOW,
                dir_fd=root_fd,
            )
        except OSError as exc:
            raise RequestFailure("INTEGRITY_FAIL", "unsafe session directory") from exc

        for _ in range(16):
            candidate = ".tmp-" + secrets.token_hex(12)
            try:
                file_fd = os.open(
                    candidate,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=session_fd,
                )
                temporary = candidate
                break
            except FileExistsError:
                continue
        else:
            raise OSError("could not allocate temporary session file")

        with os.fdopen(file_fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(
            temporary,
            filename,
            src_dir_fd=session_fd,
            dst_dir_fd=session_fd,
        )
        temporary = None
    finally:
        if temporary is not None and session_fd is not None:
            try:
                os.unlink(temporary, dir_fd=session_fd)
            except FileNotFoundError:
                pass
        if session_fd is not None:
            os.close(session_fd)
        os.close(root_fd)


def _post_with_policy(path, data, content_type, cfg):
    url = cfg["mock_base_url"].rstrip("/") + path
    retries_left = cfg["retry_max_5xx"]
    while True:
        try:
            status, body = http_client.post(
                url,
                data,
                content_type,
                cfg["service_timeout_ms"],
                cfg[
                    "max_tts_wav_bytes"
                    if path == "/tts"
                    else "max_json_response_bytes"
                ],
                cfg["max_http_header_bytes"],
            )
        except (TimeoutError, socket.timeout) as exc:
            raise RequestFailure("UPSTREAM_TIMEOUT", f"{path} timed out") from exc
        except (OSError, ValueError) as exc:
            raise RequestFailure("UPSTREAM_ERROR", f"{path} transport error") from exc

        if status == 200:
            return body
        if 500 <= status < 600 and retries_left > 0:
            retries_left -= 1
            continue
        raise RequestFailure("UPSTREAM_ERROR", f"{path} returned HTTP {status}")


def _response_string(body, field, service):
    try:
        response = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RequestFailure("UPSTREAM_ERROR", f"invalid {service} response") from exc
    value = response.get(field) if isinstance(response, dict) else None
    if not isinstance(value, str) or not value:
        raise RequestFailure("UPSTREAM_ERROR", f"invalid {service} response")
    return value


def _orchestrate(upload, cfg):
    asr_body = _post_with_policy(
        "/asr", upload, "application/octet-stream", cfg
    )
    text = _response_string(asr_body, "text", "ASR")
    llm_body = _post_with_policy(
        "/llm", _json_bytes({"text": text}), "application/json", cfg
    )
    reply = _response_string(llm_body, "reply", "LLM")
    tts_wav = _post_with_policy(
        "/tts", _json_bytes({"text": reply}), "application/json", cfg
    )
    return text, reply, tts_wav


def _get_or_process(session_id, session, upload, cfg):
    with session.condition:
        while session.processing and session.result is None:
            session.condition.wait()
        if session.result is not None:
            return session.result
        session.processing = True

    try:
        text, reply, tts_wav = _orchestrate(upload, cfg)
        try:
            pcm = audio.wav_pcm(
                tts_wav,
                sample_rate=cfg["pcm_sample_rate_hz"],
                channels=cfg["pcm_channels"],
                bits_per_sample=cfg["pcm_bits_per_sample"],
            )
        except ValueError as exc:
            raise RequestFailure("UPSTREAM_ERROR", "unsupported TTS WAV") from exc
        _write_session_file(session_id, "reply.wav", tts_wav, cfg)
        result = (text, reply, tts_wav, pcm)
    except Exception:
        with session.condition:
            session.processing = False
            session.condition.notify_all()
        raise

    with session.condition:
        session.result = result
        session.processing = False
        session.condition.notify_all()
        return result


def _send_json_frame(conn, frame_type, seq, value):
    payload = _json_bytes(value)
    if len(payload) > protocol.MAX_PAYLOAD:
        raise RequestFailure("UPSTREAM_ERROR", "response payload exceeds protocol limit")
    conn.sendall(protocol.encode_frame(frame_type, seq, payload))


def _send_error(conn, seq, failure):
    payload = {"code": failure.code}
    if failure.message:
        payload["msg"] = failure.message
    try:
        _send_json_frame(conn, protocol.T_ERROR, seq, payload)
    except (OSError, RequestFailure, ValueError):
        pass


def _send_downlink(conn, pcm, cfg):
    chunks = list(audio.chunk_pcm(pcm, cfg["audio_chunk_bytes"]))
    for seq, chunk in enumerate(chunks, 1):
        conn.sendall(protocol.encode_frame(protocol.T_TTS_CHUNK, seq, chunk))
    _send_json_frame(conn, protocol.T_TTS_END, len(chunks), {
        "total_chunks": len(chunks),
        "sha256": hashlib.sha256(pcm).hexdigest(),
    })


def _handle_frame(conn, frame, cfg, connection_state):
    frame_type, seq, payload = frame
    session = connection_state.get("session")
    if session is None:
        if frame_type != protocol.T_HELLO or seq != 0:
            raise RequestFailure("INTEGRITY_FAIL", "HELLO must be the first frame")
        session_id, session = _open_session(payload, cfg)
        connection_state["session_id"] = session_id
        connection_state["session"] = session
        with session.condition:
            last_seq = session.last_seq
        _send_json_frame(conn, protocol.T_ACK, 0, {"last_seq": last_seq})
        return False

    if frame_type == protocol.T_HELLO:
        raise RequestFailure("INTEGRITY_FAIL", "duplicate HELLO")
    if frame_type == protocol.T_AUDIO_CHUNK:
        _accept_chunk(session, seq, payload, cfg)
        conn.sendall(protocol.encode_frame(protocol.T_ACK, seq))
        return False
    if frame_type != protocol.T_AUDIO_END:
        raise RequestFailure("INTEGRITY_FAIL", "unexpected frame type")

    upload = _assemble_upload(session, seq, payload, cfg)
    session_id = connection_state["session_id"]
    _write_session_file(session_id, "upload.wav", upload, cfg)
    text, reply, _, pcm = _get_or_process(session_id, session, upload, cfg)
    _send_json_frame(conn, protocol.T_ACK, seq, {
        "ok": True,
        "text": text,
        "reply": reply,
    })
    _send_downlink(conn, pcm, cfg)
    return True


def _reset_sessions_for_tests():
    with _sessions_lock:
        _sessions.clear()


def load_config(path):
    return json.loads(pathlib.Path(path).read_text())


def handle_connection(conn, cfg):
    decoder = protocol.FrameDecoder()
    connection_state = {}
    associated_seq = 0
    try:
        while True:
            try:
                data = conn.recv(
                    protocol.HEADER_LEN + protocol.MAX_PAYLOAD + protocol.CRC_LEN
                )
            except OSError:
                return
            if not data:
                return
            try:
                frames = decoder.feed(data)
            except protocol.ProtocolError as exc:
                frames = exc.frames
                decode_error = exc
            else:
                decode_error = None
            finished_connection = False
            for frame in frames:
                if finished_connection:
                    _send_error(
                        conn,
                        frame[1],
                        RequestFailure("INTEGRITY_FAIL", "frame after AUDIO_END"),
                    )
                    return
                associated_seq = frame[1]
                try:
                    finished = _handle_frame(conn, frame, cfg, connection_state)
                except RequestFailure as exc:
                    _send_error(conn, associated_seq, exc)
                    return
                except OSError:
                    return
                except Exception:
                    _send_error(
                        conn,
                        associated_seq,
                        RequestFailure("UPSTREAM_ERROR", "internal processing failure"),
                    )
                    return
                if finished:
                    finished_connection = True
            if decode_error is not None:
                _send_error(
                    conn,
                    decode_error.seq,
                    RequestFailure(decode_error.code, decode_error.code),
                )
                return
            if finished_connection:
                return
    finally:
        session = connection_state.get("session")
        if session is not None:
            with session.condition:
                session.active_connections -= 1
                session.last_activity = time.monotonic()
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
    srv.bind((cfg.get("listen_host", "127.0.0.1"), args.port))
    srv.listen(16)
    while True:
        conn, _ = srv.accept()
        threading.Thread(target=handle_connection, args=(conn, cfg), daemon=True).start()


if __name__ == "__main__":
    main()
