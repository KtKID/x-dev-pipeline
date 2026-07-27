"""Bounded HTTP/1.1 client for the local mock services."""
import socket
import time
import urllib.parse


def _remaining(deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("HTTP request deadline exceeded")
    return remaining


def _recv(sock, size, deadline):
    sock.settimeout(_remaining(deadline))
    try:
        return sock.recv(size)
    except socket.timeout as exc:
        raise TimeoutError("HTTP request deadline exceeded") from exc


def post(url, data, content_type, timeout_ms, max_response_bytes, max_header_bytes):
    """Return ``(status, body)`` with a total deadline and bounded response."""
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "http" or not parsed.hostname:
        raise ValueError("only absolute http URLs are supported")
    port = parsed.port or 80
    target = urllib.parse.urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
    deadline = time.monotonic() + timeout_ms / 1000
    request = (
        f"POST {target} HTTP/1.1\r\n"
        f"Host: {parsed.hostname}:{port}\r\n"
        f"Content-Type: {content_type}\r\n"
        f"Content-Length: {len(data)}\r\n"
        "Connection: close\r\n\r\n"
    ).encode("ascii") + data

    try:
        sock = socket.create_connection(
            (parsed.hostname, port), timeout=_remaining(deadline)
        )
    except socket.timeout as exc:
        raise TimeoutError("HTTP connect deadline exceeded") from exc

    with sock:
        sock.settimeout(_remaining(deadline))
        try:
            sock.sendall(request)
        except socket.timeout as exc:
            raise TimeoutError("HTTP send deadline exceeded") from exc

        received = bytearray()
        marker = -1
        while marker < 0:
            part = _recv(sock, min(4096, max_header_bytes + 1 - len(received)), deadline)
            if not part:
                raise ValueError("upstream closed before HTTP headers")
            received.extend(part)
            marker = received.find(b"\r\n\r\n")
            if marker < 0 and len(received) > max_header_bytes:
                raise ValueError("HTTP headers exceed configured maximum")

        header_block = bytes(received[:marker])
        body = bytearray(received[marker + 4:])
        lines = header_block.split(b"\r\n")
        try:
            status = int(lines[0].split(b" ", 2)[1])
        except (IndexError, ValueError) as exc:
            raise ValueError("invalid HTTP status line") from exc
        if status != 200:
            return status, b""
        headers = {}
        for line in lines[1:]:
            if b":" not in line:
                raise ValueError("invalid HTTP header")
            key, value = line.split(b":", 1)
            headers[key.strip().lower()] = value.strip()
        if b"transfer-encoding" in headers:
            raise ValueError("chunked HTTP responses are unsupported")
        try:
            content_length = int(headers[b"content-length"])
        except (KeyError, ValueError) as exc:
            raise ValueError("HTTP response requires Content-Length") from exc
        if content_length < 0 or content_length > max_response_bytes:
            raise ValueError("HTTP response exceeds configured maximum")
        if len(body) > content_length:
            raise ValueError("HTTP response exceeds Content-Length")
        while len(body) < content_length:
            part = _recv(
                sock,
                min(65536, content_length - len(body)),
                deadline,
            )
            if not part:
                raise ValueError("truncated HTTP response body")
            body.extend(part)
        return status, bytes(body)
