import socket
import threading
import time
import unittest
from unittest import mock

import http_client
import app


class HttpClientTests(unittest.TestCase):
    def run_server(self, server, parts):
        def target():
            try:
                server.recv(65536)
                for delay, part in parts:
                    time.sleep(delay)
                    server.sendall(part)
            except OSError:
                pass
            finally:
                server.close()

        thread = threading.Thread(target=target)
        thread.start()
        self.addCleanup(thread.join, 1)

    def test_response_body_limit_is_enforced_from_headers(self):
        client, server = socket.socketpair()
        self.run_server(server, [
            (0, b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nhello"),
        ])
        with mock.patch("http_client.socket.create_connection", return_value=client):
            with self.assertRaisesRegex(ValueError, "configured maximum"):
                http_client.post(
                    "http://127.0.0.1:9100/asr",
                    b"request",
                    "application/octet-stream",
                    1000,
                    4,
                    4096,
                )

    def test_slow_drip_cannot_extend_total_deadline(self):
        client, server = socket.socketpair()
        self.run_server(server, [
            (0, b"HTTP/1.1 200 OK\r\nContent-Length: 3\r\n\r\na"),
            (0.06, b"b"),
            (0.06, b"c"),
        ])
        with mock.patch("http_client.socket.create_connection", return_value=client):
            started = time.monotonic()
            with self.assertRaises(TimeoutError):
                http_client.post(
                    "http://127.0.0.1:9100/asr",
                    b"request",
                    "application/octet-stream",
                    100,
                    1024,
                    4096,
                )
        self.assertLess(time.monotonic() - started, 0.25)

    def test_malformed_5xx_body_still_obeys_retry_policy(self):
        clients = []
        for _ in range(2):
            client, server = socket.socketpair()
            clients.append(client)
            self.run_server(server, [
                (0, b"HTTP/1.1 500 Injected\r\nConnection: close\r\n\r\n"),
            ])
        cfg = {
            "mock_base_url": "http://127.0.0.1:9100",
            "retry_max_5xx": 1,
            "service_timeout_ms": 1000,
            "max_json_response_bytes": 4,
            "max_tts_wav_bytes": 4,
            "max_http_header_bytes": 4096,
        }
        with mock.patch(
            "http_client.socket.create_connection", side_effect=clients
        ) as connect:
            with self.assertRaises(app.RequestFailure) as caught:
                app._post_with_policy("/asr", b"request", "bytes", cfg)

        self.assertEqual(caught.exception.code, "UPSTREAM_ERROR")
        self.assertEqual(connect.call_count, 2)


if __name__ == "__main__":
    unittest.main()
