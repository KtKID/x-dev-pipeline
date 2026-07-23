#!/usr/bin/env python3
"""Deterministic, stdlib-only evaluator for the self-contained voice-chain case."""

from __future__ import annotations

import argparse
import ast
import contextlib
import hashlib
import importlib.util
import json
import os
import pathlib
import signal
import shutil
import socket
import struct
import subprocess
import sys
import sysconfig
import tempfile
import threading
import time
import urllib.request
import wave
import zlib


MAGIC = b"\xa5\x5a"
T_HELLO, T_AUDIO_CHUNK, T_AUDIO_END, T_ACK, T_ERROR, T_TTS_CHUNK, T_TTS_END = range(1, 8)
HEADER_LEN = 11
CRC_LEN = 4
CHUNK = 3200
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
ORACLE_CASE = REPO_ROOT / "cases" / "voice-chain"


def encode_frame(frame_type: int, seq: int, payload: bytes = b"") -> bytes:
    body = struct.pack(">BII", frame_type, seq, len(payload)) + payload
    return MAGIC + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


class Decoder:
    def __init__(self) -> None:
        self.buffer = b""

    def feed(self, data: bytes) -> list[tuple[int, int, bytes]]:
        self.buffer += data
        frames: list[tuple[int, int, bytes]] = []
        while len(self.buffer) >= HEADER_LEN:
            if self.buffer[:2] != MAGIC:
                raise AssertionError("server emitted bad magic")
            frame_type, seq, payload_len = struct.unpack(">BII", self.buffer[2:HEADER_LEN])
            total = HEADER_LEN + payload_len + CRC_LEN
            if len(self.buffer) < total:
                break
            body = self.buffer[2:HEADER_LEN + payload_len]
            expected_crc = struct.unpack(">I", self.buffer[HEADER_LEN + payload_len:total])[0]
            if zlib.crc32(body) & 0xFFFFFFFF != expected_crc:
                raise AssertionError("server emitted bad crc")
            frames.append((frame_type, seq, self.buffer[HEADER_LEN:HEADER_LEN + payload_len]))
            self.buffer = self.buffer[total:]
        return frames


class Peer:
    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock
        self.sock.settimeout(4)
        self.decoder = Decoder()
        self.pending: list[tuple[int, int, bytes]] = []

    def recv(self, timeout: float = 4) -> tuple[int, int, bytes]:
        self.sock.settimeout(timeout)
        while not self.pending:
            data = self.sock.recv(65536)
            if not data:
                raise ConnectionError("server closed")
            self.pending.extend(self.decoder.feed(data))
        return self.pending.pop(0)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_port(port: int, process: subprocess.Popen[bytes], timeout: float = 5) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            out = process.stdout.read().decode(errors="replace") if process.stdout else ""
            raise RuntimeError(f"process exited before listen: {out[-1000:]}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                return
        except OSError:
            time.sleep(0.03)
    raise TimeoutError(f"port {port} did not open")


class Stack:
    def __init__(self, fixture: pathlib.Path, timeout_ms: int = 500, retry_5xx: int = 1) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="voice-chain-eval-")
        self.root = pathlib.Path(self.temp.name) / "fixture"
        shutil.copytree(ORACLE_CASE / "fixture", self.root)
        shutil.rmtree(self.root / "backend")
        shutil.copytree(fixture / "backend", self.root / "backend")
        self.backend = self.root / "backend"
        self.mock = self.root / "mock-services"
        self.trace = self.root / "mock-trace.jsonl"
        mock_script = self.mock / "mock_services.py"
        mock_source = mock_script.read_text(encoding="utf-8")
        mock_source = mock_source.replace("import json\n", "import json\nimport os\n", 1)
        mock_source = mock_source.replace(
            "    def do_POST(self):\n        body = self._body()\n",
            "    def do_POST(self):\n"
            "        body = self._body()\n"
            "        trace_path = os.environ.get('VOICE_CHAIN_EVAL_TRACE')\n"
            "        if trace_path:\n"
            "            with open(trace_path, 'a', encoding='utf-8') as trace:\n"
            "                trace.write(self.path + '\\n')\n",
            1,
        )
        mock_script.write_text(mock_source, encoding="utf-8")
        self.mock_port = free_port()
        self.backend_port = free_port()
        while self.backend_port == self.mock_port:
            self.backend_port = free_port()
        cfg = {
            "listen_host": "127.0.0.1",
            "mock_base_url": f"http://127.0.0.1:{self.mock_port}",
            "service_timeout_ms": timeout_ms,
            "retry_max_5xx": retry_5xx,
        }
        self.config = self.backend / "eval-config.json"
        self.config.write_text(json.dumps(cfg), encoding="utf-8")
        self.processes: list[subprocess.Popen[bytes]] = []

    def start(self) -> "Stack":
        try:
            mock_env = dict(os.environ)
            mock_env["VOICE_CHAIN_EVAL_TRACE"] = str(self.trace)
            mock = subprocess.Popen(
                [sys.executable, "mock_services.py", "--port", str(self.mock_port)],
                cwd=self.mock,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=mock_env,
                start_new_session=True,
            )
            self.processes.append(mock)
            wait_port(self.mock_port, mock)
            backend = subprocess.Popen(
                [sys.executable, "app.py", "--port", str(self.backend_port), "--config", str(self.config)],
                cwd=self.backend,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            self.processes.append(backend)
            wait_port(self.backend_port, backend)
            return self
        except Exception:
            self.close()
            raise

    def connect(self) -> Peer:
        return Peer(socket.create_connection(("127.0.0.1", self.backend_port), timeout=2))

    def control(self, payload: dict[str, object]) -> None:
        raw = json.dumps(payload).encode()
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.mock_port}/control",
            data=raw,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            assert response.status == 200

    def trace_count(self, service: str) -> int:
        if not self.trace.is_file():
            return 0
        return self.trace.read_text(encoding="utf-8").splitlines().count(f"/{service}")

    def close(self) -> None:
        for process in reversed(self.processes):
            if process.poll() is None:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGTERM)
        for process in reversed(self.processes):
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=2)
        self.temp.cleanup()

    def __enter__(self) -> "Stack":
        return self.start()

    def __exit__(self, *_args: object) -> None:
        self.close()


def jdump(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False).encode()


def chunks(raw: bytes) -> list[bytes]:
    return [raw[index:index + CHUNK] for index in range(0, len(raw), CHUNK)]


def hello(peer: Peer, session_id: str) -> int:
    peer.sock.sendall(encode_frame(T_HELLO, 0, jdump({"device_id": "hidden-grader", "session_id": session_id})))
    frame = peer.recv()
    assert frame[0] == T_ACK and frame[1] == 0, frame
    return int(json.loads(frame[2])["last_seq"])


def send_upload(
    peer: Peer,
    raw: bytes,
    pipeline: bool = True,
    start_seq: int = 1,
    sha256: str | None = None,
) -> tuple[dict[str, object] | None, list[tuple[int, int, bytes]], float]:
    parts = chunks(raw)
    outbound = [encode_frame(T_AUDIO_CHUNK, index, part) for index, part in enumerate(parts, 1) if index >= start_seq]
    if pipeline:
        peer.sock.sendall(b"".join(outbound))
        for index in range(start_seq, len(parts) + 1):
            frame = peer.recv()
            assert frame[0] == T_ACK and frame[1] == index and frame[2] == b"", frame
    else:
        for index, frame_bytes in enumerate(outbound, start_seq):
            peer.sock.sendall(frame_bytes)
            frame = peer.recv()
            assert frame[0] == T_ACK and frame[1] == index, frame
    end = jdump({"total_chunks": len(parts), "sha256": sha256 or hashlib.sha256(raw).hexdigest()})
    started = time.monotonic()
    peer.sock.sendall(encode_frame(T_AUDIO_END, len(parts), end))
    first = peer.recv(timeout=6)
    elapsed = time.monotonic() - started
    if first[0] == T_ERROR:
        return None, [first], elapsed
    assert first[0] == T_ACK and first[1] == len(parts), first
    ack = json.loads(first[2])
    downlink: list[tuple[int, int, bytes]] = []
    while True:
        frame = peer.recv(timeout=4)
        downlink.append(frame)
        if frame[0] in (T_TTS_END, T_ERROR):
            break
    return ack, downlink, elapsed


def pcm_from_wav(path: pathlib.Path) -> bytes:
    with wave.open(str(path), "rb") as source:
        assert source.getnchannels() == 1
        assert source.getsampwidth() == 2
        assert source.getframerate() == 16000
        return source.readframes(source.getnframes())


def check_end_integrity(payload: bytes, pcm: bytes, chunk_count: int) -> bool:
    digest = hashlib.sha256(pcm).hexdigest()
    if payload == bytes.fromhex(digest) or payload.decode(errors="ignore").strip() == digest:
        return True
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(value, dict):
        return False
    supplied = value.get("sha256", value.get("digest"))
    count = value.get("total_chunks", value.get("chunks", chunk_count))
    return supplied == digest and count == chunk_count


class Checks:
    def __init__(self, workspace: pathlib.Path) -> None:
        self.workspace = workspace
        self.fixture = workspace / "fixture"
        self.details: dict[str, tuple[bool, str]] = {}
        self.shared: dict[str, object] = {}

    def record(self, key: str, fn) -> None:
        try:
            evidence = fn()
            self.details[key] = (True, str(evidence or "check passed"))
        except Exception as exc:  # independent checks should all finish
            self.details[key] = (False, f"{type(exc).__name__}: {exc}")

    def success_probe(self) -> dict[str, object]:
        with Stack(self.fixture) as stack:
            raw = (stack.root / "assets" / "ask_weather.wav").read_bytes()
            peer = stack.connect()
            assert hello(peer, "success") == 0
            ack, frames, _elapsed = send_upload(peer, raw, pipeline=True)
            assert ack is not None
            required_ack = {"ok": True, "text": "今天天气怎么样", "reply": "今天晴，气温二十六度"}
            assert all(ack.get(key) == value for key, value in required_ack.items()), ack
            tts_chunks = [frame for frame in frames if frame[0] == T_TTS_CHUNK]
            assert frames[-1][0] == T_TTS_END
            pcm = b"".join(frame[2] for frame in tts_chunks)
            result = {
                "stack": stack,
                "ack": ack,
                "frames": frames,
                "pcm": pcm,
                "raw": raw,
                "upload": (stack.backend / "sessions" / "success" / "upload.wav").read_bytes(),
                "reply": (stack.backend / "sessions" / "success" / "reply.wav").read_bytes(),
                "expected_reply": (stack.root / "assets" / "tts_weather.wav").read_bytes(),
            }
            return {key: value for key, value in result.items() if key != "stack"}

    def protocol_module(self) -> str:
        with Stack(self.fixture) as stack:
            peer = stack.connect()
            hello_wire = encode_frame(T_HELLO, 0, jdump({"device_id": "split-client", "session_id": "stream"}))
            for boundary in (1, 4, 9, len(hello_wire)):
                start = 0 if boundary == 1 else (1 if boundary == 4 else (4 if boundary == 9 else 9))
                peer.sock.sendall(hello_wire[start:boundary])
            assert peer.recv()[:2] == (T_ACK, 0)
            raw = (stack.root / "assets" / "ask_weather.wav").read_bytes()
            parts = chunks(raw)
            glued = encode_frame(T_AUDIO_CHUNK, 1, parts[0]) + encode_frame(T_AUDIO_CHUNK, 2, parts[1])
            peer.sock.sendall(glued[:7])
            peer.sock.sendall(glued[7:])
            assert peer.recv()[:2] == (T_ACK, 1)
            assert peer.recv()[:2] == (T_ACK, 2)
        return "real TCP backend handled split HELLO and glued/split AUDIO_CHUNK frames"

    def protocol_errors(self) -> str:
        cases = {
            "BAD_MAGIC": b"\x00\x00" + encode_frame(T_HELLO, 0)[2:],
            "BAD_CRC": encode_frame(T_HELLO, 0)[:-1] + bytes([encode_frame(T_HELLO, 0)[-1] ^ 1]),
            "PAYLOAD_TOO_LARGE": MAGIC + struct.pack(">BII", T_HELLO, 0, 262145),
        }
        with Stack(self.fixture) as stack:
            for index, (expected, raw) in enumerate(cases.items()):
                peer = stack.connect()
                peer.sock.sendall(raw)
                frame = peer.recv()
                assert frame[0] == T_ERROR and json.loads(frame[2])["code"] == expected, (expected, frame)
                peer.sock.settimeout(1)
                try:
                    closed = peer.sock.recv(1) == b""
                except (ConnectionResetError, BrokenPipeError):
                    closed = True
                assert closed, f"connection stayed open after {expected}"
                peer.sock.close()
        return "all three protocol error codes returned and connections closed"

    def success(self) -> str:
        data = self.success_probe()
        self.shared["success"] = data
        frames = data["frames"]
        assert isinstance(frames, list) and frames
        return "pipelined chunks acknowledged; AUDIO_END returned exact success payload"

    def upload_bytes(self) -> str:
        data = self.shared.get("success") or self.success_probe()
        assert data["upload"] == data["raw"]
        return f"upload.wav matched {len(data['raw'])} input bytes"

    def resume(self) -> str:
        with Stack(self.fixture) as stack:
            raw = (stack.root / "assets" / "ask_time.wav").read_bytes()
            parts = chunks(raw)
            first = stack.connect()
            assert hello(first, "resume") == 0
            first.sock.sendall(encode_frame(T_AUDIO_CHUNK, 1, parts[0]) + encode_frame(T_AUDIO_CHUNK, 2, parts[1]))
            assert first.recv()[:2] == (T_ACK, 1)
            assert first.recv()[:2] == (T_ACK, 2)
            first.sock.close()
            second = stack.connect()
            assert hello(second, "resume") == 2
            ack, _frames, _elapsed = send_upload(second, raw, start_seq=3)
            assert ack and ack["text"] == "现在几点了"
            assert (stack.backend / "sessions" / "resume" / "upload.wav").read_bytes() == raw
        return "HELLO last_seq=2 and resumed upload completed"

    def integrity_failure(self) -> str:
        with Stack(self.fixture) as stack:
            raw = (stack.root / "assets" / "ask_weather.wav").read_bytes()
            peer = stack.connect()
            hello(peer, "bad-sha")
            ack, frames, _elapsed = send_upload(peer, raw, sha256="0" * 64)
            assert ack is None
            assert json.loads(frames[0][2])["code"] == "INTEGRITY_FAIL"
            assert not (stack.backend / "sessions" / "bad-sha" / "reply.wav").exists()
            assert all(stack.trace_count(service) == 0 for service in ("asr", "llm", "tts"))
        return "bad digest produced INTEGRITY_FAIL, no reply.wav, and zero upstream calls"

    def orchestration(self) -> str:
        data = self.shared.get("success") or self.success_probe()
        assert data["reply"] == data["expected_reply"]
        assert data["ack"]["text"] == "今天天气怎么样"
        assert data["ack"]["reply"] == "今天晴，气温二十六度"
        return "ASR/LLM outputs and TTS WAV matched deterministic fixtures"

    def timeout(self) -> str:
        observed: dict[str, float] = {}
        for service in ("asr", "llm", "tts"):
            with Stack(self.fixture, timeout_ms=120) as stack:
                stack.control({"service": service, "hang_ms": 900})
                raw = (stack.root / "assets" / "ask_weather.wav").read_bytes()
                peer = stack.connect()
                hello(peer, f"timeout-{service}")
                ack, frames, elapsed = send_upload(peer, raw)
                assert ack is None and json.loads(frames[0][2])["code"] == "UPSTREAM_TIMEOUT"
                assert elapsed < 1.2, (service, elapsed)
                assert stack.trace_count(service) == 1, (service, stack.trace_count(service))
                observed[service] = elapsed
        return f"all stages returned UPSTREAM_TIMEOUT with 120ms config: {observed}"

    def retry_5xx(self) -> str:
        for service in ("asr", "llm", "tts"):
            with Stack(self.fixture, retry_5xx=1) as stack:
                stack.control({"service": service, "mode": "500"})
                raw = (stack.root / "assets" / "ask_weather.wav").read_bytes()
                peer = stack.connect()
                hello(peer, f"retry-{service}")
                ack, _frames, _elapsed = send_upload(peer, raw)
                assert ack and ack["ok"] is True
                assert stack.trace_count(service) == 2, (service, stack.trace_count(service))
        return "single injected 500 recovered at ASR, LLM, and TTS with retry_max_5xx=1"

    def no_retry_4xx(self) -> str:
        observed: dict[str, float] = {}
        for service in ("asr", "llm", "tts"):
            stack = Stack(self.fixture, retry_5xx=100000)
            try:
                fixture_path = stack.mock / "fixtures.json"
                fixture_data = json.loads(fixture_path.read_text(encoding="utf-8"))
                if service == "asr":
                    weather = (stack.root / "assets" / "ask_weather.wav").read_bytes()
                    fixture_data["asr"].pop(hashlib.sha256(weather).hexdigest())
                elif service == "llm":
                    fixture_data["llm"].pop("今天天气怎么样")
                else:
                    fixture_data["tts"].pop("今天晴，气温二十六度")
                fixture_path.write_text(json.dumps(fixture_data, ensure_ascii=False), encoding="utf-8")
                stack.start()
                raw = (stack.root / "assets" / "ask_weather.wav").read_bytes()
                peer = stack.connect()
                hello(peer, f"4xx-{service}")
                ack, frames, elapsed = send_upload(peer, raw)
                assert ack is None and json.loads(frames[0][2])["code"] == "UPSTREAM_ERROR"
                assert elapsed < 1.0, (service, elapsed)
                assert stack.trace_count(service) == 1, (service, stack.trace_count(service))
                observed[service] = elapsed
            finally:
                stack.close()
        return f"ASR/LLM/TTS 4xx returned promptly with retry_max_5xx=100000: {observed}"

    def dynamic_config(self) -> str:
        with Stack(self.fixture, timeout_ms=137, retry_5xx=0) as stack:
            assert stack.mock_port != 9100
            raw = (stack.root / "assets" / "ask_weather.wav").read_bytes()
            stack.control({"service": "asr", "mode": "500"})
            peer = stack.connect()
            hello(peer, "dynamic-retry")
            ack, frames, _elapsed = send_upload(peer, raw)
            assert ack is None and json.loads(frames[0][2])["code"] == "UPSTREAM_ERROR"
            assert stack.trace_count("asr") == 1
        timeout_observed: dict[int, float] = {}
        for timeout_ms in (80, 400):
            with Stack(self.fixture, timeout_ms=timeout_ms, retry_5xx=0) as timeout_stack:
                timeout_stack.control({"service": "asr", "hang_ms": 900})
                raw = (timeout_stack.root / "assets" / "ask_weather.wav").read_bytes()
                peer = timeout_stack.connect()
                hello(peer, f"dynamic-timeout-{timeout_ms}")
                ack, frames, elapsed = send_upload(peer, raw)
                assert ack is None and json.loads(frames[0][2])["code"] == "UPSTREAM_TIMEOUT"
                assert timeout_stack.trace_count("asr") == 1
                timeout_observed[timeout_ms] = elapsed
        assert 0.04 <= timeout_observed[80] <= 0.35, timeout_observed
        assert 0.25 <= timeout_observed[400] <= 0.75, timeout_observed
        assert timeout_observed[400] - timeout_observed[80] >= 0.2, timeout_observed
        return f"dynamic port {stack.mock_port}, retry=0, and timeout tiers affected behavior: {timeout_observed}"

    def downlink_order(self) -> str:
        data = self.shared.get("success") or self.success_probe()
        frames = data["frames"]
        tts = [frame for frame in frames if frame[0] == T_TTS_CHUNK]
        assert [frame[1] for frame in tts] == list(range(1, len(tts) + 1))
        assert frames[-1][0] == T_TTS_END and frames[-1][1] == len(tts)
        return f"ACK preceded {len(tts)} ordered TTS_CHUNK frames and TTS_END"

    def downlink_pcm(self) -> str:
        data = self.shared.get("success") or self.success_probe()
        expected = pcm_from_wav(self.fixture / "assets" / "tts_weather.wav")
        assert data["pcm"] == expected
        frames = data["frames"]
        tts = [frame for frame in frames if frame[0] == T_TTS_CHUNK]
        assert check_end_integrity(frames[-1][2], expected, len(tts))
        return f"downlink matched {len(expected)} PCM bytes with verifiable digest"

    def concurrency(self) -> str:
        with Stack(self.fixture) as stack:
            cases = [
                ("a", "ask_weather.wav", "今天天气怎么样", "今天晴，气温二十六度", "tts_weather.wav"),
                ("b", "ask_time.wav", "现在几点了", "现在是下午三点", "tts_time.wav"),
            ]
            outputs: dict[str, tuple[dict[str, object], bytes]] = {}
            errors: list[str] = []

            def worker(session: str, filename: str, expected_text: str, expected_reply: str, tts_name: str) -> None:
                try:
                    raw = (stack.root / "assets" / filename).read_bytes()
                    peer = stack.connect()
                    hello(peer, session)
                    ack, frames, _elapsed = send_upload(peer, raw)
                    assert ack and ack["text"] == expected_text
                    assert ack["reply"] == expected_reply
                    outputs[session] = (ack, b"".join(frame[2] for frame in frames if frame[0] == T_TTS_CHUNK))
                except Exception as exc:
                    errors.append(f"{session}: {exc}")

            threads = [threading.Thread(target=worker, args=item) for item in cases]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=10)
            assert not errors, errors
            assert set(outputs) == {"a", "b"}
            for session, filename, expected_text, expected_reply, tts_name in cases:
                session_dir = stack.backend / "sessions" / session
                expected_tts = (stack.root / "assets" / tts_name).read_bytes()
                required_ack = {"ok": True, "text": expected_text, "reply": expected_reply}
                assert all(outputs[session][0].get(key) == value for key, value in required_ack.items())
                assert outputs[session][1] == pcm_from_wav(stack.root / "assets" / tts_name)
                assert session_dir.joinpath("upload.wav").read_bytes() == (stack.root / "assets" / filename).read_bytes()
                assert session_dir.joinpath("reply.wav").read_bytes() == expected_tts
        return "two concurrent sessions matched exact ACK, upload, reply.wav, and PCM oracles"

    def disconnect_isolation(self) -> str:
        # The large deterministic TTS body exists only to force a real socket
        # write reset. Give its upstream fetch an independent budget so this
        # assertion measures downlink isolation instead of service timeout.
        stack = Stack(self.fixture, timeout_ms=10_000)
        try:
            large_reply = stack.root / "assets" / "tts_weather.wav"
            with wave.open(str(large_reply), "wb") as target:
                target.setnchannels(1)
                target.setsampwidth(2)
                target.setframerate(16000)
                target.writeframes(b"\x00\x00" * (8 * 1024 * 1024))
            stack.start()
            raw = (stack.root / "assets" / "ask_weather.wav").read_bytes()
            first = stack.connect()
            hello(first, "drop")
            parts = chunks(raw)
            first.sock.sendall(b"".join(encode_frame(T_AUDIO_CHUNK, i, part) for i, part in enumerate(parts, 1)))
            for i in range(1, len(parts) + 1):
                assert first.recv()[:2] == (T_ACK, i)
            end = jdump({"total_chunks": len(parts), "sha256": hashlib.sha256(raw).hexdigest()})
            first.sock.sendall(encode_frame(T_AUDIO_END, len(parts), end))
            assert first.recv()[0] == T_ACK
            first.sock.close()
            time.sleep(0.1)
            second_raw = (stack.root / "assets" / "ask_time.wav").read_bytes()
            second = stack.connect()
            hello(second, "after-drop")
            ack, _frames, _elapsed = send_upload(second, second_raw)
            assert ack and ack["text"] == "现在几点了"
            assert stack.processes[-1].poll() is None
        finally:
            stack.close()
        return "backend stayed alive after a forced large downlink reset and completed a second session"

    def stdlib_only(self) -> str:
        local = {path.stem for path in (self.fixture / "backend").glob("*.py")}
        stdlib_root = pathlib.Path(sysconfig.get_paths()["stdlib"]).resolve()
        external: set[str] = set()
        for path in (self.fixture / "backend").glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    roots = [alias.name.split(".")[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    roots = [node.module.split(".")[0]]
                else:
                    continue
                for root in roots:
                    if root in local:
                        continue
                    spec = importlib.util.find_spec(root)
                    origin = None if spec is None else spec.origin
                    if origin in (None, "built-in", "frozen"):
                        if spec is None:
                            external.add(root)
                        continue
                    resolved = pathlib.Path(origin).resolve()
                    if stdlib_root not in resolved.parents or "site-packages" in resolved.parts:
                        external.add(root)
        assert not external, sorted(external)
        return "backend imports resolve to stdlib or local modules"

    def spec_document(self) -> str:
        spec_path = self.workspace / "docs" / "spec" / "voice-chain" / "spec.md"
        assert spec_path.is_file(), "docs/spec/voice-chain/spec.md missing"
        body = spec_path.read_text(encoding="utf-8")
        assert "> spec_version: 3" in body
        assert "待确认" not in body or "待确认：无" in body
        for token in ("影响边界", "判断依据", "建模覆盖", "验收清单", "SC_01", "fixture/backend/app.py", "fixture/backend/protocol.py", "fixture/backend/http_client.py", "fixture/backend/audio.py"):
            assert token in body, token
        tool = self.workspace / "tools" / "xdev.py"
        assert tool.is_file(), "tools/xdev.py missing"
        result = subprocess.run(
            [sys.executable, str(tool), "validate", str(spec_path.parent), "--json"],
            cwd=self.workspace,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=20,
        )
        assert result.returncode == 0, result.stdout.decode(errors="replace")[-2000:]
        return f"{spec_path} is a validated, ready spec3 contract with stable IDs and four backend modules"

    def req_checklist(self) -> str:
        spec_root = self.workspace / "docs" / "spec" / "voice-chain"
        checklists = sorted(spec_root.glob("tasks/*/dev-checklist.md"))
        assert checklists, "dev-checklist.md missing"
        scenario_refs: set[str] = set()
        for path in checklists:
            body = path.read_text(encoding="utf-8")
            scenario_refs.update(__import__("re").findall(r"SC_\d{2}", body))
            assert "risk:" in body and "Scenario IDs" in body
        spec_path = spec_root / "spec.md"
        assert spec_path.is_file()
        spec_refs = set(__import__("re").findall(r"Scenario (SC_\d{2})", spec_path.read_text(encoding="utf-8")))
        assert spec_refs and spec_refs <= scenario_refs, (sorted(spec_refs), sorted(scenario_refs))
        tool = self.workspace / "tools" / "xdev.py"
        assert tool.is_file(), "tools/xdev.py missing"
        for checklist in checklists:
            result = subprocess.run([sys.executable, str(tool), "validate", str(checklist.parent), "--json"], cwd=self.workspace, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20)
            assert result.returncode == 0, result.stdout.decode(errors="replace")[-2000:]
        return f"{len(checklists)} checklist(s) cover {len(spec_refs)} scenarios and validate"

    def verify_evidence(self) -> str:
        spec_root = self.workspace / "docs" / "spec" / "voice-chain"
        reports = sorted(spec_root.glob("tasks/*/dev-report*.md"))
        assert reports, "dev-report missing"
        body = "\n".join(path.read_text(encoding="utf-8") for path in reports)
        assert body.count("```verify") >= 3
        assert "mode: auto" in body
        assert any(token in body for token in ("unittest", "test", "smoke"))
        assert "e2e" in body.lower() or "mode: manual" in body
        tool = self.workspace / "tools" / "xdev.py"
        assert tool.is_file(), "tools/xdev.py missing"
        task_dirs = sorted({path.parent for path in reports})
        for task_dir in task_dirs:
            result = subprocess.run(
                [sys.executable, str(tool), "verify", str(task_dir), "--json"],
                cwd=self.workspace,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=120,
            )
            assert result.returncode == 0, result.stdout.decode(errors="replace")[-4000:]
        return f"{len(reports)} dev-report file(s) replayed successfully through xdev verify"

    def hygiene(self) -> str:
        leftovers = []
        for path in self.workspace.rglob("*.pid"):
            leftovers.append(str(path.relative_to(self.workspace)))
        assert not leftovers, leftovers
        assert not (self.workspace / ".git").exists()
        for relative in ("task", "fixture/device-sim", "fixture/mock-services", "fixture/assets"):
            candidate = self.workspace / relative
            oracle = ORACLE_CASE / relative
            candidate_files = sorted(path.relative_to(candidate) for path in candidate.rglob("*") if path.is_file())
            oracle_files = sorted(path.relative_to(oracle) for path in oracle.rglob("*") if path.is_file())
            assert candidate_files == oracle_files, f"read-only tree changed: {relative}"
            for item in oracle_files:
                assert (candidate / item).read_bytes() == (oracle / item).read_bytes(), f"read-only file changed: {relative}/{item}"
        return "read-only task/oracles match frozen case; no pid files or nested git state"


EXPECTATIONS = [
    ("流式解码同时处理半包、粘包和连续多帧。", "protocol_module"),
    ("协议错误返回 BAD_MAGIC、BAD_CRC、PAYLOAD_TOO_LARGE 并关闭连接。", "protocol_errors"),
    ("HELLO、流水线 AUDIO_CHUNK、AUDIO_END 与 ACK 顺序正确。", "success"),
    ("upload.wav 与输入逐字节一致，AUDIO_END ACK 含 ok、text、reply。", "upload_bytes"),
    ("同一 session_id 断线续传并完成全链路。", "resume"),
    ("SHA-256 不匹配产生 INTEGRITY_FAIL 并跳过回复产物。", "integrity_failure"),
    ("ASR、LLM、TTS 成功链路产出正确文本与 reply.wav。", "orchestration"),
    ("上游超时按配置产生 UPSTREAM_TIMEOUT。", "timeout"),
    ("5xx 按 retry_max_5xx 重试并可恢复。", "retry_5xx"),
    ("4xx 零重试并产生 UPSTREAM_ERROR。", "no_retry_4xx"),
    ("动态服务地址、超时和重试配置生效。", "dynamic_config"),
    ("AUDIO_END ACK 后下发连续 TTS_CHUNK 与 TTS_END。", "downlink_order"),
    ("下行载荷为精确 PCM，并带可验证完整性摘要。", "downlink_pcm"),
    ("两台设备并发时会话、文件、结果与 PCM 隔离。", "concurrency"),
    ("下行断连后端保持存活并服务其他会话。", "disconnect_isolation"),
    ("backend 运行时代码只依赖 Python 标准库与本地模块。", "stdlib_only"),
    ("spec3 文档完整、可交接并使用稳定 Scenario ID。", "spec_document"),
    ("req3 checklist 完整覆盖 Scenario 且通过机械校验。", "req_checklist"),
    ("dev-report 提供可复跑的 unit、smoke、e2e 证据。", "verify_evidence"),
    ("运行产物保持隔离且无后台 pid 残留。", "hygiene"),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=pathlib.Path)
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    checks = Checks(workspace)
    for _text, method in EXPECTATIONS:
        checks.record(method, getattr(checks, method))
    expectations = []
    for text, method in EXPECTATIONS:
        passed, evidence = checks.details[method]
        expectations.append({"text": text, "passed": passed, "evidence": evidence})
    passed = sum(1 for item in expectations if item["passed"])
    critical_methods = {method for _text, method in EXPECTATIONS[:19]}
    critical_passed = all(checks.details[name][0] for name in critical_methods)
    result = {
        "expectations": expectations,
        "summary": {"passed": passed, "failed": len(expectations) - passed, "total": len(expectations), "pass_rate": passed / len(expectations)},
        "quality_score": passed * 5,
        "critical_gate_passed": critical_passed,
        "execution_metrics": {"total_tool_calls": 0, "errors_encountered": len(expectations) - passed},
        "eval_feedback": {"suggestions": [], "overall": "Deterministic local protocol, integration, concurrency, and artifact checks."},
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if passed >= 18 and critical_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
