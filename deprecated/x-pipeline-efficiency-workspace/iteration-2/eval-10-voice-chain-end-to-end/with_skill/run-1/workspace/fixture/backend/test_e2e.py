import concurrent.futures
import hashlib
import json
import pathlib
import socket
import struct
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
import wave

import protocol


BACKEND = pathlib.Path(__file__).resolve().parent
FIXTURE = BACKEND.parent
ASSETS = FIXTURE / "assets"
MOCK_SCRIPT = FIXTURE / "mock-services" / "mock_services.py"
APP_SCRIPT = BACKEND / "app.py"
DEVICE_SCRIPT = FIXTURE / "device-sim" / "device_sim.py"
UPLOAD_CHUNK_BYTES = 3200
PCM_GOLDENS = {
    "tts_weather.wav": (26656, "af253a81e48f81c3374d763c46541cfddc163747a80c57f2d028e14dfc55ccdf"),
    "tts_time.wav": (19552, "5b7488c474ff758d5b6caf6b254af5b146366afa2dc360d526469cc9b4184aa6"),
}


def golden_pcm(name):
    with wave.open(str(ASSETS / name), "rb") as wav:
        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) != (1, 2, 16000):
            raise AssertionError("golden fixture format changed")
        pcm = wav.readframes(wav.getnframes())
    length, digest = PCM_GOLDENS[name]
    if len(pcm) != length or hashlib.sha256(pcm).hexdigest() != digest:
        raise AssertionError("golden fixture PCM changed")
    return pcm


def free_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


class WireClient:
    def __init__(self, port):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=3)
        self.sock.settimeout(3)
        self.decoder = protocol.FrameDecoder()
        self.pending = []

    def send(self, frame_type, seq, payload=b""):
        self.sock.sendall(protocol.encode_frame(frame_type, seq, payload))

    def recv(self):
        while not self.pending:
            data = self.sock.recv(65536)
            if not data:
                raise ConnectionError("backend closed")
            self.pending.extend(self.decoder.feed(data))
        return self.pending.pop(0)

    def hello(self, session_id):
        self.send(
            protocol.T_HELLO,
            0,
            json.dumps({"device_id": "e2e", "session_id": session_id}).encode(),
        )
        frame = self.recv()
        if frame[0] != protocol.T_ACK:
            raise AssertionError(frame)
        return json.loads(frame[2])["last_seq"]

    def close(self):
        self.sock.close()


class VoiceChainE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mock_port = free_port()
        cls.backend_port = free_port()
        cls.temp = tempfile.TemporaryDirectory(prefix="voice-chain-e2e-")
        cls.run_dir = pathlib.Path(cls.temp.name)
        cls.config = cls.run_dir / "config.json"
        cls.config.write_text(
            json.dumps(
                {
                    "listen_host": "127.0.0.1",
                    "mock_base_url": f"http://127.0.0.1:{cls.mock_port}",
                    "service_timeout_ms": 200,
                    "retry_max_5xx": 1,
                }
            )
        )
        cls.mock = subprocess.Popen(
            [sys.executable, str(MOCK_SCRIPT), "--port", str(cls.mock_port)],
            cwd=cls.run_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        cls.backend = subprocess.Popen(
            [
                sys.executable,
                str(APP_SCRIPT),
                "--port",
                str(cls.backend_port),
                "--config",
                str(cls.config),
            ],
            cwd=cls.run_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        cls.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        cls._wait_for_services()

    @classmethod
    def tearDownClass(cls):
        for process in (cls.backend, cls.mock):
            process.terminate()
        for process in (cls.backend, cls.mock):
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        cls.temp.cleanup()

    @classmethod
    def _wait_for_services(cls):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if cls.mock.poll() is not None or cls.backend.poll() is not None:
                raise RuntimeError("test service exited during startup")
            try:
                with cls.opener.open(
                    f"http://127.0.0.1:{cls.mock_port}/health", timeout=0.2
                ) as response:
                    if response.status != 200:
                        continue
                probe = socket.create_connection(
                    ("127.0.0.1", cls.backend_port), timeout=0.2
                )
                probe.close()
                return
            except OSError:
                time.sleep(0.03)
        raise RuntimeError("test services did not start")

    @classmethod
    def control(cls, body):
        request = urllib.request.Request(
            f"http://127.0.0.1:{cls.mock_port}/control",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with cls.opener.open(request, timeout=1) as response:
            return json.loads(response.read())

    def talk(self, session_id, wav_path):
        raw = pathlib.Path(wav_path).read_bytes()
        chunks = [
            raw[index:index + UPLOAD_CHUNK_BYTES]
            for index in range(0, len(raw), UPLOAD_CHUNK_BYTES)
        ]
        client = WireClient(self.backend_port)
        try:
            last_seq = client.hello(session_id)
            for seq, chunk in enumerate(chunks, 1):
                if seq <= last_seq:
                    continue
                client.send(protocol.T_AUDIO_CHUNK, seq, chunk)
                self.assertEqual(client.recv()[:2], (protocol.T_ACK, seq))
            client.send(
                protocol.T_AUDIO_END,
                len(chunks),
                json.dumps(
                    {
                        "total_chunks": len(chunks),
                        "sha256": hashlib.sha256(raw).hexdigest(),
                    }
                ).encode(),
            )
            result = client.recv()
            if result[0] == protocol.T_ERROR:
                self.assertEqual(client.sock.recv(1), b"")
                return {"error": json.loads(result[2]), "last_seq": last_seq}
            self.assertEqual(result[:2], (protocol.T_ACK, len(chunks)))
            ack = json.loads(result[2])
            pcm_chunks = []
            while True:
                frame = client.recv()
                if frame[0] == protocol.T_TTS_CHUNK:
                    self.assertEqual(frame[1], len(pcm_chunks) + 1)
                    pcm_chunks.append(frame[2])
                    continue
                self.assertEqual(frame[0], protocol.T_TTS_END)
                pcm = b"".join(pcm_chunks)
                end = json.loads(frame[2])
                self.assertEqual(frame[1], len(pcm_chunks))
                self.assertEqual(end["total_chunks"], len(pcm_chunks))
                self.assertEqual(end["sha256"], hashlib.sha256(pcm).hexdigest())
                return {"ack": ack, "pcm": pcm, "last_seq": last_seq}
        finally:
            client.close()

    def test_success_files_and_concurrent_isolation(self):
        inputs = [
            ("concurrent-weather", ASSETS / "ask_weather.wav"),
            ("concurrent-time", ASSETS / "ask_time.wav"),
        ]
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self.talk, session, wav) for session, wav in inputs]
            results = [future.result(timeout=5) for future in futures]
        expected = [
            ("今天天气怎么样", "今天晴，气温二十六度", "tts_weather.wav"),
            ("现在几点了", "现在是下午三点", "tts_time.wav"),
        ]
        for (session, wav), result, (text, reply, tts_name) in zip(inputs, results, expected):
            self.assertEqual(result["ack"], {"ok": True, "text": text, "reply": reply})
            self.assertEqual(result["pcm"], golden_pcm(tts_name))
            session_dir = self.run_dir / "sessions" / session
            self.assertEqual((session_dir / "upload.wav").read_bytes(), wav.read_bytes())
            self.assertEqual((session_dir / "reply.wav").read_bytes(), (ASSETS / tts_name).read_bytes())

        self.control({"service": "asr", "hang_ms": 150})
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            slow = pool.submit(self.talk, "overlap-slow", ASSETS / "ask_weather.wav")
            upload_path = self.run_dir / "sessions" / "overlap-slow" / "upload.wav"
            deadline = time.monotonic() + 1
            while not upload_path.exists() and time.monotonic() < deadline:
                time.sleep(0.005)
            self.assertTrue(upload_path.exists())
            time.sleep(0.02)
            fast = pool.submit(self.talk, "overlap-fast", ASSETS / "ask_time.wav")
            fast_result = fast.result(timeout=2)
            self.assertFalse(slow.done(), "sessions were serialized behind the slow ASR call")
            slow_result = slow.result(timeout=2)
        self.assertEqual(fast_result["ack"]["text"], "现在几点了")
        self.assertEqual(slow_result["ack"]["text"], "今天天气怎么样")

    def test_device_sim_cli_smoke(self):
        out_dir = self.run_dir / "device-out"
        completed = subprocess.run(
            [
                sys.executable,
                str(DEVICE_SCRIPT),
                "--server",
                f"127.0.0.1:{self.backend_port}",
                "--wav",
                str(ASSETS / "ask_weather.wav"),
                "--session",
                "device-sim-smoke",
                "--out",
                str(out_dir),
            ],
            cwd=self.run_dir,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=5,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout)
        self.assertIn("AUDIO_END -> ACK", completed.stdout)
        self.assertIn("下行结束", completed.stdout)
        expected_pcm = golden_pcm("tts_weather.wav")
        self.assertEqual((out_dir / "reply_payload.bin").read_bytes(), expected_pcm)

        time_completed = subprocess.run(
            [
                sys.executable,
                str(DEVICE_SCRIPT),
                "--server",
                f"127.0.0.1:{self.backend_port}",
                "--wav",
                str(ASSETS / "ask_time.wav"),
                "--session",
                "device-sim-time-upload",
                "--upload-only",
            ],
            cwd=self.run_dir,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=5,
            check=False,
        )
        self.assertEqual(time_completed.returncode, 0, time_completed.stdout)
        self.assertIn('"text":"现在几点了"', time_completed.stdout)
        time_upload = self.run_dir / "sessions" / "device-sim-time-upload" / "upload.wav"
        self.assertEqual(time_upload.read_bytes(), (ASSETS / "ask_time.wav").read_bytes())

    def test_disconnect_resume_completes_full_chain(self):
        session = "resume-e2e"
        raw = (ASSETS / "ask_weather.wav").read_bytes()
        chunks = [raw[index:index + UPLOAD_CHUNK_BYTES] for index in range(0, len(raw), UPLOAD_CHUNK_BYTES)]
        first = WireClient(self.backend_port)
        self.assertEqual(first.hello(session), 0)
        for seq, chunk in enumerate(chunks[:3], 1):
            first.send(protocol.T_AUDIO_CHUNK, seq, chunk)
            self.assertEqual(first.recv()[:2], (protocol.T_ACK, seq))
        first.close()
        result = self.talk(session, ASSETS / "ask_weather.wav")
        self.assertEqual(result["last_seq"], 3)
        self.assertEqual(
            result["ack"],
            {"ok": True, "text": "今天天气怎么样", "reply": "今天晴，气温二十六度"},
        )
        session_dir = self.run_dir / "sessions" / session
        self.assertEqual((session_dir / "upload.wav").read_bytes(), raw)
        self.assertEqual(
            (session_dir / "reply.wav").read_bytes(),
            (ASSETS / "tts_weather.wav").read_bytes(),
        )
        self.assertEqual(result["pcm"], golden_pcm("tts_weather.wav"))

    def test_5xx_retry_timeout_and_4xx_error(self):
        for service in ("asr", "llm", "tts"):
            with self.subTest(service=service, mode="500"):
                self.control({"service": service, "mode": "500"})
                recovered = self.talk(f"retry-{service}-e2e", ASSETS / "ask_time.wav")
                self.assertEqual(recovered["ack"]["reply"], "现在是下午三点")

        for service in ("asr", "llm", "tts"):
            with self.subTest(service=service, mode="timeout"):
                self.control({"service": service, "hang_ms": 600})
                started = time.monotonic()
                timed_out = self.talk(f"timeout-{service}-e2e", ASSETS / "ask_time.wav")
                self.assertEqual(timed_out["error"]["code"], "UPSTREAM_TIMEOUT", timed_out)
                self.assertLess(time.monotonic() - started, 1.5)

        unknown = self.talk("unknown-e2e", ASSETS / "tts_weather.wav")
        self.assertEqual(unknown["error"]["code"], "UPSTREAM_ERROR")

    def test_downlink_disconnect_keeps_backend_available(self):
        raw = (ASSETS / "ask_weather.wav").read_bytes()
        chunks = [raw[index:index + UPLOAD_CHUNK_BYTES] for index in range(0, len(raw), UPLOAD_CHUNK_BYTES)]
        client = WireClient(self.backend_port)
        self.assertEqual(client.hello("drop-downlink"), 0)
        for seq, chunk in enumerate(chunks, 1):
            client.send(protocol.T_AUDIO_CHUNK, seq, chunk)
            client.recv()
        client.send(
            protocol.T_AUDIO_END,
            len(chunks),
            json.dumps(
                {"total_chunks": len(chunks), "sha256": hashlib.sha256(raw).hexdigest()}
            ).encode(),
        )
        self.assertEqual(client.recv()[0], protocol.T_ACK)
        client.sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
        client.close()
        result = self.talk("after-drop", ASSETS / "ask_time.wav")
        self.assertEqual(result["ack"]["text"], "现在几点了")
        self.assertIsNone(self.backend.poll())


if __name__ == "__main__":
    unittest.main()
