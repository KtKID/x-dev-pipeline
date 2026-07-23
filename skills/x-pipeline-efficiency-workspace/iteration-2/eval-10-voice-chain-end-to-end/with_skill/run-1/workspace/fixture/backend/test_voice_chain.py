import pathlib
import hashlib
import http.client
import json
import socket
import struct
import threading
import unittest
import wave
from unittest import mock

import app
import audio
import http_client
import protocol


ROOT = pathlib.Path(__file__).resolve().parent
ASSETS = ROOT.parent / "assets"
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


class ProtocolTests(unittest.TestCase):
    def test_fragmented_and_coalesced_frames(self):
        first = protocol.encode_frame(protocol.T_AUDIO_CHUNK, 1, b"a")
        second = protocol.encode_frame(protocol.T_AUDIO_CHUNK, 2, b"bc")
        decoder = protocol.FrameDecoder()
        self.assertEqual(decoder.feed(first[:7]), [])
        self.assertEqual(
            decoder.feed(first[7:] + second),
            [
                (protocol.T_AUDIO_CHUNK, 1, b"a"),
                (protocol.T_AUDIO_CHUNK, 2, b"bc"),
            ],
        )

    def test_protocol_errors(self):
        good = protocol.encode_frame(protocol.T_HELLO, 0, b"{}")
        cases = [
            (b"xx" + good[2:], "BAD_MAGIC"),
            (good[:-1] + bytes([good[-1] ^ 1]), "BAD_CRC"),
            (
                protocol.MAGIC
                + struct.pack(">BII", protocol.T_HELLO, 0, protocol.MAX_PAYLOAD + 1),
                "PAYLOAD_TOO_LARGE",
            ),
        ]
        for raw, code in cases:
            with self.subTest(code=code), self.assertRaisesRegex(protocol.ProtocolError, code) as caught:
                protocol.FrameDecoder().feed(raw)
            expected_seq = 0 if code == "BAD_MAGIC" else 0
            self.assertEqual(caught.exception.seq, expected_seq)

    def test_error_preserves_valid_prefix_and_bad_magic_is_immediate(self):
        valid = protocol.encode_frame(protocol.T_AUDIO_CHUNK, 1, b"valid")
        bad = protocol.encode_frame(protocol.T_AUDIO_CHUNK, 2, b"bad")
        bad = bad[:-1] + bytes([bad[-1] ^ 1])
        with self.assertRaises(protocol.ProtocolError) as caught:
            protocol.FrameDecoder().feed(valid + bad)
        self.assertEqual(
            caught.exception.frames,
            ((protocol.T_AUDIO_CHUNK, 1, b"valid"),),
        )
        with self.assertRaisesRegex(protocol.ProtocolError, "BAD_MAGIC"):
            protocol.FrameDecoder().feed(b"xx")


class AudioTests(unittest.TestCase):
    def test_fixture_wav_becomes_chunked_pcm(self):
        raw = (ASSETS / "tts_weather.wav").read_bytes()
        pcm = audio.wav_pcm(raw)
        self.assertEqual(pcm, golden_pcm("tts_weather.wav"))
        chunks = list(audio.chunk_pcm(pcm, audio.PLAYBACK_CHUNK_BYTES))
        self.assertEqual(b"".join(chunks), pcm)
        self.assertTrue(all(len(chunk) == audio.PLAYBACK_CHUNK_BYTES for chunk in chunks[:-1]))
        self.assertLessEqual(len(chunks[-1]), audio.PLAYBACK_CHUNK_BYTES)

    def test_rejects_wrong_device_format(self):
        raw = bytearray((ASSETS / "tts_weather.wav").read_bytes())
        raw[22:24] = struct.pack("<H", 2)
        with self.assertRaisesRegex(ValueError, "unsupported"):
            audio.wav_pcm(bytes(raw))


class SessionTests(unittest.TestCase):
    def test_contiguous_resume_and_idempotent_replay(self):
        state = app.SessionState("resume-1")
        first = b"a" * app.UPLOAD_CHUNK_BYTES
        final = b"b"
        state.accept_chunk(1, first)
        state.accept_chunk(1, first)
        self.assertEqual(state.last_seq, 1)
        state.accept_chunk(2, final)
        raw = first + final
        metadata = json.dumps(
            {"total_chunks": 2, "sha256": hashlib.sha256(raw).hexdigest()}
        ).encode()
        self.assertEqual(state.assemble(2, metadata), raw)

    def test_rejects_gap_replay_change_count_and_digest(self):
        state = app.SessionState("bad-1")
        with self.assertRaisesRegex(app.ConversationError, "gap"):
            state.accept_chunk(2, b"x")
        state.accept_chunk(1, b"x")
        with self.assertRaisesRegex(app.ConversationError, "differs"):
            state.accept_chunk(1, b"y")
        for metadata in (
            {"total_chunks": 2, "sha256": hashlib.sha256(b"x").hexdigest()},
            {"total_chunks": 1, "sha256": "0" * 64},
        ):
            with self.assertRaises(app.ConversationError):
                state.assemble(1, json.dumps(metadata).encode())

    def test_hello_identifier_is_path_safe(self):
        device, session = app.validate_hello(
            json.dumps({"device_id": "esp", "session_id": "safe_1-2.3"}).encode()
        )
        self.assertEqual((device, session), ("esp", "safe_1-2.3"))
        for session_id in (".", "..", "../escape", "", "slash/name", "x" * 129):
            with self.subTest(session_id=session_id), self.assertRaises(app.ConversationError):
                app.validate_hello(
                    json.dumps({"device_id": "esp", "session_id": session_id}).encode()
                )


class OrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.cfg = {
            "mock_base_url": "http://mock",
            "service_timeout_ms": 25,
            "retry_max_5xx": 1,
        }

    def test_successful_service_data_flow(self):
        replies = [
            (200, json.dumps({"text": "question"}).encode()),
            (200, json.dumps({"reply": "answer"}).encode()),
            (200, b"wav"),
        ]
        with mock.patch.object(app.http_client, "post", side_effect=replies) as post:
            self.assertEqual(app.orchestrate(b"upload", self.cfg), ("question", "answer", b"wav"))
        self.assertEqual(post.call_count, 3)
        self.assertEqual(post.call_args_list[0].args[1], b"upload")
        self.assertEqual(json.loads(post.call_args_list[1].args[1]), {"text": "question"})
        self.assertEqual(json.loads(post.call_args_list[2].args[1]), {"text": "answer"})

    def test_5xx_retries_once(self):
        with mock.patch.object(
            app.http_client,
            "post",
            side_effect=[(500, b"fail"), (200, b"ok")],
        ) as post:
            self.assertEqual(
                app.upstream_post(self.cfg, "/asr", b"data", "application/octet-stream"),
                b"ok",
            )
        self.assertEqual(post.call_count, 2)

    def test_5xx_exhaustion_and_4xx_have_exact_attempt_counts(self):
        cases = [
            ([(500, b"fail"), (503, b"fail")], 2),
            ([(400, b"bad")], 1),
            ([OSError("refused")], 1),
        ]
        for effects, expected_calls in cases:
            with self.subTest(effects=effects), mock.patch.object(
                app.http_client, "post", side_effect=effects
            ) as post:
                with self.assertRaises(app.ConversationError) as caught:
                    app.upstream_post(self.cfg, "/service", b"data", "application/json")
                self.assertEqual(caught.exception.code, "UPSTREAM_ERROR")
                self.assertEqual(post.call_count, expected_calls)

    def test_timeout_and_4xx_map_to_device_codes(self):
        cases = [(TimeoutError(), "UPSTREAM_TIMEOUT"), ((404, b"missing"), "UPSTREAM_ERROR")]
        for effect, code in cases:
            with self.subTest(code=code), mock.patch.object(app.http_client, "post", side_effect=[effect]):
                with self.assertRaises(app.ConversationError) as caught:
                    app.upstream_post(self.cfg, "/asr", b"data", "application/octet-stream")
                self.assertEqual(caught.exception.code, code)

    def test_incomplete_http_response_maps_to_upstream_error(self):
        class IncompleteResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                raise http.client.IncompleteRead(b"partial", 10)

        with mock.patch.object(http_client._opener, "open", return_value=IncompleteResponse()):
            with self.assertRaisesRegex(OSError, "incomplete HTTP response"):
                http_client.post("http://mock/asr", b"data", "application/octet-stream", 25)
        with mock.patch.object(
            app.http_client, "post", side_effect=OSError("incomplete HTTP response")
        ):
            with self.assertRaises(app.ConversationError) as caught:
                app.upstream_post(self.cfg, "/asr", b"data", "application/octet-stream")
        self.assertEqual(caught.exception.code, "UPSTREAM_ERROR")


class ConnectionTests(unittest.TestCase):
    def test_payload_too_large_reports_seq_closes_and_retains_prefix(self):
        cfg = {
            "mock_base_url": "http://mock",
            "service_timeout_ms": 25,
            "retry_max_5xx": 1,
        }
        session_id = "oversize-prefix-resume"
        server, client = socket.socketpair()
        worker = threading.Thread(target=app.handle_connection, args=(server, cfg))
        worker.start()
        client.sendall(
            protocol.encode_frame(
                protocol.T_HELLO,
                0,
                app.json_bytes({"device_id": "test", "session_id": session_id}),
            )
        )
        self.assertEqual(protocol.FrameDecoder().feed(client.recv(65536))[0][0], protocol.T_ACK)
        oversized = protocol.MAGIC + struct.pack(
            ">BII", protocol.T_AUDIO_CHUNK, 9, protocol.MAX_PAYLOAD + 1
        )
        client.sendall(protocol.encode_frame(protocol.T_AUDIO_CHUNK, 1, b"prefix") + oversized)
        received = b""
        while True:
            part = client.recv(65536)
            if not part:
                break
            received += part
        worker.join(2)
        client.close()
        response = protocol.FrameDecoder().feed(received)
        self.assertEqual([frame[0] for frame in response], [protocol.T_ACK, protocol.T_ERROR])
        self.assertEqual(response[-1][1], 9)
        self.assertEqual(json.loads(response[-1][2])["code"], "PAYLOAD_TOO_LARGE")

        server, client = socket.socketpair()
        worker = threading.Thread(target=app.handle_connection, args=(server, cfg))
        worker.start()
        client.sendall(
            protocol.encode_frame(
                protocol.T_HELLO,
                0,
                app.json_bytes({"device_id": "test", "session_id": session_id}),
            )
        )
        hello_ack = protocol.FrameDecoder().feed(client.recv(65536))[0]
        self.assertEqual(json.loads(hello_ack[2]), {"last_seq": 1})
        client.close()
        worker.join(2)

    def test_integrity_errors_close_without_upstream_calls(self):
        cfg = {
            "mock_base_url": "http://mock",
            "service_timeout_ms": 25,
            "retry_max_5xx": 1,
        }
        raw = b"short"
        digest = hashlib.sha256(raw).hexdigest()
        cases = [
            (
                "bad-digest",
                [
                    protocol.encode_frame(protocol.T_AUDIO_CHUNK, 1, raw),
                    protocol.encode_frame(
                        protocol.T_AUDIO_END,
                        1,
                        app.json_bytes({"total_chunks": 1, "sha256": "0" * 64}),
                    ),
                ],
                1,
            ),
            (
                "bad-end-count",
                [
                    protocol.encode_frame(protocol.T_AUDIO_CHUNK, 1, raw),
                    protocol.encode_frame(
                        protocol.T_AUDIO_END,
                        2,
                        app.json_bytes({"total_chunks": 1, "sha256": digest}),
                    ),
                ],
                2,
            ),
            (
                "bad-block-shape",
                [
                    protocol.encode_frame(protocol.T_AUDIO_CHUNK, 1, raw),
                    protocol.encode_frame(protocol.T_AUDIO_CHUNK, 2, b"later"),
                ],
                2,
            ),
        ]
        with mock.patch.object(app, "orchestrate") as orchestrate:
            for session_id, frames, expected_seq in cases:
                with self.subTest(session_id=session_id):
                    server, client = socket.socketpair()
                    worker = threading.Thread(target=app.handle_connection, args=(server, cfg))
                    worker.start()
                    client.sendall(
                        protocol.encode_frame(
                            protocol.T_HELLO,
                            0,
                            app.json_bytes({"device_id": "test", "session_id": session_id}),
                        )
                    )
                    self.assertEqual(
                        protocol.FrameDecoder().feed(client.recv(65536))[0][0], protocol.T_ACK
                    )
                    client.sendall(b"".join(frames))
                    received = b""
                    while True:
                        part = client.recv(65536)
                        if not part:
                            break
                        received += part
                    worker.join(2)
                    client.close()
                    response = protocol.FrameDecoder().feed(received)
                    error = next(frame for frame in response if frame[0] == protocol.T_ERROR)
                    self.assertEqual(error[1], expected_seq)
                    self.assertEqual(json.loads(error[2])["code"], "INTEGRITY_FAIL")
            orchestrate.assert_not_called()

    def test_valid_chunk_before_bad_frame_is_retained_for_resume(self):
        cfg = {
            "mock_base_url": "http://mock",
            "service_timeout_ms": 25,
            "retry_max_5xx": 1,
        }
        session_id = "valid-prefix-resume"
        server, client = socket.socketpair()
        worker = threading.Thread(target=app.handle_connection, args=(server, cfg))
        worker.start()
        client.sendall(
            protocol.encode_frame(
                protocol.T_HELLO,
                0,
                app.json_bytes({"device_id": "test", "session_id": session_id}),
            )
        )
        self.assertEqual(protocol.FrameDecoder().feed(client.recv(65536))[0][0], protocol.T_ACK)
        good = protocol.encode_frame(protocol.T_AUDIO_CHUNK, 1, b"short-final")
        bad = protocol.encode_frame(protocol.T_AUDIO_CHUNK, 2, b"bad")
        bad = bad[:-1] + bytes([bad[-1] ^ 1])
        client.sendall(good + bad)
        received = b""
        while True:
            part = client.recv(65536)
            if not part:
                break
            received += part
        worker.join(2)
        client.close()
        response = protocol.FrameDecoder().feed(received)
        self.assertEqual([frame[0] for frame in response], [protocol.T_ACK, protocol.T_ERROR])
        self.assertEqual(json.loads(response[-1][2])["code"], "BAD_CRC")

        server, client = socket.socketpair()
        worker = threading.Thread(target=app.handle_connection, args=(server, cfg))
        worker.start()
        client.sendall(
            protocol.encode_frame(
                protocol.T_HELLO,
                0,
                app.json_bytes({"device_id": "test", "session_id": session_id}),
            )
        )
        hello_ack = protocol.FrameDecoder().feed(client.recv(65536))[0]
        self.assertEqual(json.loads(hello_ack[2]), {"last_seq": 1})
        client.close()
        worker.join(2)
        self.assertFalse(worker.is_alive())

    def test_two_bad_magic_bytes_get_immediate_error(self):
        cfg = {
            "mock_base_url": "http://mock",
            "service_timeout_ms": 25,
            "retry_max_5xx": 1,
        }
        server, client = socket.socketpair()
        worker = threading.Thread(target=app.handle_connection, args=(server, cfg))
        worker.start()
        client.settimeout(1)
        client.sendall(b"xx")
        response = protocol.FrameDecoder().feed(client.recv(65536))[0]
        self.assertEqual(response[0], protocol.T_ERROR)
        self.assertEqual(json.loads(response[2])["code"], "BAD_MAGIC")
        self.assertEqual(client.recv(1), b"")
        client.close()
        worker.join(2)
        self.assertFalse(worker.is_alive())

    def test_ack_precedes_playable_chunks_and_integrity_end(self):
        upload = (ASSETS / "ask_weather.wav").read_bytes()
        tts_wav = (ASSETS / "tts_weather.wav").read_bytes()
        pcm = golden_pcm("tts_weather.wav")
        upload_chunks = [
            upload[index:index + app.UPLOAD_CHUNK_BYTES]
            for index in range(0, len(upload), app.UPLOAD_CHUNK_BYTES)
        ]
        session_id = "unit-connection-order"
        frames = [
            protocol.encode_frame(
                protocol.T_HELLO,
                0,
                app.json_bytes({"device_id": "test", "session_id": session_id}),
            )
        ]
        frames.extend(
            protocol.encode_frame(protocol.T_AUDIO_CHUNK, seq, chunk)
            for seq, chunk in enumerate(upload_chunks, 1)
        )
        frames.append(
            protocol.encode_frame(
                protocol.T_AUDIO_END,
                len(upload_chunks),
                app.json_bytes(
                    {
                        "total_chunks": len(upload_chunks),
                        "sha256": hashlib.sha256(upload).hexdigest(),
                    }
                ),
            )
        )
        server, client = socket.socketpair()
        cfg = {
            "mock_base_url": "http://mock",
            "service_timeout_ms": 25,
            "retry_max_5xx": 1,
        }
        with mock.patch.object(
            app, "orchestrate", return_value=("question", "answer", tts_wav)
        ), mock.patch.object(app, "atomic_write"):
            worker = threading.Thread(target=app.handle_connection, args=(server, cfg))
            worker.start()
            client.sendall(b"".join(frames))
            client.shutdown(socket.SHUT_WR)
            client.settimeout(2)
            received = b""
            while True:
                part = client.recv(65536)
                if not part:
                    break
                received += part
            worker.join(2)
        client.close()
        self.assertFalse(worker.is_alive())
        decoded = protocol.FrameDecoder().feed(received)
        chunk_acks = [
            frame[1]
            for frame in decoded
            if frame[0] == protocol.T_ACK and frame[2] == b"" and frame[1] > 0
        ]
        self.assertEqual(chunk_acks, list(range(1, len(upload_chunks) + 1)))
        end_ack_index = next(
            index
            for index, frame in enumerate(decoded)
            if frame[0] == protocol.T_ACK and frame[1] == len(upload_chunks) and frame[2]
        )
        first_tts_index = next(
            index for index, frame in enumerate(decoded) if frame[0] == protocol.T_TTS_CHUNK
        )
        self.assertLess(end_ack_index, first_tts_index)
        tts_chunks = [frame[2] for frame in decoded if frame[0] == protocol.T_TTS_CHUNK]
        self.assertEqual(b"".join(tts_chunks), pcm)
        tts_end = next(frame for frame in decoded if frame[0] == protocol.T_TTS_END)
        metadata = json.loads(tts_end[2])
        self.assertEqual(tts_end[1], len(tts_chunks))
        self.assertEqual(metadata["total_chunks"], len(tts_chunks))
        self.assertEqual(metadata["sha256"], hashlib.sha256(pcm).hexdigest())

    def test_downlink_send_failure_does_not_interrupt_concurrent_session(self):
        upload = (ASSETS / "ask_weather.wav").read_bytes()
        upload_chunks = [
            upload[index:index + app.UPLOAD_CHUNK_BYTES]
            for index in range(0, len(upload), app.UPLOAD_CHUNK_BYTES)
        ]

        def request(session_id):
            frames = [
                protocol.encode_frame(
                    protocol.T_HELLO,
                    0,
                    app.json_bytes({"device_id": "test", "session_id": session_id}),
                )
            ]
            frames.extend(
                protocol.encode_frame(protocol.T_AUDIO_CHUNK, seq, chunk)
                for seq, chunk in enumerate(upload_chunks, 1)
            )
            frames.append(
                protocol.encode_frame(
                    protocol.T_AUDIO_END,
                    len(upload_chunks),
                    app.json_bytes(
                        {
                            "total_chunks": len(upload_chunks),
                            "sha256": hashlib.sha256(upload).hexdigest(),
                        }
                    ),
                )
            )
            return b"".join(frames)

        class FailOnTtsSocket:
            def __init__(self, wrapped):
                self.wrapped = wrapped
                self.failed = threading.Event()

            def recv(self, size):
                return self.wrapped.recv(size)

            def sendall(self, data):
                if len(data) >= protocol.HEADER_LEN and data[2] == protocol.T_TTS_CHUNK:
                    self.failed.set()
                    raise BrokenPipeError("injected downlink failure")
                self.wrapped.sendall(data)

            def close(self):
                self.wrapped.close()

        cfg = {
            "mock_base_url": "http://mock",
            "service_timeout_ms": 25,
            "retry_max_5xx": 1,
        }
        first_server, first_client = socket.socketpair()
        second_server, second_client = socket.socketpair()
        failing = FailOnTtsSocket(first_server)
        barrier = threading.Barrier(2, timeout=2)
        tts_wav = (ASSETS / "tts_weather.wav").read_bytes()

        def concurrent_orchestrate(_upload, _cfg):
            barrier.wait()
            return "question", "answer", tts_wav

        with mock.patch.object(app, "orchestrate", side_effect=concurrent_orchestrate), mock.patch.object(
            app, "atomic_write"
        ):
            first_worker = threading.Thread(
                target=app.handle_connection, args=(failing, cfg)
            )
            second_worker = threading.Thread(
                target=app.handle_connection, args=(second_server, cfg)
            )
            first_worker.start()
            second_worker.start()
            first_client.sendall(request("downlink-fail-a"))
            second_client.sendall(request("downlink-fail-b"))
            first_received = b""
            second_received = b""
            while True:
                part = first_client.recv(65536)
                if not part:
                    break
                first_received += part
            while True:
                part = second_client.recv(65536)
                if not part:
                    break
                second_received += part
            first_worker.join(2)
            second_worker.join(2)
        first_client.close()
        second_client.close()
        self.assertTrue(failing.failed.is_set())
        self.assertFalse(first_worker.is_alive())
        self.assertFalse(second_worker.is_alive())
        first_frames = protocol.FrameDecoder().feed(first_received)
        second_frames = protocol.FrameDecoder().feed(second_received)
        self.assertTrue(any(frame[0] == protocol.T_ACK and frame[2] for frame in first_frames))
        self.assertFalse(any(frame[0] == protocol.T_TTS_END for frame in first_frames))
        self.assertTrue(any(frame[0] == protocol.T_TTS_END for frame in second_frames))


if __name__ == "__main__":
    unittest.main()
