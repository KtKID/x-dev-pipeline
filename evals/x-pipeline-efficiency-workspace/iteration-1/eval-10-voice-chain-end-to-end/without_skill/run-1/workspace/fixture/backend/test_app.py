import hashlib
import json
import pathlib
import socket
import tempfile
import unittest
from unittest import mock

import app
import protocol


class UploadSessionTests(unittest.TestCase):
    def setUp(self):
        app._reset_sessions_for_tests()
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.cfg = {
            "audio_chunk_bytes": 4,
            "session_id_max_length": 128,
            "device_id_max_length": 128,
            "max_upload_bytes": 16,
            "max_sessions": 4,
            "session_ttl_seconds": 60,
            "sessions_dir": self.temporary.name,
        }

    def hello(self, session_id="session-1", device_id="device-1"):
        return json.dumps({
            "session_id": session_id,
            "device_id": device_id,
        }).encode()

    def end(self, raw, total):
        return json.dumps({
            "total_chunks": total,
            "sha256": hashlib.sha256(raw).hexdigest(),
        }).encode()

    def test_resume_reports_contiguous_last_sequence(self):
        _, session = app._open_session(self.hello(), self.cfg)
        app._accept_chunk(session, 1, b"abcd", self.cfg)
        app._accept_chunk(session, 2, b"ef", self.cfg)

        _, resumed = app._open_session(self.hello(), self.cfg)

        self.assertIs(resumed, session)
        self.assertEqual(resumed.last_seq, 2)
        self.assertEqual(app._assemble_upload(
            resumed, 2, self.end(b"abcdef", 2), self.cfg
        ), b"abcdef")

    def test_repeated_chunk_is_idempotent_and_conflict_fails(self):
        _, session = app._open_session(self.hello(), self.cfg)
        app._accept_chunk(session, 1, b"abcd", self.cfg)
        app._accept_chunk(session, 1, b"abcd", self.cfg)

        with self.assertRaisesRegex(app.RequestFailure, "conflicting"):
            app._accept_chunk(session, 1, b"wxyz", self.cfg)
        self.assertEqual(session.last_seq, 1)

    def test_gap_and_chunk_after_short_chunk_fail(self):
        _, session = app._open_session(self.hello(), self.cfg)
        with self.assertRaisesRegex(app.RequestFailure, "contiguous"):
            app._accept_chunk(session, 2, b"abcd", self.cfg)
        app._accept_chunk(session, 1, b"ab", self.cfg)
        with self.assertRaisesRegex(app.RequestFailure, "short final"):
            app._accept_chunk(session, 2, b"cd", self.cfg)

    def test_end_rejects_missing_chunks_and_wrong_hash(self):
        _, session = app._open_session(self.hello(), self.cfg)
        app._accept_chunk(session, 1, b"abcd", self.cfg)
        with self.assertRaisesRegex(app.RequestFailure, "missing"):
            app._assemble_upload(session, 2, self.end(b"abcdefgh", 2), self.cfg)
        with self.assertRaisesRegex(app.RequestFailure, "sha256"):
            app._assemble_upload(session, 1, self.end(b"wrong", 1), self.cfg)

    def test_session_id_cannot_escape_sessions_directory(self):
        for value in ("../escape", "/absolute", "..", "with/slash", ""):
            with self.subTest(value=value):
                with self.assertRaises(app.RequestFailure):
                    app._open_session(self.hello(session_id=value), self.cfg)

    def test_session_belongs_to_one_device(self):
        app._open_session(self.hello(), self.cfg)
        with self.assertRaisesRegex(app.RequestFailure, "another device"):
            app._open_session(self.hello(device_id="device-2"), self.cfg)

    def test_atomic_write_replaces_complete_file(self):
        target = pathlib.Path(self.temporary.name) / "session-1" / "upload.wav"
        app._atomic_write(target, b"first")
        app._atomic_write(target, b"second")

        self.assertEqual(target.read_bytes(), b"second")
        self.assertEqual(list(target.parent.iterdir()), [target])

    def test_upload_and_session_capacity_are_bounded(self):
        _, session = app._open_session(self.hello(), self.cfg)
        limited = dict(self.cfg, max_upload_bytes=3)
        with self.assertRaisesRegex(app.RequestFailure, "upload exceeds"):
            app._accept_chunk(session, 1, b"abcd", limited)

        capacity = dict(self.cfg, max_sessions=1)
        with self.assertRaisesRegex(app.RequestFailure, "capacity"):
            app._open_session(self.hello(session_id="session-2"), capacity)

        with session.condition:
            session.active_connections = 0
            session.last_activity -= capacity["session_ttl_seconds"] + 1
        _, replacement = app._open_session(
            self.hello(session_id="session-2"), capacity
        )
        self.assertIsNot(replacement, session)

    @unittest.skipUnless(hasattr(__import__("os"), "O_NOFOLLOW"), "requires O_NOFOLLOW")
    def test_session_directory_symlink_is_rejected(self):
        outside = pathlib.Path(self.temporary.name) / "outside"
        outside.mkdir()
        sessions = pathlib.Path(self.temporary.name) / "root"
        sessions.mkdir()
        (sessions / "safe-id").symlink_to(outside, target_is_directory=True)
        cfg = dict(self.cfg, sessions_dir=str(sessions))

        with self.assertRaisesRegex(app.RequestFailure, "unsafe session"):
            app._write_session_file("safe-id", "upload.wav", b"data", cfg)

        self.assertFalse((outside / "upload.wav").exists())


class OrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.cfg = {
            "mock_base_url": "http://127.0.0.1:9100",
            "service_timeout_ms": 1234,
            "retry_max_5xx": 1,
            "max_json_response_bytes": 1024,
            "max_tts_wav_bytes": 4096,
            "max_http_header_bytes": 4096,
        }

    @mock.patch("app.http_client.post")
    def test_services_are_called_in_order_with_expected_payloads(self, post):
        post.side_effect = [
            (200, json.dumps({"text": "question"}).encode()),
            (200, json.dumps({"reply": "answer"}).encode()),
            (200, b"wav"),
        ]

        self.assertEqual(
            app._orchestrate(b"upload", self.cfg),
            ("question", "answer", b"wav"),
        )
        self.assertEqual([call.args[0] for call in post.call_args_list], [
            "http://127.0.0.1:9100/asr",
            "http://127.0.0.1:9100/llm",
            "http://127.0.0.1:9100/tts",
        ])
        self.assertEqual(post.call_args_list[0].args[1], b"upload")
        self.assertEqual(
            json.loads(post.call_args_list[1].args[1]), {"text": "question"}
        )
        self.assertEqual(
            json.loads(post.call_args_list[2].args[1]), {"text": "answer"}
        )
        self.assertTrue(all(
            call.args[3] == self.cfg["service_timeout_ms"]
            for call in post.call_args_list
        ))
        self.assertEqual([call.args[4] for call in post.call_args_list], [
            self.cfg["max_json_response_bytes"],
            self.cfg["max_json_response_bytes"],
            self.cfg["max_tts_wav_bytes"],
        ])

    @mock.patch("app.http_client.post")
    def test_one_5xx_is_retried_then_recovers(self, post):
        post.side_effect = [(500, b"error"), (200, b"ok")]

        self.assertEqual(
            app._post_with_policy("/asr", b"data", "bytes", self.cfg), b"ok"
        )
        self.assertEqual(post.call_count, 2)

    @mock.patch("app.http_client.post")
    def test_5xx_retry_exhaustion_is_upstream_error(self, post):
        post.return_value = (500, b"error")

        with self.assertRaises(app.RequestFailure) as caught:
            app._post_with_policy("/asr", b"data", "bytes", self.cfg)

        self.assertEqual(caught.exception.code, "UPSTREAM_ERROR")
        self.assertEqual(post.call_count, 2)

    @mock.patch("app.http_client.post")
    def test_timeout_is_not_retried(self, post):
        post.side_effect = TimeoutError("late")

        with self.assertRaises(app.RequestFailure) as caught:
            app._post_with_policy("/asr", b"data", "bytes", self.cfg)

        self.assertEqual(caught.exception.code, "UPSTREAM_TIMEOUT")
        self.assertEqual(post.call_count, 1)

    @mock.patch("app.http_client.post")
    def test_socket_timeout_is_not_retried(self, post):
        post.side_effect = socket.timeout("late")

        with self.assertRaises(app.RequestFailure) as caught:
            app._post_with_policy("/asr", b"data", "bytes", self.cfg)

        self.assertEqual(caught.exception.code, "UPSTREAM_TIMEOUT")
        self.assertEqual(post.call_count, 1)

    @mock.patch("app.http_client.post")
    def test_4xx_is_not_retried(self, post):
        post.return_value = (404, b"unknown")

        with self.assertRaises(app.RequestFailure) as caught:
            app._post_with_policy("/asr", b"data", "bytes", self.cfg)

        self.assertEqual(caught.exception.code, "UPSTREAM_ERROR")
        self.assertEqual(post.call_count, 1)

    @mock.patch("app.http_client.post")
    def test_malformed_success_is_upstream_error(self, post):
        post.return_value = (200, b"{}")

        with self.assertRaises(app.RequestFailure) as caught:
            app._orchestrate(b"upload", self.cfg)

        self.assertEqual(caught.exception.code, "UPSTREAM_ERROR")
        self.assertEqual(post.call_count, 1)


class RecordingConnection:
    def __init__(self, fail_after=None):
        self.data = bytearray()
        self.calls = 0
        self.fail_after = fail_after

    def sendall(self, data):
        if self.fail_after is not None and self.calls >= self.fail_after:
            raise BrokenPipeError("disconnected")
        self.calls += 1
        self.data.extend(data)


class ScriptedConnection(RecordingConnection):
    def __init__(self, received):
        super().__init__()
        self.received = list(received)
        self.closed = False

    def recv(self, _):
        return self.received.pop(0) if self.received else b""

    def close(self):
        self.closed = True


class DownlinkTests(unittest.TestCase):
    def test_downlink_chunks_and_integrity_tail(self):
        conn = RecordingConnection()
        pcm = b"abcdefghij"

        app._send_downlink(conn, pcm, {"audio_chunk_bytes": 4})

        frames = protocol.FrameDecoder().feed(conn.data)
        self.assertEqual(frames[:-1], [
            (protocol.T_TTS_CHUNK, 1, b"abcd"),
            (protocol.T_TTS_CHUNK, 2, b"efgh"),
            (protocol.T_TTS_CHUNK, 3, b"ij"),
        ])
        self.assertEqual(frames[-1][0:2], (protocol.T_TTS_END, 3))
        tail = json.loads(frames[-1][2])
        self.assertEqual(tail, {
            "total_chunks": 3,
            "sha256": hashlib.sha256(pcm).hexdigest(),
        })

    def test_valid_hello_is_acked_before_later_bad_crc_error(self):
        app._reset_sessions_for_tests()
        hello = protocol.encode_frame(protocol.T_HELLO, 0, json.dumps({
            "device_id": "device-1",
            "session_id": "mixed-packet",
        }).encode())
        bad = bytearray(protocol.encode_frame(protocol.T_AUDIO_CHUNK, 1, b"abcd"))
        bad[-1] ^= 0xFF
        conn = ScriptedConnection([hello + bad])
        cfg = {
            "session_id_max_length": 128,
            "device_id_max_length": 128,
            "max_sessions": 4,
            "session_ttl_seconds": 60,
        }

        app.handle_connection(conn, cfg)

        frames = protocol.FrameDecoder().feed(conn.data)
        self.assertEqual(frames[0][:2], (protocol.T_ACK, 0))
        self.assertEqual(json.loads(frames[0][2]), {"last_seq": 0})
        self.assertEqual(frames[1][:2], (protocol.T_ERROR, 1))
        self.assertEqual(json.loads(frames[1][2])["code"], "BAD_CRC")
        self.assertTrue(conn.closed)

    def test_json_frame_over_wire_limit_becomes_upstream_error(self):
        with self.assertRaises(app.RequestFailure) as caught:
            app._send_json_frame(
                RecordingConnection(),
                protocol.T_ACK,
                0,
                {"text": "x" * protocol.MAX_PAYLOAD},
            )
        self.assertEqual(caught.exception.code, "UPSTREAM_ERROR")

    @mock.patch("app._get_or_process")
    def test_audio_end_then_bad_crc_in_same_batch_gets_error(self, process):
        app._reset_sessions_for_tests()
        process.return_value = ("question", "answer", b"wav", b"pcm")
        raw = b"abcd"
        hello = protocol.encode_frame(protocol.T_HELLO, 0, json.dumps({
            "device_id": "device-1",
            "session_id": "end-then-error",
        }).encode())
        chunk = protocol.encode_frame(protocol.T_AUDIO_CHUNK, 1, raw)
        end = protocol.encode_frame(protocol.T_AUDIO_END, 1, json.dumps({
            "total_chunks": 1,
            "sha256": hashlib.sha256(raw).hexdigest(),
        }).encode())
        bad = bytearray(protocol.encode_frame(protocol.T_AUDIO_CHUNK, 2, b"more"))
        bad[-1] ^= 0xFF
        conn = ScriptedConnection([hello + chunk + end + bad])
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        cfg = {
            "audio_chunk_bytes": 4,
            "session_id_max_length": 128,
            "device_id_max_length": 128,
            "max_upload_bytes": 16,
            "max_sessions": 4,
            "session_ttl_seconds": 60,
            "sessions_dir": temporary.name,
        }

        app.handle_connection(conn, cfg)

        frames = protocol.FrameDecoder().feed(conn.data)
        self.assertEqual(frames[-1][:2], (protocol.T_ERROR, 2))
        self.assertEqual(json.loads(frames[-1][2])["code"], "BAD_CRC")

if __name__ == "__main__":
    unittest.main()
