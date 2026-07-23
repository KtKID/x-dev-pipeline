"""Self-contained cross-process E2E verification for the voice chain."""
import concurrent.futures
import hashlib
import json
import os
import pathlib
import socket
import struct
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request

import audio
import protocol


BACKEND = pathlib.Path(__file__).resolve().parent
FIXTURE = BACKEND.parent
ASSETS = FIXTURE / "assets"
MOCK = FIXTURE / "mock-services" / "mock_services.py"
CHUNK_SIZE = 3200


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Client:
    def __init__(self, port):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=3)
        self.sock.settimeout(3)
        self.decoder = protocol.FrameDecoder()
        self.pending = []

    def send(self, frame_type, seq, payload=b""):
        self.sock.sendall(protocol.encode_frame(frame_type, seq, payload))

    def recv(self):
        while not self.pending:
            data = self.sock.recv(protocol.MAX_PAYLOAD + protocol.HEADER_LEN + protocol.CRC_LEN)
            if not data:
                raise ConnectionError("backend closed before a complete response")
            self.pending.extend(self.decoder.feed(data))
        return self.pending.pop(0)

    def hello(self, session_id, device_id="e2e-device"):
        self.send(protocol.T_HELLO, 0, json.dumps({
            "device_id": device_id,
            "session_id": session_id,
        }).encode())
        frame = self.recv()
        if frame[0] != protocol.T_ACK:
            raise AssertionError(frame)
        return json.loads(frame[2])["last_seq"]

    def close(self, reset=False):
        if reset:
            self.sock.setsockopt(
                socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0)
            )
        self.sock.close()


class VoiceChainE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        root = pathlib.Path(cls.temporary.name)
        cls.sessions = root / "sessions"
        cls.mock_port = free_port()
        cls.backend_port = free_port()
        config = {
            "listen_host": "127.0.0.1",
            "mock_base_url": f"http://127.0.0.1:{cls.mock_port}",
            "service_timeout_ms": 200,
            "retry_max_5xx": 1,
            "audio_chunk_bytes": CHUNK_SIZE,
            "pcm_sample_rate_hz": 16000,
            "pcm_channels": 1,
            "pcm_bits_per_sample": 16,
            "max_upload_bytes": 4000000,
            "max_sessions": 64,
            "session_ttl_seconds": 600,
            "session_id_max_length": 128,
            "device_id_max_length": 128,
            "max_json_response_bytes": 131072,
            "max_tts_wav_bytes": 4000000,
            "max_http_header_bytes": 65536,
            "sessions_dir": str(cls.sessions),
        }
        cls.config_path = root / "config.json"
        cls.config_path.write_text(json.dumps(config))
        cls.mock_process = subprocess.Popen(
            [sys.executable, str(MOCK), "--port", str(cls.mock_port)],
            cwd=MOCK.parent,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        cls.backend_process = subprocess.Popen(
            [sys.executable, str(BACKEND / "app.py"), "--port", str(cls.backend_port),
             "--config", str(cls.config_path)],
            cwd=BACKEND,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        cls.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if cls.mock_process.poll() is not None or cls.backend_process.poll() is not None:
                raise RuntimeError("E2E child process exited during startup")
            try:
                with cls.opener.open(
                    f"http://127.0.0.1:{cls.mock_port}/health", timeout=0.2
                ) as response:
                    if response.status == 200:
                        probe = socket.create_connection(
                            ("127.0.0.1", cls.backend_port), timeout=0.2
                        )
                        probe.close()
                        break
            except OSError:
                time.sleep(0.03)
        else:
            raise RuntimeError("E2E services did not start")

    @classmethod
    def tearDownClass(cls):
        for process in (cls.backend_process, cls.mock_process):
            process.terminate()
        for process in (cls.backend_process, cls.mock_process):
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        cls.temporary.cleanup()

    @classmethod
    def control(cls, value):
        request = urllib.request.Request(
            f"http://127.0.0.1:{cls.mock_port}/control",
            data=json.dumps(value).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with cls.opener.open(request, timeout=2) as response:
            return json.loads(response.read())

    def setUp(self):
        self.control({"reset": True})

    def upload(self, session_id, wav_path, pipeline=False):
        raw = pathlib.Path(wav_path).read_bytes()
        chunks = [raw[i:i + CHUNK_SIZE] for i in range(0, len(raw), CHUNK_SIZE)]
        client = Client(self.backend_port)
        last = client.hello(session_id)
        frames = [
            protocol.encode_frame(protocol.T_AUDIO_CHUNK, seq, chunk)
            for seq, chunk in enumerate(chunks, 1) if seq > last
        ]
        if pipeline:
            stream = b"".join(frames)
            cuts = (1, 10, 307, len(stream))
            start = 0
            for end in cuts:
                if end > start:
                    client.sock.sendall(stream[start:end])
                start = end
            if start < len(stream):
                client.sock.sendall(stream[start:])
            for expected in range(last + 1, len(chunks) + 1):
                self.assertEqual(client.recv()[:2], (protocol.T_ACK, expected))
        else:
            for seq, frame in enumerate(frames, last + 1):
                client.sock.sendall(frame)
                self.assertEqual(client.recv()[:2], (protocol.T_ACK, seq))
        end_payload = json.dumps({
            "total_chunks": len(chunks),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }).encode()
        client.send(protocol.T_AUDIO_END, len(chunks), end_payload)
        first = client.recv()
        if first[0] == protocol.T_ERROR:
            client.close()
            return first, b"", None
        self.assertEqual(first[:2], (protocol.T_ACK, len(chunks)))
        pcm = bytearray()
        while True:
            frame = client.recv()
            if frame[0] == protocol.T_TTS_CHUNK:
                pcm.extend(frame[2])
            elif frame[0] == protocol.T_TTS_END:
                tail = json.loads(frame[2])
                self.assertEqual(frame[1], tail["total_chunks"])
                self.assertEqual(tail["sha256"], hashlib.sha256(pcm).hexdigest())
                client.close()
                return first, bytes(pcm), tail
            else:
                raise AssertionError(frame)

    def test_01_normal_chain_and_files(self):
        ack, pcm, _ = self.upload("normal-weather", ASSETS / "ask_weather.wav")
        self.assertEqual(json.loads(ack[2]), {
            "ok": True,
            "text": "今天天气怎么样",
            "reply": "今天晴，气温二十六度",
        })
        session = self.sessions / "normal-weather"
        self.assertEqual((session / "upload.wav").read_bytes(),
                         (ASSETS / "ask_weather.wav").read_bytes())
        self.assertEqual((session / "reply.wav").read_bytes(),
                         (ASSETS / "tts_weather.wav").read_bytes())
        self.assertEqual(pcm, audio.wav_pcm((ASSETS / "tts_weather.wav").read_bytes()))

    def test_02_disconnect_resume_completes_chain(self):
        raw = (ASSETS / "ask_time.wav").read_bytes()
        chunks = [raw[i:i + CHUNK_SIZE] for i in range(0, len(raw), CHUNK_SIZE)]
        client = Client(self.backend_port)
        self.assertEqual(client.hello("resume-time"), 0)
        for seq, chunk in enumerate(chunks[:3], 1):
            client.send(protocol.T_AUDIO_CHUNK, seq, chunk)
            self.assertEqual(client.recv()[:2], (protocol.T_ACK, seq))
        client.close()

        client = Client(self.backend_port)
        self.assertEqual(client.hello("resume-time"), 3)
        client.close()
        ack, pcm, _ = self.upload("resume-time", ASSETS / "ask_time.wav")
        self.assertEqual(json.loads(ack[2])["reply"], "现在是下午三点")
        self.assertEqual(pcm, audio.wav_pcm((ASSETS / "tts_time.wav").read_bytes()))

    def test_03_pipelined_sticky_and_split_frames(self):
        ack, _, _ = self.upload(
            "pipeline-weather", ASSETS / "ask_weather.wav", pipeline=True
        )
        self.assertTrue(json.loads(ack[2])["ok"])

    def test_04_bad_magic_crc_and_oversized_length(self):
        bad_magic = bytearray(protocol.encode_frame(protocol.T_HELLO, 0, b"{}"))
        bad_magic[0] ^= 0xFF
        client = Client(self.backend_port)
        client.sock.sendall(bad_magic)
        frame = client.recv()
        self.assertEqual(json.loads(frame[2])["code"], "BAD_MAGIC")
        client.close()

        bad_crc = bytearray(protocol.encode_frame(protocol.T_HELLO, 7, b"{}"))
        bad_crc[-1] ^= 0xFF
        client = Client(self.backend_port)
        client.sock.sendall(bad_crc)
        frame = client.recv()
        self.assertEqual(frame[1], 7)
        self.assertEqual(json.loads(frame[2])["code"], "BAD_CRC")
        client.close()

        header = protocol.MAGIC + struct.pack(
            ">BII", protocol.T_AUDIO_CHUNK, 11, protocol.MAX_PAYLOAD + 1
        )
        client = Client(self.backend_port)
        client.sock.sendall(header)
        frame = client.recv()
        self.assertEqual(frame[1], 11)
        self.assertEqual(json.loads(frame[2])["code"], "PAYLOAD_TOO_LARGE")
        client.close()

    def test_05_5xx_retries_and_timeout_is_bounded(self):
        self.control({"service": "asr", "mode": "500"})
        ack, _, _ = self.upload("retry-weather", ASSETS / "ask_weather.wav")
        self.assertEqual(ack[0], protocol.T_ACK)

        self.control({"service": "asr", "hang_ms": 700})
        started = time.monotonic()
        error, _, _ = self.upload("timeout-time", ASSETS / "ask_time.wav")
        elapsed = time.monotonic() - started
        self.assertEqual(error[0], protocol.T_ERROR)
        error_payload = json.loads(error[2])
        self.assertEqual(error_payload["code"], "UPSTREAM_TIMEOUT", error_payload)
        self.assertLess(elapsed, 1.5)

    def test_06_unknown_audio_is_upstream_error_without_hang(self):
        source = bytearray((ASSETS / "ask_weather.wav").read_bytes())
        source[-1] ^= 0x01
        unknown = pathlib.Path(self.temporary.name) / "unknown.wav"
        unknown.write_bytes(source)
        error, _, _ = self.upload("unknown-audio", unknown)
        self.assertEqual(error[0], protocol.T_ERROR)
        self.assertEqual(json.loads(error[2])["code"], "UPSTREAM_ERROR")

    def test_07_concurrent_sessions_are_isolated(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            weather = pool.submit(
                self.upload, "concurrent-weather", ASSETS / "ask_weather.wav"
            )
            clock = pool.submit(
                self.upload, "concurrent-time", ASSETS / "ask_time.wav"
            )
            weather_ack, weather_pcm, _ = weather.result(timeout=5)
            time_ack, time_pcm, _ = clock.result(timeout=5)
        self.assertEqual(json.loads(weather_ack[2])["text"], "今天天气怎么样")
        self.assertEqual(json.loads(time_ack[2])["text"], "现在几点了")
        self.assertEqual(weather_pcm, audio.wav_pcm((ASSETS / "tts_weather.wav").read_bytes()))
        self.assertEqual(time_pcm, audio.wav_pcm((ASSETS / "tts_time.wav").read_bytes()))

    def test_08_downlink_reset_does_not_stop_server(self):
        raw = (ASSETS / "ask_weather.wav").read_bytes()
        chunks = [raw[i:i + CHUNK_SIZE] for i in range(0, len(raw), CHUNK_SIZE)]
        client = Client(self.backend_port)
        client.hello("reset-downlink")
        for seq, chunk in enumerate(chunks, 1):
            client.send(protocol.T_AUDIO_CHUNK, seq, chunk)
            client.recv()
        client.send(protocol.T_AUDIO_END, len(chunks), json.dumps({
            "total_chunks": len(chunks),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }).encode())
        self.assertEqual(client.recv()[0], protocol.T_ACK)
        client.close(reset=True)

        ack, _, _ = self.upload("after-reset", ASSETS / "ask_time.wav")
        self.assertEqual(ack[0], protocol.T_ACK)
        self.assertIsNone(self.backend_process.poll())


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(VoiceChainE2E)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.wasSuccessful():
        print(f"E2E_OK tests={result.testsRun}")
    raise SystemExit(0 if result.wasSuccessful() else 1)
