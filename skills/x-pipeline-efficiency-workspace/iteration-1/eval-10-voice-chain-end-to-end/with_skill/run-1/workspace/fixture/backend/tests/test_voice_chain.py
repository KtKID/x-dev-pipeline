import concurrent.futures
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
from unittest import mock


BACKEND = pathlib.Path(__file__).resolve().parents[1]
FIXTURE = BACKEND.parent
WORKSPACE = FIXTURE.parent
sys.path.insert(0, str(BACKEND))

import app  # noqa: E402
import audio  # noqa: E402
import http_client  # noqa: E402
import protocol  # noqa: E402


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()


def make_wav(rate=audio.PCM_SAMPLE_RATE, channels=audio.PCM_CHANNELS, width=2):
    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(width)
        wav.setframerate(rate)
        wav.writeframes(b"\x00" * (rate * channels * width // 100))
    return out.getvalue()


def raw_http_server(parts):
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    def serve():
        try:
            conn, _ = server.accept()
            with conn:
                request = b""
                while b"\r\n\r\n" not in request:
                    data = conn.recv(4096)
                    if not data:
                        return
                    request += data
                for delay, data in parts:
                    if delay:
                        time.sleep(delay)
                    conn.sendall(data)
        except OSError:
            pass
        finally:
            server.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    return f"http://127.0.0.1:{port}/service", thread


class ProtocolAndAudioTests(unittest.TestCase):
    def test_stream_decoder_handles_split_and_sticky_frames(self):
        first = protocol.encode_frame(protocol.T_HELLO, 0, b"hello")
        second = protocol.encode_frame(protocol.T_AUDIO_CHUNK, 1, b"audio")
        decoder = protocol.FrameDecoder()
        self.assertEqual(decoder.feed(first[:3]), [])
        self.assertEqual(
            decoder.feed(first[3:] + second),
            [
                (protocol.T_HELLO, 0, b"hello"),
                (protocol.T_AUDIO_CHUNK, 1, b"audio"),
            ],
        )

    def test_decoder_rejects_bad_magic(self):
        frame = bytearray(protocol.encode_frame(protocol.T_HELLO, 0))
        frame[0] ^= 0xFF
        with self.assertRaisesRegex(protocol.ProtocolError, "BAD_MAGIC"):
            protocol.FrameDecoder().feed(bytes(frame))

    def test_decoder_rejects_bad_crc_with_related_seq(self):
        frame = bytearray(protocol.encode_frame(protocol.T_AUDIO_CHUNK, 7, b"data"))
        frame[-1] ^= 0xFF
        with self.assertRaises(protocol.ProtocolError) as caught:
            protocol.FrameDecoder().feed(bytes(frame))
        self.assertEqual(caught.exception.code, "BAD_CRC")
        self.assertEqual(caught.exception.seq, 7)

    def test_decoder_rejects_oversized_declaration_before_payload(self):
        header = protocol.MAGIC + struct.pack(
            ">BII", protocol.T_AUDIO_CHUNK, 9, protocol.MAX_PAYLOAD + 1
        )
        with self.assertRaises(protocol.ProtocolError) as caught:
            protocol.FrameDecoder().feed(header)
        self.assertEqual(caught.exception.code, "PAYLOAD_TOO_LARGE")
        self.assertEqual(caught.exception.seq, 9)

    def test_wav_pcm_accepts_only_device_format_and_chunks_losslessly(self):
        raw = (FIXTURE / "assets" / "tts_weather.wav").read_bytes()
        pcm = audio.wav_pcm(raw)
        chunks = list(audio.chunk_pcm(pcm, audio.PCM_CHUNK_SIZE))
        self.assertEqual(b"".join(chunks), pcm)
        self.assertTrue(all(len(chunk) == audio.PCM_CHUNK_SIZE for chunk in chunks[:-1]))
        self.assertLessEqual(len(chunks[-1]), audio.PCM_CHUNK_SIZE)

        for invalid in (make_wav(rate=8000), make_wav(channels=2), make_wav(width=1)):
            with self.assertRaisesRegex(ValueError, "unsupported wav format"):
                audio.wav_pcm(invalid)

        corrupt_size = bytearray(raw)
        corrupt_size[4:8] = (0).to_bytes(4, "little")
        with self.assertRaisesRegex(ValueError, "RIFF size mismatch"):
            audio.wav_pcm(bytes(corrupt_size))
        with self.assertRaisesRegex(ValueError, "RIFF size mismatch"):
            audio.wav_pcm(raw + b"trailing")


class UpstreamPolicyTests(unittest.TestCase):
    def test_config_is_validated_before_runtime(self):
        valid = {
            "listen_host": "127.0.0.1",
            "mock_base_url": "http://127.0.0.1:9100",
            "service_timeout_ms": 50,
            "retry_max_5xx": 0,
        }
        self.assertIs(app.validate_config(valid), valid)
        for invalid in (
            {**valid, "mock_base_url": "relative"},
            {**valid, "mock_base_url": "http://127.0.0.1:bad"},
            {**valid, "mock_base_url": "http://127.0.0.1:70000"},
            {**valid, "mock_base_url": "http://127.0.0.1:0"},
            {**valid, "service_timeout_ms": 0},
            {**valid, "service_timeout_ms": True},
            {**valid, "retry_max_5xx": -1},
            {key: value for key, value in valid.items() if key != "mock_base_url"},
        ):
            with self.assertRaises(ValueError):
                app.validate_config(invalid)

    def test_malformed_or_truncated_http_is_upstream_error(self):
        response = b"HTTP/1.1 200 OK\r\nContent-Length: 10\r\nConnection: close\r\n\r\nabc"
        url, thread = raw_http_server([(0, response)])
        with self.assertRaises(app.UpstreamFailure) as caught:
            app.call_upstream(url, b"request", "application/octet-stream", 200, 0)
        thread.join(timeout=1)
        self.assertEqual(caught.exception.code, "UPSTREAM_ERROR")

    def test_total_deadline_rejects_trickled_http_body(self):
        header = b"HTTP/1.1 200 OK\r\nContent-Length: 10\r\nConnection: close\r\n\r\n"
        parts = [(0, header)] + [(0.03, b"x") for _ in range(10)]
        url, thread = raw_http_server(parts)
        started = time.monotonic()
        with self.assertRaises(TimeoutError):
            http_client.post(url, b"request", "application/octet-stream", 50)
        self.assertLess(time.monotonic() - started, 0.2)
        thread.join(timeout=1)

    def test_total_deadline_rejects_trickled_http_headers(self):
        response = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok"
        url, thread = raw_http_server([(0.03, bytes([byte])) for byte in response])
        started = time.monotonic()
        with self.assertRaises(TimeoutError):
            http_client.post(url, b"request", "application/octet-stream", 50)
        self.assertLess(time.monotonic() - started, 0.2)
        thread.join(timeout=1)

    def test_5xx_retries_up_to_configured_extra_attempts(self):
        with mock.patch.object(
            app.http_client,
            "post",
            side_effect=[(500, b"first"), (200, b"ok")],
        ) as post:
            body = app.call_upstream(
                "http://service/asr", b"wav", "application/octet-stream", 50, 1
            )
        self.assertEqual(body, b"ok")
        self.assertEqual(post.call_count, 2)

    def test_exhausted_5xx_and_4xx_are_upstream_errors(self):
        with mock.patch.object(app.http_client, "post", return_value=(500, b"bad")) as post:
            with self.assertRaises(app.UpstreamFailure) as caught:
                app.call_upstream("http://service/tts", b"{}", "application/json", 50, 1)
        self.assertEqual(caught.exception.code, "UPSTREAM_ERROR")
        self.assertEqual(post.call_count, 2)

        with mock.patch.object(app.http_client, "post", return_value=(400, b"bad")) as post:
            with self.assertRaises(app.UpstreamFailure) as caught:
                app.call_upstream("http://service/llm", b"{}", "application/json", 50, 4)
        self.assertEqual(caught.exception.code, "UPSTREAM_ERROR")
        self.assertEqual(post.call_count, 1)

    def test_timeout_is_not_retried(self):
        with mock.patch.object(app.http_client, "post", side_effect=TimeoutError("late")) as post:
            with self.assertRaises(app.UpstreamFailure) as caught:
                app.call_upstream("http://service/asr", b"wav", "application/octet-stream", 50, 5)
        self.assertEqual(caught.exception.code, "UPSTREAM_TIMEOUT")
        self.assertEqual(post.call_count, 1)


class EndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.run_dir = pathlib.Path(cls.temp.name)
        cls.mock_port = free_port()
        cls.backend_port = free_port()
        cls.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        cls.mock_proc = subprocess.Popen(
            [
                sys.executable,
                str(FIXTURE / "mock-services" / "mock_services.py"),
                "--port",
                str(cls.mock_port),
            ],
            cwd=cls.run_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        cls._wait_http(f"http://127.0.0.1:{cls.mock_port}/health")

        config = {
            "listen_host": "127.0.0.1",
            "mock_base_url": f"http://127.0.0.1:{cls.mock_port}",
            "service_timeout_ms": 200,
            "retry_max_5xx": 1,
        }
        cls.config_path = cls.run_dir / "config.json"
        cls.config_path.write_text(json.dumps(config))
        cls.backend_proc = subprocess.Popen(
            [
                sys.executable,
                str(BACKEND / "app.py"),
                "--port",
                str(cls.backend_port),
                "--config",
                str(cls.config_path),
            ],
            cwd=cls.run_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        cls._wait_tcp(cls.backend_port)

    @classmethod
    def tearDownClass(cls):
        for proc in (getattr(cls, "backend_proc", None), getattr(cls, "mock_proc", None)):
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=3)
        cls.temp.cleanup()

    def setUp(self):
        self._control({"reset": True})

    @classmethod
    def _wait_http(cls, url):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                with cls.opener.open(url, timeout=0.2) as response:
                    if response.status == 200:
                        return
            except OSError:
                time.sleep(0.02)
        raise AssertionError(f"service did not start: {url}")

    @classmethod
    def _wait_tcp(cls, port):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if cls.backend_proc.poll() is not None:
                raise AssertionError("backend exited during startup")
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                    return
            except OSError:
                time.sleep(0.02)
        raise AssertionError("backend did not listen")

    def _control(self, value):
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.mock_port}/control",
            data=json_bytes(value),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.opener.open(request, timeout=1) as response:
            self.assertEqual(response.status, 200)

    def _connect(self):
        sock = socket.create_connection(("127.0.0.1", self.backend_port), timeout=2)
        sock.settimeout(2)
        return sock

    @staticmethod
    def _recv_frame(sock, decoder, pending):
        while not pending:
            data = sock.recv(protocol.MAX_PAYLOAD + protocol.HEADER_LEN + protocol.CRC_LEN)
            if not data:
                raise ConnectionError("backend closed")
            pending.extend(decoder.feed(data))
        return pending.pop(0)

    def _hello(self, sock, session_id):
        decoder, pending = protocol.FrameDecoder(), []
        sock.sendall(
            protocol.encode_frame(
                protocol.T_HELLO,
                0,
                json_bytes({"device_id": "test-device", "session_id": session_id}),
            )
        )
        frame = self._recv_frame(sock, decoder, pending)
        self.assertEqual((frame[0], frame[1]), (protocol.T_ACK, 0))
        return decoder, pending, json.loads(frame[2])["last_seq"]

    @staticmethod
    def _chunks(raw):
        return [
            raw[offset : offset + audio.PCM_CHUNK_SIZE]
            for offset in range(0, len(raw), audio.PCM_CHUNK_SIZE)
        ]

    def _upload_with_acks(self, sock, decoder, pending, raw, start=1):
        chunks = self._chunks(raw)
        for seq in range(start, len(chunks) + 1):
            sock.sendall(protocol.encode_frame(protocol.T_AUDIO_CHUNK, seq, chunks[seq - 1]))
            frame = self._recv_frame(sock, decoder, pending)
            self.assertEqual(frame, (protocol.T_ACK, seq, b""))
        return chunks

    def _send_end(self, sock, decoder, pending, raw, chunks, digest=None):
        digest = digest or hashlib.sha256(raw).hexdigest()
        sock.sendall(
            protocol.encode_frame(
                protocol.T_AUDIO_END,
                len(chunks),
                json_bytes({"total_chunks": len(chunks), "sha256": digest}),
            )
        )
        return self._recv_frame(sock, decoder, pending)

    def _receive_downlink(self, sock, decoder, pending):
        chunks = []
        while True:
            frame = self._recv_frame(sock, decoder, pending)
            if frame[0] == protocol.T_TTS_CHUNK:
                self.assertEqual(frame[1], len(chunks) + 1)
                chunks.append(frame[2])
                continue
            self.assertEqual(frame[0], protocol.T_TTS_END)
            metadata = json.loads(frame[2])
            pcm = b"".join(chunks)
            self.assertEqual(frame[1], len(chunks))
            self.assertEqual(metadata["total_chunks"], len(chunks))
            self.assertEqual(metadata["sha256"], hashlib.sha256(pcm).hexdigest())
            return pcm, metadata

    def _conversation(self, session_id, asset_name):
        raw = (FIXTURE / "assets" / asset_name).read_bytes()
        with self._connect() as sock:
            decoder, pending, last = self._hello(sock, session_id)
            self.assertEqual(last, 0)
            chunks = self._upload_with_acks(sock, decoder, pending, raw)
            ack = self._send_end(sock, decoder, pending, raw, chunks)
            self.assertEqual(ack[0], protocol.T_ACK)
            pcm, metadata = self._receive_downlink(sock, decoder, pending)
        return raw, json.loads(ack[2]), pcm, metadata

    def _assert_error_for_wire(self, raw, code, seq):
        with self._connect() as sock:
            sock.sendall(raw)
            frame = self._recv_frame(sock, protocol.FrameDecoder(), [])
            self.assertEqual((frame[0], frame[1]), (protocol.T_ERROR, seq))
            self.assertEqual(json.loads(frame[2])["code"], code)
            self.assertEqual(sock.recv(1), b"")
        self.assertIsNone(self.backend_proc.poll())

    def test_protocol_errors_are_returned_and_connection_closes(self):
        bad_magic = bytearray(protocol.encode_frame(protocol.T_HELLO, 0))
        bad_magic[0] ^= 0xFF
        self._assert_error_for_wire(bytes(bad_magic), "BAD_MAGIC", 0)

        bad_crc = bytearray(protocol.encode_frame(protocol.T_AUDIO_CHUNK, 4, b"bad"))
        bad_crc[-1] ^= 0xFF
        self._assert_error_for_wire(bytes(bad_crc), "BAD_CRC", 4)

        too_large = protocol.MAGIC + struct.pack(
            ">BII", protocol.T_AUDIO_CHUNK, 5, protocol.MAX_PAYLOAD + 1
        )
        self._assert_error_for_wire(too_large, "PAYLOAD_TOO_LARGE", 5)

        raw = (FIXTURE / "assets" / "ask_weather.wav").read_bytes()
        first_chunk = self._chunks(raw)[0]
        with self._connect() as sock:
            decoder, pending, _ = self._hello(sock, "valid-before-bad-crc")
            good = protocol.encode_frame(protocol.T_AUDIO_CHUNK, 1, first_chunk)
            bad = bytearray(protocol.encode_frame(protocol.T_AUDIO_CHUNK, 2, b"bad"))
            bad[-1] ^= 0xFF
            sock.sendall(good + bytes(bad))
            self.assertEqual(
                self._recv_frame(sock, decoder, pending),
                (protocol.T_ACK, 1, b""),
            )
            error = self._recv_frame(sock, decoder, pending)
            self.assertEqual((error[0], error[1]), (protocol.T_ERROR, 2))
            self.assertEqual(json.loads(error[2])["code"], "BAD_CRC")

        with self._connect() as sock:
            _, _, last_seq = self._hello(sock, "valid-before-bad-crc")
            self.assertEqual(last_seq, 1)

    def test_pipelined_fragmented_upload_and_full_downlink(self):
        session = "pipeline-weather"
        raw = (FIXTURE / "assets" / "ask_weather.wav").read_bytes()
        chunks = self._chunks(raw)
        with self._connect() as sock:
            decoder, pending, last = self._hello(sock, session)
            self.assertEqual(last, 0)
            wire = b"".join(
                protocol.encode_frame(protocol.T_AUDIO_CHUNK, seq, chunk)
                for seq, chunk in enumerate(chunks, 1)
            )
            wire += protocol.encode_frame(
                protocol.T_AUDIO_END,
                len(chunks),
                json_bytes(
                    {"total_chunks": len(chunks), "sha256": hashlib.sha256(raw).hexdigest()}
                ),
            )
            cuts = (1, 8, 31, 509, 4093)
            offset = 0
            for size in cuts:
                sock.sendall(wire[offset : offset + size])
                offset += size
            sock.sendall(wire[offset:])

            for seq in range(1, len(chunks) + 1):
                self.assertEqual(
                    self._recv_frame(sock, decoder, pending),
                    (protocol.T_ACK, seq, b""),
                )
            ack = self._recv_frame(sock, decoder, pending)
            self.assertEqual(json.loads(ack[2])["text"], "今天天气怎么样")
            pcm, _ = self._receive_downlink(sock, decoder, pending)

        self.assertEqual((self.run_dir / "sessions" / session / "upload.wav").read_bytes(), raw)
        expected_tts = (FIXTURE / "assets" / "tts_weather.wav").read_bytes()
        self.assertEqual((self.run_dir / "sessions" / session / "reply.wav").read_bytes(), expected_tts)
        self.assertEqual(pcm, audio.wav_pcm(expected_tts))

    def test_integrity_failure_skips_orchestration(self):
        session = "bad-integrity"
        raw = (FIXTURE / "assets" / "ask_weather.wav").read_bytes()
        with self._connect() as sock:
            decoder, pending, _ = self._hello(sock, session)
            chunks = self._upload_with_acks(sock, decoder, pending, raw)
            frame = self._send_end(sock, decoder, pending, raw, chunks, digest="0" * 64)
            self.assertEqual(frame[0], protocol.T_ERROR)
            self.assertEqual(json.loads(frame[2])["code"], "INTEGRITY_FAIL")
        self.assertFalse((self.run_dir / "sessions" / session / "reply.wav").exists())

    def test_success_ack_and_reply_file(self):
        session = "success-weather"
        _, ack, pcm, _ = self._conversation(session, "ask_weather.wav")
        self.assertEqual(
            ack,
            {"ok": True, "text": "今天天气怎么样", "reply": "今天晴，气温二十六度"},
        )
        reply = (FIXTURE / "assets" / "tts_weather.wav").read_bytes()
        self.assertEqual((self.run_dir / "sessions" / session / "reply.wav").read_bytes(), reply)
        self.assertEqual(pcm, audio.wav_pcm(reply))

    def test_upstream_timeout_returns_error_within_finite_time(self):
        self._control({"service": "asr", "hang_ms": 600})
        raw = (FIXTURE / "assets" / "ask_time.wav").read_bytes()
        started = time.monotonic()
        with self._connect() as sock:
            decoder, pending, _ = self._hello(sock, "timeout-asr")
            chunks = self._upload_with_acks(sock, decoder, pending, raw)
            frame = self._send_end(sock, decoder, pending, raw, chunks)
        self.assertEqual(frame[0], protocol.T_ERROR)
        self.assertEqual(json.loads(frame[2])["code"], "UPSTREAM_TIMEOUT")
        self.assertLess(time.monotonic() - started, 1.5)

    def test_single_5xx_retries_and_completes(self):
        self._control({"service": "llm", "mode": "500"})
        _, ack, _, _ = self._conversation("retry-llm", "ask_time.wav")
        self.assertEqual(ack["reply"], "现在是下午三点")

    def test_unknown_audio_4xx_returns_upstream_error(self):
        raw = bytearray((FIXTURE / "assets" / "ask_time.wav").read_bytes())
        raw[-1] ^= 0x01
        raw = bytes(raw)
        with self._connect() as sock:
            decoder, pending, _ = self._hello(sock, "unknown-audio")
            chunks = self._upload_with_acks(sock, decoder, pending, raw)
            frame = self._send_end(sock, decoder, pending, raw, chunks)
        self.assertEqual(frame[0], protocol.T_ERROR)
        self.assertEqual(json.loads(frame[2])["code"], "UPSTREAM_ERROR")

    def test_resume_from_contiguous_prefix_completes_chain(self):
        session = "resume-weather"
        raw = (FIXTURE / "assets" / "ask_weather.wav").read_bytes()
        chunks = self._chunks(raw)
        split = max(1, len(chunks) // 2)
        with self._connect() as sock:
            decoder, pending, last = self._hello(sock, session)
            self.assertEqual(last, 0)
            for seq in range(1, split + 1):
                sock.sendall(protocol.encode_frame(protocol.T_AUDIO_CHUNK, seq, chunks[seq - 1]))
                self.assertEqual(
                    self._recv_frame(sock, decoder, pending),
                    (protocol.T_ACK, seq, b""),
                )

        with self._connect() as sock:
            decoder, pending, last = self._hello(sock, session)
            self.assertEqual(last, split)
            self._upload_with_acks(sock, decoder, pending, raw, start=last + 1)
            ack = self._send_end(sock, decoder, pending, raw, chunks)
            self.assertEqual(json.loads(ack[2])["reply"], "今天晴，气温二十六度")
            self._receive_downlink(sock, decoder, pending)
        self.assertEqual((self.run_dir / "sessions" / session / "upload.wav").read_bytes(), raw)

    def test_concurrent_sessions_are_isolated(self):
        pairs = (("parallel-weather", "ask_weather.wav"), ("parallel-time", "ask_time.wav"))
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(pairs)) as pool:
            futures = [pool.submit(self._conversation, session, asset) for session, asset in pairs]
            results = [future.result(timeout=5) for future in futures]

        self.assertEqual(results[0][1]["text"], "今天天气怎么样")
        self.assertEqual(results[1][1]["text"], "现在几点了")
        for (session, asset), (raw, _, _, _) in zip(pairs, results):
            self.assertEqual((self.run_dir / "sessions" / session / "upload.wav").read_bytes(), raw)

    def test_disconnect_during_response_does_not_stop_other_sessions(self):
        raw = (FIXTURE / "assets" / "ask_weather.wav").read_bytes()
        sock = self._connect()
        decoder, pending, _ = self._hello(sock, "disconnect-downlink")
        chunks = self._upload_with_acks(sock, decoder, pending, raw)
        ack = self._send_end(sock, decoder, pending, raw, chunks)
        self.assertEqual(ack[0], protocol.T_ACK)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
        sock.close()

        _, ack, _, _ = self._conversation("after-disconnect", "ask_time.wav")
        self.assertEqual(ack["text"], "现在几点了")
        self.assertIsNone(self.backend_proc.poll())

    def test_device_sim_cli_completes_real_smoke_chain(self):
        output_dir = self.run_dir / "device-output"
        result = subprocess.run(
            [
                sys.executable,
                str(FIXTURE / "device-sim" / "device_sim.py"),
                "--server",
                f"127.0.0.1:{self.backend_port}",
                "--wav",
                str(FIXTURE / "assets" / "ask_weather.wav"),
                "--session",
                "device-sim-smoke",
                "--out",
                str(output_dir),
            ],
            cwd=self.run_dir,
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("AUDIO_END -> ACK", result.stdout)
        self.assertIn("下行结束", result.stdout)
        expected_pcm = audio.wav_pcm((FIXTURE / "assets" / "tts_weather.wav").read_bytes())
        self.assertEqual((output_dir / "reply_payload.bin").read_bytes(), expected_pcm)


if __name__ == "__main__":
    unittest.main()
