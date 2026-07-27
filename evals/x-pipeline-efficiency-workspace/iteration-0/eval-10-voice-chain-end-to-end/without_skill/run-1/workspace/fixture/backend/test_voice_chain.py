import hashlib
import io
import json
import os
import pathlib
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
import wave
import zlib
from unittest import mock

import app
import audio
import protocol


BACKEND = pathlib.Path(__file__).resolve().parent
FIXTURE = BACKEND.parent
ASSETS = FIXTURE / "assets"

# Independent wire/audio oracle copied from task/specs, intentionally separate from production.
W_MAGIC = b"\xa5\x5a"
W_HELLO, W_AUDIO_CHUNK, W_AUDIO_END, W_ACK, W_ERROR, W_TTS_CHUNK, W_TTS_END = range(1, 8)
W_HEADER_LEN, W_CRC_LEN, W_MAX_PAYLOAD, W_AUDIO_BLOCK_SIZE = 11, 4, 262144, 3200


def wire_encode(frame_type, seq, payload=b""):
    body = struct.pack(">BII", frame_type, seq, len(payload)) + payload
    return W_MAGIC + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


class WireDecoder:
    def __init__(self):
        self.buffer = b""

    def feed(self, data):
        self.buffer += data
        frames = []
        while len(self.buffer) >= W_HEADER_LEN:
            if self.buffer[:2] != W_MAGIC:
                raise AssertionError("bad server magic")
            frame_type, seq, payload_len = struct.unpack(">BII", self.buffer[2:W_HEADER_LEN])
            if payload_len > W_MAX_PAYLOAD:
                raise AssertionError("server payload exceeds wire maximum")
            total = W_HEADER_LEN + payload_len + W_CRC_LEN
            if len(self.buffer) < total:
                break
            body = self.buffer[2:W_HEADER_LEN + payload_len]
            expected_crc, = struct.unpack(">I", self.buffer[W_HEADER_LEN + payload_len:total])
            if zlib.crc32(body) & 0xFFFFFFFF != expected_crc:
                raise AssertionError("bad server CRC")
            frames.append((frame_type, seq, self.buffer[W_HEADER_LEN:W_HEADER_LEN + payload_len]))
            self.buffer = self.buffer[total:]
        return frames


def oracle_wav_pcm(raw):
    with wave.open(io.BytesIO(raw), "rb") as source:
        if (source.getnchannels(), source.getsampwidth(), source.getframerate(),
                source.getcomptype()) != (1, 2, 16000, "NONE"):
            raise AssertionError("fixture is outside the device PCM contract")
        return source.readframes(source.getnframes())


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_port(port, proc, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(proc.stderr.read())
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                return
        except OSError:
            time.sleep(0.02)
    raise TimeoutError(f"port {port} did not open")


def recv_frame(sock, decoder, pending):
    while not pending:
        raw = sock.recv(W_MAX_PAYLOAD + W_HEADER_LEN + W_CRC_LEN)
        if not raw:
            raise ConnectionError("server closed")
        pending.extend(decoder.feed(raw))
    return pending.pop(0)


def hello(sock, session_id, device_id="test-device"):
    decoder, pending = WireDecoder(), []
    body = json.dumps({"device_id": device_id, "session_id": session_id}).encode()
    sock.sendall(wire_encode(W_HELLO, 0, body))
    frame = recv_frame(sock, decoder, pending)
    return decoder, pending, frame


def upload_frames(raw):
    size = W_AUDIO_BLOCK_SIZE
    return [raw[i:i + size] for i in range(0, len(raw), size)]


def send_upload(sock, session_id, raw, device_id="test-device", pipeline=False):
    decoder, pending, ack = hello(sock, session_id, device_id)
    if ack[0] != W_ACK:
        return decoder, pending, ack
    last_seq = json.loads(ack[2])["last_seq"]
    chunks = upload_frames(raw)
    frames = [
        wire_encode(W_AUDIO_CHUNK, seq, chunk)
        for seq, chunk in enumerate(chunks, 1)
        if seq > last_seq
    ]
    end = json.dumps({
        "total_chunks": len(chunks),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }).encode()
    frames.append(wire_encode(W_AUDIO_END, len(chunks), end))
    if pipeline:
        sock.sendall(b"".join(frames))
        for seq in range(last_seq + 1, len(chunks) + 1):
            chunk_ack = recv_frame(sock, decoder, pending)
            if chunk_ack[:2] != (W_ACK, seq) or chunk_ack[2]:
                raise AssertionError(f"bad chunk ACK: {chunk_ack}")
    else:
        for seq, frame in zip(range(last_seq + 1, len(chunks) + 1), frames[:-1]):
            sock.sendall(frame)
            chunk_ack = recv_frame(sock, decoder, pending)
            if chunk_ack[:2] != (W_ACK, seq) or chunk_ack[2]:
                raise AssertionError(f"bad chunk ACK: {chunk_ack}")
        sock.sendall(frames[-1])
    return decoder, pending, recv_frame(sock, decoder, pending)


def receive_downlink(sock, decoder, pending):
    chunks = []
    while True:
        frame = recv_frame(sock, decoder, pending)
        if frame[0] == W_TTS_CHUNK:
            if frame[1] != len(chunks) + 1:
                raise AssertionError(f"bad TTS sequence: {frame[1]}")
            chunks.append(frame[2])
            continue
        if frame[0] != W_TTS_END:
            raise AssertionError(f"unexpected frame: {frame}")
        return b"".join(chunks), frame


def assert_closed(testcase, sock):
    sock.settimeout(1)
    testcase.assertEqual(b"", sock.recv(1), "server must close after ERROR")


class ProtocolAndAudioTests(unittest.TestCase):
    def test_protocol_matches_fixed_wire_golden(self):
        golden = bytes.fromhex("a55a0100000000000000027b7d4bf217fe")
        self.assertEqual(golden, protocol.encode_frame(protocol.T_HELLO, 0, b"{}"))
        self.assertEqual([(1, 0, b"{}")], protocol.FrameDecoder().feed(golden))

    def test_streaming_decoder_handles_arbitrary_splits_and_sticky_frames(self):
        expected = [
            (protocol.T_HELLO, 0, b"{}"),
            (protocol.T_AUDIO_CHUNK, 1, b"abc"),
            (protocol.T_AUDIO_CHUNK, 2, b"defg"),
        ]
        wire = b"".join(protocol.encode_frame(*frame) for frame in expected)
        decoder = protocol.FrameDecoder()
        actual = []
        for byte in wire:
            actual.extend(decoder.feed(bytes([byte])))
        self.assertEqual(expected, actual)

    def test_protocol_errors_preserve_defined_codes(self):
        bad_magic = b"zz" + protocol.encode_frame(protocol.T_HELLO, 0)[2:]
        with self.assertRaisesRegex(protocol.ProtocolError, "BAD_MAGIC"):
            protocol.FrameDecoder().feed(bad_magic)

        bad_crc = bytearray(protocol.encode_frame(protocol.T_AUDIO_CHUNK, 7, b"x"))
        bad_crc[-1] ^= 1
        with self.assertRaises(protocol.ProtocolError) as caught:
            protocol.FrameDecoder().feed(bytes(bad_crc))
        self.assertEqual("BAD_CRC", caught.exception.code)
        self.assertEqual(7, caught.exception.seq)

        oversized = protocol.MAGIC + struct.pack(
            ">BII", protocol.T_AUDIO_CHUNK, 9, protocol.MAX_PAYLOAD + 1
        )
        with self.assertRaises(protocol.ProtocolError) as caught:
            protocol.FrameDecoder().feed(oversized)
        self.assertEqual("PAYLOAD_TOO_LARGE", caught.exception.code)
        self.assertEqual(9, caught.exception.seq)

    def test_wav_validation_and_short_pcm_tail(self):
        raw = (ASSETS / "tts_weather.wav").read_bytes()
        pcm = audio.wav_pcm(raw)
        self.assertEqual(oracle_wav_pcm(raw), pcm)
        self.assertEqual(3200, audio.AUDIO_BLOCK_SIZE)
        self.assertEqual(16000, audio.PCM_SAMPLE_RATE)
        chunks = list(audio.chunk_pcm(pcm, audio.AUDIO_BLOCK_SIZE))
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) == 3200 for chunk in chunks[:-1]))
        self.assertGreater(len(chunks[-1]), 0)
        self.assertLess(len(chunks[-1]), 3200)
        self.assertEqual(pcm, b"".join(chunks))

        buf = io.BytesIO()
        with wave.open(buf, "wb") as out:
            out.setnchannels(2)
            out.setsampwidth(2)
            out.setframerate(16000)
            out.writeframes(b"\0" * 16)
        with self.assertRaises(ValueError):
            audio.wav_pcm(buf.getvalue())


class PipelineUnitTests(unittest.TestCase):
    def setUp(self):
        self.cfg = {
            "mock_base_url": "http://127.0.0.1:1",
            "service_timeout_ms": 10,
            "retry_max_5xx": 1,
        }

    def test_5xx_exhaustion_honors_configured_retry_limit(self):
        with mock.patch.object(
            app.http_client, "post", side_effect=[(500, b""), (503, b"")]
        ) as post:
            with self.assertRaises(app.UpstreamFailure) as caught:
                app._service_post(self.cfg, "/asr", b"wav", "application/octet-stream")
        self.assertEqual("UPSTREAM_ERROR", caught.exception.code)
        self.assertEqual(2, post.call_count)

    def test_4xx_and_timeout_do_not_retry(self):
        with mock.patch.object(app.http_client, "post", return_value=(404, b"{}")) as post:
            with self.assertRaises(app.UpstreamFailure) as caught:
                app._service_post(self.cfg, "/asr", b"wav", "application/octet-stream")
        self.assertEqual("UPSTREAM_ERROR", caught.exception.code)
        self.assertEqual(1, post.call_count)

        with mock.patch.object(app.http_client, "post", side_effect=socket.timeout("late")) as post:
            with self.assertRaises(app.UpstreamFailure) as caught:
                app._service_post(self.cfg, "/asr", b"wav", "application/octet-stream")
        self.assertEqual("UPSTREAM_TIMEOUT", caught.exception.code)
        self.assertEqual(1, post.call_count)

    def test_http_total_deadline_rejects_slow_trickle(self):
        server = socket.socket()
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]

        def trickle():
            conn = None
            try:
                conn, _ = server.accept()
                request = b""
                while b"\r\n\r\n" not in request:
                    request += conn.recv(8192)
                conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 4\r\n\r\n")
                for byte in b"slow":
                    time.sleep(0.06)
                    conn.sendall(bytes([byte]))
            except OSError:
                pass
            finally:
                if conn is not None:
                    conn.close()
                server.close()

        thread = threading.Thread(target=trickle, daemon=True)
        thread.start()
        started = time.monotonic()
        with self.assertRaises(TimeoutError):
            app.http_client.post(
                f"http://127.0.0.1:{port}/slow", b"x", "application/octet-stream", 100
            )
        self.assertLess(time.monotonic() - started, 0.3)
        thread.join(timeout=1)

    def test_pipeline_order_payloads_and_content_types(self):
        calls = []
        reply_wav = (ASSETS / "tts_weather.wav").read_bytes()

        def fake_post(url, data, content_type, timeout_ms):
            calls.append((url.rsplit("/", 1)[-1], data, content_type, timeout_ms))
            if url.endswith("/asr"):
                return 200, json.dumps({"text": "今天天气怎么样"}).encode()
            if url.endswith("/llm"):
                return 200, json.dumps({"reply": "今天晴，气温二十六度"}).encode()
            return 200, reply_wav

        with mock.patch.object(app.http_client, "post", side_effect=fake_post):
            text, reply, got_wav, pcm = app.run_pipeline(self.cfg, b"upload-wav")
        self.assertEqual("今天天气怎么样", text)
        self.assertEqual("今天晴，气温二十六度", reply)
        self.assertEqual(reply_wav, got_wav)
        self.assertEqual(oracle_wav_pcm(reply_wav), pcm)
        self.assertEqual(["asr", "llm", "tts"], [call[0] for call in calls])
        self.assertEqual("application/octet-stream", calls[0][2])
        self.assertEqual(b"upload-wav", calls[0][1])
        self.assertEqual("application/json", calls[1][2])
        self.assertEqual({"text": "今天天气怎么样"}, json.loads(calls[1][1]))
        self.assertEqual("application/json", calls[2][2])
        self.assertEqual({"text": "今天晴，气温二十六度"}, json.loads(calls[2][1]))
        self.assertTrue(all(call[3] == 10 for call in calls))

    def test_each_upstream_failure_stops_the_pipeline(self):
        reply_wav = (ASSETS / "tts_weather.wav").read_bytes()
        successes = [
            (200, json.dumps({"text": "今天天气怎么样"}).encode()),
            (200, json.dumps({"reply": "今天晴，气温二十六度"}).encode()),
            (200, reply_wav),
        ]
        for target in range(3):
            for mode in ("4xx", "5xx", "timeout"):
                calls = []

                def fake_post(url, data, content_type, timeout_ms):
                    index = len(calls)
                    calls.append(url.rsplit("/", 1)[-1])
                    if index < target:
                        return successes[index]
                    if mode == "timeout":
                        raise socket.timeout("late")
                    return (400 if mode == "4xx" else 500), b"{}"

                with self.subTest(service=target, mode=mode):
                    with mock.patch.object(app.http_client, "post", side_effect=fake_post):
                        with self.assertRaises(app.UpstreamFailure) as caught:
                            app.run_pipeline(self.cfg, b"upload-wav")
                    expected_code = "UPSTREAM_TIMEOUT" if mode == "timeout" else "UPSTREAM_ERROR"
                    self.assertEqual(expected_code, caught.exception.code)
                    target_calls = 2 if mode == "5xx" else 1
                    self.assertEqual(target + target_calls, len(calls))
                    self.assertEqual(["asr", "llm", "tts"][:target], calls[:target])
                    self.assertTrue(all(name == ["asr", "llm", "tts"][target]
                                        for name in calls[target:]))


class ScriptedSocket:
    def __init__(self, incoming, fail_on_type=None):
        self.incoming = [incoming]
        self.sent = []
        self.fail_on_type = fail_on_type
        self.failed = False
        self.closed = False

    def recv(self, _size):
        return self.incoming.pop(0) if self.incoming else b""

    def sendall(self, data):
        frame = WireDecoder().feed(data)[0]
        if frame[0] == self.fail_on_type:
            self.failed = True
            raise BrokenPipeError("injected device disconnect")
        self.sent.append(data)

    def close(self):
        self.closed = True


class ConnectionIsolationUnitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.previous_cwd = os.getcwd()
        os.chdir(self.tmp.name)
        with app._sessions_lock:
            app._sessions.clear()
        self.cfg = {
            "listen_host": "127.0.0.1",
            "mock_base_url": "http://127.0.0.1:1",
            "service_timeout_ms": 100,
            "retry_max_5xx": 1,
        }

    def tearDown(self):
        os.chdir(self.previous_cwd)
        self.tmp.cleanup()

    def frames_for_upload(self, session_id, raw, end_total=None):
        hello_body = json.dumps({"device_id": session_id, "session_id": session_id}).encode()
        chunks = upload_frames(raw)
        frames = [wire_encode(W_HELLO, 0, hello_body)]
        frames.extend(wire_encode(W_AUDIO_CHUNK, seq, chunk)
                      for seq, chunk in enumerate(chunks, 1))
        total = len(chunks) if end_total is None else end_total
        end = json.dumps({"total_chunks": total,
                          "sha256": hashlib.sha256(raw).hexdigest()}).encode()
        frames.append(wire_encode(W_AUDIO_END, total, end))
        return b"".join(frames)

    def test_missing_chunk_returns_related_error_and_skips_upstream(self):
        raw = (ASSETS / "ask_weather.wav").read_bytes()
        hello_body = json.dumps({"device_id": "missing", "session_id": "missing"}).encode()
        first = upload_frames(raw)[0]
        end = json.dumps({"total_chunks": 2,
                          "sha256": hashlib.sha256(raw).hexdigest()}).encode()
        incoming = b"".join([
            wire_encode(W_HELLO, 0, hello_body),
            wire_encode(W_AUDIO_CHUNK, 1, first),
            wire_encode(W_AUDIO_END, 2, end),
        ])
        sock = ScriptedSocket(incoming)
        with mock.patch.object(app, "run_pipeline") as pipeline:
            app.handle_connection(sock, self.cfg)
        frames = WireDecoder().feed(b"".join(sock.sent))
        self.assertEqual([(W_ACK, 0), (W_ACK, 1), (W_ERROR, 2)],
                         [(frame[0], frame[1]) for frame in frames])
        self.assertEqual("INTEGRITY_FAIL", json.loads(frames[-1][2])["code"])
        pipeline.assert_not_called()
        self.assertTrue(sock.closed)

    def test_tts_write_failure_is_isolated_from_next_session(self):
        weather = (ASSETS / "ask_weather.wav").read_bytes()
        reply_wav = (ASSETS / "tts_weather.wav").read_bytes()
        pipeline_result = ("今天天气怎么样", "今天晴，气温二十六度",
                           reply_wav, oracle_wav_pcm(reply_wav))
        broken = ScriptedSocket(self.frames_for_upload("broken", weather), W_TTS_CHUNK)
        with mock.patch.object(app, "run_pipeline", return_value=pipeline_result):
            app.handle_connection(broken, self.cfg)
        self.assertTrue(broken.failed)
        self.assertTrue(broken.closed)

        healthy = ScriptedSocket(self.frames_for_upload("healthy", weather))
        with mock.patch.object(app, "run_pipeline", return_value=pipeline_result):
            app.handle_connection(healthy, self.cfg)
        frames = WireDecoder().feed(b"".join(healthy.sent))
        self.assertEqual(W_TTS_END, frames[-1][0])
        self.assertTrue(healthy.closed)


class VoiceChainE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = pathlib.Path(cls.tmp.name)
        cls.mock_port = free_port()
        cls.backend_port = free_port()
        cls.cfg = {
            "listen_host": "127.0.0.1",
            "mock_base_url": f"http://127.0.0.1:{cls.mock_port}",
            "service_timeout_ms": 120,
            "retry_max_5xx": 1,
        }
        cls.config_path = cls.root / "config.json"
        cls.config_path.write_text(json.dumps(cls.cfg))
        cls.mock = subprocess.Popen(
            [sys.executable, str(FIXTURE / "mock-services" / "mock_services.py"),
             "--port", str(cls.mock_port)],
            cwd=cls.root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        wait_port(cls.mock_port, cls.mock)
        cls.backend = subprocess.Popen(
            [sys.executable, str(BACKEND / "app.py"), "--port", str(cls.backend_port),
             "--config", str(cls.config_path)],
            cwd=cls.root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        wait_port(cls.backend_port, cls.backend)

    @classmethod
    def tearDownClass(cls):
        for proc in (cls.backend, cls.mock):
            proc.terminate()
        for proc in (cls.backend, cls.mock):
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)
        cls.tmp.cleanup()

    def setUp(self):
        self.control({"reset": True})

    def connect(self):
        sock = socket.create_connection(("127.0.0.1", self.backend_port), timeout=2)
        sock.settimeout(2)
        return sock

    def control(self, payload):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.mock_port}/control",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=2):
            pass

    def assert_session_files(self, session_id, upload, reply_name):
        session = self.root / "sessions" / session_id
        self.assertEqual(upload, (session / "upload.wav").read_bytes())
        self.assertEqual(
            (ASSETS / reply_name).read_bytes(),
            (session / "reply.wav").read_bytes(),
        )

    def test_success_pipeline_ack_files_and_downlink_integrity(self):
        raw = (ASSETS / "ask_weather.wav").read_bytes()
        with self.connect() as sock:
            decoder, pending, ack = send_upload(sock, "success", raw, pipeline=True)
            self.assertEqual(W_ACK, ack[0])
            self.assertEqual(
                {"ok": True, "text": "今天天气怎么样", "reply": "今天晴，气温二十六度"},
                json.loads(ack[2]),
            )
            pcm, end = receive_downlink(sock, decoder, pending)
        expected_pcm = oracle_wav_pcm((ASSETS / "tts_weather.wav").read_bytes())
        self.assertEqual(expected_pcm, pcm)
        meta = json.loads(end[2])
        self.assertEqual(len(upload_frames(pcm)), end[1])
        self.assertEqual(end[1], meta["total_chunks"])
        self.assertEqual(hashlib.sha256(pcm).hexdigest(), meta["sha256"])
        self.assertTrue(all(len(chunk) == 3200
                            for chunk in upload_frames(pcm)[:-1]))
        self.assert_session_files("success", raw, "tts_weather.wav")

    def test_disconnect_resume_then_full_chain(self):
        raw = (ASSETS / "ask_time.wav").read_bytes()
        chunks = upload_frames(raw)
        with self.connect() as first:
            decoder, pending, ack = hello(first, "resume")
            self.assertEqual(0, json.loads(ack[2])["last_seq"])
            for seq, chunk in enumerate(chunks[:2], 1):
                first.sendall(wire_encode(W_AUDIO_CHUNK, seq, chunk))
                self.assertEqual((W_ACK, seq, b""), recv_frame(first, decoder, pending))
        with self.connect() as second:
            decoder, pending, hello_ack = hello(second, "resume")
            self.assertEqual(W_ACK, hello_ack[0])
            self.assertEqual(2, json.loads(hello_ack[2])["last_seq"])
            for seq, chunk in enumerate(chunks[2:], 3):
                second.sendall(wire_encode(W_AUDIO_CHUNK, seq, chunk))
                self.assertEqual((W_ACK, seq, b""), recv_frame(second, decoder, pending))
            end = json.dumps({"total_chunks": len(chunks),
                              "sha256": hashlib.sha256(raw).hexdigest()}).encode()
            second.sendall(wire_encode(W_AUDIO_END, len(chunks), end))
            ack = recv_frame(second, decoder, pending)
            self.assertEqual(W_ACK, ack[0])
            self.assertEqual("现在几点了", json.loads(ack[2])["text"])
            receive_downlink(second, decoder, pending)
        self.assert_session_files("resume", raw, "tts_time.wav")

    def test_integrity_and_wire_errors_return_error(self):
        raw = (ASSETS / "ask_weather.wav").read_bytes()
        chunks = upload_frames(raw)
        with self.connect() as sock:
            decoder, pending, ack = hello(sock, "bad-hash")
            for seq, chunk in enumerate(chunks, 1):
                sock.sendall(wire_encode(W_AUDIO_CHUNK, seq, chunk))
                recv_frame(sock, decoder, pending)
            end = json.dumps({"total_chunks": len(chunks), "sha256": "0" * 64}).encode()
            sock.sendall(wire_encode(W_AUDIO_END, len(chunks), end))
            error = recv_frame(sock, decoder, pending)
            self.assertEqual((W_ERROR, len(chunks)), error[:2])
            self.assertEqual("INTEGRITY_FAIL", json.loads(error[2])["code"])
            assert_closed(self, sock)

        with self.connect() as sock:
            sock.sendall(b"ZZ")
            error = recv_frame(sock, WireDecoder(), [])
            self.assertEqual((W_ERROR, 0), error[:2])
            self.assertEqual("BAD_MAGIC", json.loads(error[2])["code"])
            assert_closed(self, sock)

        with self.connect() as sock:
            frame = bytearray(wire_encode(W_HELLO, 7, b"{}"))
            frame[-1] ^= 1
            sock.sendall(frame)
            decoder = WireDecoder()
            error = recv_frame(sock, decoder, [])
            self.assertEqual((W_ERROR, 7), error[:2])
            self.assertEqual("BAD_CRC", json.loads(error[2])["code"])
            assert_closed(self, sock)

        with self.connect() as sock:
            oversized = W_MAGIC + struct.pack(
                ">BII", W_AUDIO_CHUNK, 12, W_MAX_PAYLOAD + 1
            )
            sock.sendall(oversized)
            error = recv_frame(sock, WireDecoder(), [])
            self.assertEqual(12, error[1])
            self.assertEqual("PAYLOAD_TOO_LARGE", json.loads(error[2])["code"])
            assert_closed(self, sock)

    def test_unsafe_session_gap_and_cross_device_takeover_are_rejected(self):
        before = {path.relative_to(self.root) for path in self.root.rglob("*")}
        for unsafe in ("", "a" * 129, "../escape", "a/b", "a\\b", ".hidden"):
            with self.subTest(session_id=unsafe), self.connect() as sock:
                _, _, error = hello(sock, unsafe)
                self.assertEqual(W_ERROR, error[0])
                self.assertEqual("INTEGRITY_FAIL", json.loads(error[2])["code"])
                assert_closed(self, sock)
        after = {path.relative_to(self.root) for path in self.root.rglob("*")}
        self.assertEqual(before, after)

        with self.connect() as sock:
            decoder, pending, ack = hello(sock, "owned", "owner-a")
            self.assertEqual(W_ACK, ack[0])
            sock.sendall(wire_encode(W_AUDIO_CHUNK, 2, b"gap"))
            error = recv_frame(sock, decoder, pending)
            self.assertEqual("INTEGRITY_FAIL", json.loads(error[2])["code"])
            assert_closed(self, sock)

        with self.connect() as sock:
            _, _, error = hello(sock, "owned", "owner-b")
            self.assertEqual(W_ERROR, error[0])
            self.assertEqual("INTEGRITY_FAIL", json.loads(error[2])["code"])
            assert_closed(self, sock)

    def test_upstream_retry_timeout_and_4xx(self):
        weather = (ASSETS / "ask_weather.wav").read_bytes()
        self.control({"service": "asr", "mode": "500"})
        with self.connect() as sock:
            decoder, pending, ack = send_upload(sock, "retry", weather)
            self.assertEqual(W_ACK, ack[0])
            receive_downlink(sock, decoder, pending)

        self.control({"service": "asr", "hang_ms": 500})
        with self.connect() as sock:
            _, _, error = send_upload(sock, "timeout", weather)
            self.assertEqual(W_ERROR, error[0])
            error_payload = json.loads(error[2])
            self.assertEqual("UPSTREAM_TIMEOUT", error_payload["code"], error_payload)
            assert_closed(self, sock)

        unknown = io.BytesIO()
        with wave.open(unknown, "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(16000)
            out.writeframes(b"\0" * 320)
        with self.connect() as sock:
            _, _, error = send_upload(sock, "unknown", unknown.getvalue())
            self.assertEqual(W_ERROR, error[0])
            self.assertEqual("UPSTREAM_ERROR", json.loads(error[2])["code"])
            assert_closed(self, sock)

    def test_bundled_device_sim_full_chain_contract(self):
        out_dir = self.root / "device-out"
        result = subprocess.run(
            [sys.executable, str(FIXTURE / "device-sim" / "device_sim.py"),
             "--server", f"127.0.0.1:{self.backend_port}",
             "--wav", str(ASSETS / "ask_weather.wav"),
             "--session", "device-contract", "--out", str(out_dir)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("AUDIO_END -> ACK", result.stdout)
        self.assertIn("下行结束：9 块 / 26656 字节", result.stdout)
        self.assertEqual(
            oracle_wav_pcm((ASSETS / "tts_weather.wav").read_bytes()),
            (out_dir / "reply_payload.bin").read_bytes(),
        )
        self.assert_session_files(
            "device-contract", (ASSETS / "ask_weather.wav").read_bytes(), "tts_weather.wav"
        )

    def test_concurrent_sessions_and_downlink_disconnect_are_isolated(self):
        cases = [
            ("parallel-weather", "ask_weather.wav", "今天天气怎么样",
             "今天晴，气温二十六度", "tts_weather.wav"),
            ("parallel-time", "ask_time.wav", "现在几点了",
             "现在是下午三点", "tts_time.wav"),
        ]
        results = {}
        errors = []

        def run(case):
            session_id, filename, expected_text, expected_reply, tts_name = case
            try:
                with self.connect() as sock:
                    decoder, pending, ack = send_upload(
                        sock, session_id, (ASSETS / filename).read_bytes(), device_id=session_id
                    )
                    ack_payload = json.loads(ack[2])
                    pcm, end = receive_downlink(sock, decoder, pending)
                    results[session_id] = (ack_payload, pcm, json.loads(end[2]))
            except BaseException as exc:
                errors.append(exc)

        threads = [threading.Thread(target=run, args=(case,)) for case in cases]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
        self.assertEqual([], errors)
        for session_id, filename, expected_text, expected_reply, tts_name in cases:
            ack_payload, pcm, end = results[session_id]
            self.assertEqual({"ok": True, "text": expected_text, "reply": expected_reply},
                             ack_payload)
            expected_pcm = oracle_wav_pcm((ASSETS / tts_name).read_bytes())
            self.assertEqual(expected_pcm, pcm)
            self.assertEqual(hashlib.sha256(expected_pcm).hexdigest(), end["sha256"])
            self.assert_session_files(session_id, (ASSETS / filename).read_bytes(), tts_name)

        weather = (ASSETS / "ask_weather.wav").read_bytes()
        sock = self.connect()
        _, _, ack = send_upload(sock, "drop-downlink", weather)
        self.assertEqual(W_ACK, ack[0])
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
        sock.close()
        time.sleep(0.05)
        with self.connect() as healthy:
            decoder, pending, ack = send_upload(healthy, "after-drop", weather)
            self.assertEqual(W_ACK, ack[0])
            receive_downlink(healthy, decoder, pending)


if __name__ == "__main__":
    unittest.main(verbosity=2)
